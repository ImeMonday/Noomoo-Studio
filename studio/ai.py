"""Optional AI layer (captions). Always degrades to deterministic copy.

Works with any OpenAI-compatible chat-completions endpoint, so it can talk to Meta's Model API
(Muse Spark), or any other provider, purely through environment variables. Results are cached on
disk by prompt hash, which keeps repeated builds identical and free.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import sys
import urllib.error
import urllib.request
from pathlib import Path

from .config import ROOT, Brand, Content

_EMOJI = re.compile("[\u2190-\u2bff\U0001F000-\U0001FAFF]")


def _load_dotenv() -> None:
    env = ROOT / ".env"
    if not env.exists():
        return
    for line in env.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            key, _, value = line.partition("=")
            os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


class AIClient:
    def __init__(self, provider="none", base_url="", model="", api_key="", cache_path: Path | None = None,
                 timeout: float = 20.0):
        self.provider, self.base_url, self.model = provider, base_url.rstrip("/"), model
        self.api_key, self.timeout = api_key, timeout
        self.cache_path = cache_path or (ROOT / ".cache" / "ai.json")
        self._cache = None
        self._warned = False

    @classmethod
    def from_env(cls, provider: str | None = None) -> "AIClient":
        _load_dotenv()
        provider = provider or os.environ.get("AI_PROVIDER", "none")
        return cls(provider, os.environ.get("AI_BASE_URL", ""), os.environ.get("AI_MODEL", "muse-spark-1.1"),
                   os.environ.get("MODEL_API_KEY") or os.environ.get("AI_API_KEY", ""))

    @property
    def enabled(self) -> bool:
        return self.provider == "openai_compat" and bool(self.base_url and self.api_key)

    # -- cache -------------------------------------------------------------------------------
    def _load_cache(self) -> dict:
        if self._cache is None:
            try:
                self._cache = json.loads(self.cache_path.read_text(encoding="utf-8"))
            except (FileNotFoundError, json.JSONDecodeError):
                self._cache = {}
        return self._cache

    def _save_cache(self) -> None:
        self.cache_path.parent.mkdir(parents=True, exist_ok=True)
        self.cache_path.write_text(json.dumps(self._cache, indent=1, sort_keys=True), encoding="utf-8")

    # -- transport ---------------------------------------------------------------------------
    def complete(self, system: str, user: str, max_tokens: int = 60) -> str | None:
        if not self.enabled:
            return None
        key = hashlib.sha256(json.dumps([self.model, system, user]).encode()).hexdigest()
        cache = self._load_cache()
        if key in cache:
            return cache[key]
        body = json.dumps({"model": self.model, "max_tokens": max_tokens, "temperature": 0.4,
                           "messages": [{"role": "system", "content": system},
                                        {"role": "user", "content": user}]}).encode()
        req = urllib.request.Request(f"{self.base_url}/chat/completions", data=body, method="POST", headers={
            "Content-Type": "application/json", "Authorization": f"Bearer {self.api_key}"})
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                data = json.loads(resp.read().decode("utf-8"))
            content = data["choices"][0]["message"]["content"]
            if isinstance(content, list):
                content = "".join(p.get("text", "") for p in content)
        except (urllib.error.URLError, TimeoutError, KeyError, IndexError, ValueError, OSError) as exc:
            if not self._warned:
                print(f"[ai] provider unavailable ({type(exc).__name__}); using deterministic copy", file=sys.stderr)
                self._warned = True
            return None
        cache[key] = content
        self._save_cache()
        return content

    # -- features ----------------------------------------------------------------------------
    def caption(self, brand: Brand, info, fallback: str) -> str:
        """One short on-brand caption for an image; falls back to deterministic copy."""
        voice = ", ".join(brand.voice.get("adjectives", []))
        avoid = ", ".join(brand.voice.get("avoid", []))
        system = (f"You write Instagram tile captions for {brand.name}, a fictional hotel. Voice: {voice}. "
                  f"Never use these words: {avoid}. Reply with ONE caption of at most 8 words. "
                  "No hashtags, no emoji, no quotation marks.")
        out = self.complete(system, f"Image: {info.alt}. Tags: {', '.join(info.tags)}.")
        return clean_caption(out, brand) or fallback


def clean_caption(text: str | None, brand: Brand) -> str | None:
    """Accept model output only if it is a single short, brand-safe line."""
    if not text:
        return None
    line = text.strip().splitlines()[0].strip().strip("\"'\u201c\u201d")
    line = re.sub(r"\s+", " ", line)
    avoid = [w.lower() for w in brand.voice.get("avoid", [])]
    if not line or len(line) > 64 or "#" in line or _EMOJI.search(line) or any(w in line.lower() for w in avoid):
        return None
    return line


def fallback_caption(brand: Brand, content: Content, info) -> str:
    """Deterministic caption: curated copy first, else a templated line seeded by the image id."""
    if info.id in content.captions:
        return content.captions[info.id]
    seed = int(hashlib.sha1(info.id.encode()).hexdigest(), 16)
    template = content.fallback_captions[seed % len(content.fallback_captions)]
    alt = info.alt[:1].upper() + info.alt[1:]
    return template.format(alt=alt, name=brand.name, handle=brand.handle,
                           tag=(info.tags[0] if info.tags else "light"))
