"""Project state: the 3x3 grid, three stories, and every operation on them."""
from __future__ import annotations

import copy
import hashlib
import io
import json
import re
from dataclasses import asdict, dataclass
from pathlib import Path

from PIL import Image, ImageOps

from . import curate, imaging, layout, render
from .ai import AIClient, fallback_caption
from .config import WORKSPACE, load_brand, load_content, list_brands

MAX_UPLOAD_BYTES = 15 * 1024 * 1024
MIN_SIDE = 600
MAX_FIELD_CHARS = 220


@dataclass
class PostSlot:
    image_id: str
    template: str        # "full" | "arch"
    bg: str | None       # palette role behind the arch image
    caption: str
    locked: bool = False


@dataclass
class StorySlot:
    image_id: str
    template: str        # "hero" | "quote" | "offer"
    fields: dict
    locked: bool = False


class Project:
    def __init__(self, brand_id: str, ai: AIClient | None = None, workspace: Path = WORKSPACE):
        self.brand_id = brand_id
        self.brand = load_brand(brand_id)
        self.content = load_content(brand_id)
        self.ai = ai or AIClient()
        self.dir = workspace / brand_id
        self.uploads = self.dir / "uploads"
        self.library = imaging.load_library(self.uploads)
        self.posts: list = []
        self.stories: list = []
        self.report: dict = {}
        self.version = 0

    # -- lifecycle ---------------------------------------------------------------------------
    @classmethod
    def open(cls, brand_id: str, ai: AIClient | None = None, workspace: Path = WORKSPACE, fresh: bool = False):
        project = cls(brand_id, ai, workspace)
        if not fresh and project._load():
            return project
        project.curate(keep_locked=False)
        return project

    def _state_file(self) -> Path:
        return self.dir / "project.json"

    def _load(self) -> bool:
        try:
            raw = json.loads(self._state_file().read_text(encoding="utf-8"))
            posts = [PostSlot(**p) for p in raw["posts"]]
            stories = [StorySlot(**s) for s in raw["stories"]]
            if any(s.image_id not in self.library for s in posts + stories) or len(posts) != 9 or len(stories) != 3:
                return False
        except (FileNotFoundError, KeyError, TypeError, json.JSONDecodeError):
            return False
        self.posts, self.stories, self.report, self.version = posts, stories, raw.get("report", {}), raw.get("version", 0)
        return True

    def save(self) -> None:
        self.dir.mkdir(parents=True, exist_ok=True)
        data = {"posts": [asdict(p) for p in self.posts], "stories": [asdict(s) for s in self.stories],
                "report": self.report, "version": self.version}
        self._state_file().write_text(json.dumps(data, indent=1), encoding="utf-8")

    def _bump(self) -> None:
        self.version += 1
        self.save()

    # -- curation ----------------------------------------------------------------------------
    def caption_for(self, image_id: str) -> str:
        """Curated caption if the brand has one; otherwise AI (when enabled) or deterministic fallback copy."""
        info = self.library[image_id]
        if info.id in self.content.captions:
            return self.content.captions[info.id]
        return self.ai.caption(self.brand, info, fallback_caption(self.brand, self.content, info))

    def curate(self, keep_locked: bool = True) -> None:
        locked = {i: p.image_id for i, p in enumerate(self.posts) if keep_locked and p.locked}
        old_captions = {i: p.caption for i, p in enumerate(self.posts) if i in locked}
        plan, leftovers = curate.plan_grid(self.library, self.brand, locked)
        self.posts = []
        for cell, iid in enumerate(plan.order):
            template = "arch" if cell in curate.ARCH_CELLS else "full"
            self.posts.append(PostSlot(iid, template, plan.arch_bg.get(cell), old_captions.get(cell) or self.caption_for(iid),
                                       locked=cell in locked))
        keep = {i: s for i, s in enumerate(self.stories) if keep_locked and s.locked}
        taken = {p.image_id for p in self.posts}
        pool = [i for i in leftovers if i not in {s.image_id for s in keep.values()}]
        picks = curate.pick_story_images(self.library, self.brand, self.content.stories, pool, taken)
        self.stories = []
        for i, spec in enumerate(self.content.stories):
            if i in keep:
                self.stories.append(keep[i])
            else:
                self.stories.append(StorySlot(picks[i], spec.template, copy.deepcopy(spec.fields)))
        self.report = plan.report
        self._bump()

    def _refresh_backgrounds(self) -> None:
        infos = [self.library[p.image_id] for p in self.posts]
        bg = curate.pick_arch_backgrounds(infos, self.brand)
        for cell, role in bg.items():
            self.posts[cell].bg = role

    # -- editing -----------------------------------------------------------------------------
    def replace(self, kind: str, index: int, image_id: str) -> None:
        """Put an image into a slot and lock it. Posts swap if the image is already in the grid."""
        if image_id not in self.library:
            raise KeyError(f"Unknown image: {image_id}")
        if kind == "post":
            slot = self.posts[index]
            other = next((i for i, p in enumerate(self.posts) if p.image_id == image_id and i != index), None)
            if other is not None:
                o = self.posts[other]
                slot.image_id, o.image_id = o.image_id, slot.image_id
                slot.caption, o.caption = o.caption, slot.caption
                o.locked = True
            else:
                slot.image_id = image_id
                slot.caption = self.caption_for(image_id)
            slot.locked = True
            self._refresh_backgrounds()
        elif kind == "story":
            slot = self.stories[index]
            slot.image_id, slot.locked = image_id, True
        else:
            raise ValueError("kind must be 'post' or 'story'")
        self._bump()

    def set_field(self, kind: str, index: int, name: str, value) -> None:
        """Edit live text. Posts have a caption; stories expose the fields from content.json."""
        if kind == "post":
            if name != "caption":
                raise ValueError("Posts only have a caption")
            self.posts[index].caption = _clean(value)
        else:
            fields = self.stories[index].fields
            if name not in fields:
                raise ValueError(f"Unknown field: {name}")
            fields[name] = [_clean(v) for v in value][:3] if isinstance(fields[name], list) else _clean(value)
        self._bump()

    def add_upload(self, data: bytes, label: str = "") -> str:
        """Validate, normalise and register a user image. Returns its id."""
        if len(data) > MAX_UPLOAD_BYTES:
            raise ValueError("Image is larger than 15 MB")
        try:
            im = Image.open(io.BytesIO(data))
            fmt = im.format
            im.load()
        except Exception as exc:  # Pillow raises many types for corrupt input
            raise ValueError("That file is not a readable image") from exc
        if fmt not in ("JPEG", "PNG", "WEBP"):
            raise ValueError("Use a JPEG, PNG or WebP image")
        im = ImageOps.exif_transpose(im).convert("RGB")
        if min(im.size) < MIN_SIDE:
            raise ValueError(f"Image is too small: the short side must be at least {MIN_SIDE} px")
        im.thumbnail((2400, 2400))
        iid = "upload-" + hashlib.sha256(im.tobytes()).hexdigest()[:10]
        self.uploads.mkdir(parents=True, exist_ok=True)
        im.save(self.uploads / f"{iid}.jpg", "JPEG", quality=90, optimize=True)
        manifest = self.uploads / "manifest.json"
        entries = json.loads(manifest.read_text(encoding="utf-8")) if manifest.exists() else []
        if not any(e["id"] == iid for e in entries):
            alt = re.sub(r"[^A-Za-z0-9 ]+", " ", Path(label).stem).strip()[:60] or "Uploaded image"
            entries.append({"id": iid, "file": f"{iid}.jpg", "category": "upload", "alt": alt, "tags": [],
                            "license": "user supplied (synthetic, licensed or self-created only)"})
            manifest.write_text(json.dumps(entries, indent=1), encoding="utf-8")
        self.library = imaging.load_library(self.uploads)
        return iid

    # -- canvases ----------------------------------------------------------------------------
    @staticmethod
    def _href(scale: float):
        """Image loader; scale < 1 embeds lower-resolution pixels (used for the lightweight preview page)."""
        if scale >= 1:
            return imaging.data_uri
        return lambda info, w, h: imaging.data_uri(info, max(1, int(w * scale)), max(1, int(h * scale)), 72)

    def post_canvas(self, index: int, scale: float = 1.0) -> dict:
        slot = self.posts[index]
        return layout.post_canvas(self.brand, slot, self.library[slot.image_id], self._href(scale), f"p{index + 1}", index + 1)

    def story_canvas(self, index: int, scale: float = 1.0) -> dict:
        slot = self.stories[index]
        return layout.story_canvas(self.brand, slot, self.library[slot.image_id], self._href(scale), f"s{index + 1}", index + 1)

    def post_svg(self, index: int, font_base: str = "fonts/") -> str:
        return render.to_svg(self.post_canvas(index), self.brand, font_base)

    def story_svg(self, index: int, font_base: str = "fonts/") -> str:
        return render.to_svg(self.story_canvas(index), self.brand, font_base)

    # -- API view ----------------------------------------------------------------------------
    def to_dict(self) -> dict:
        def view(slot, index, kind):
            info = self.library[slot.image_id]
            d = {"kind": kind, "index": index, "image_id": slot.image_id, "template": slot.template,
                 "locked": slot.locked, "alt": info.alt, "category": info.category}
            if kind == "post":
                d["bg"] = slot.bg
                d["fields"] = {"caption": slot.caption}
            else:
                d["fields"] = {k: ("\n".join(v) if isinstance(v, list) else v) for k, v in slot.fields.items()}
            return d
        return {"brand": {"id": self.brand.id, "name": self.brand.name, "tagline": self.brand.tagline,
                          "palette": self.brand.palette, "display_font": self.brand.fonts["display"].family,
                          "display_font_file": self.brand.fonts["display"].file},
                "brands": list_brands(), "version": self.version,
                "posts": [view(p, i, "post") for i, p in enumerate(self.posts)],
                "stories": [view(s, i, "story") for i, s in enumerate(self.stories)],
                "library": [{"id": i.id, "alt": i.alt, "category": i.category} for i in sorted(self.library.values(), key=lambda x: x.id)],
                "report": self.report, "ai": {"enabled": self.ai.enabled, "provider": self.ai.provider}}


def _clean(value) -> str:
    text = re.sub(r"\s+", " ", str(value)).strip()
    if len(text) > MAX_FIELD_CHARS:
        raise ValueError(f"Text is limited to {MAX_FIELD_CHARS} characters")
    return text
