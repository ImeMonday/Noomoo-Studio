"""Brand and content configuration: loading and strict validation."""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BRANDS_DIR = ROOT / "brands"
ASSETS_DIR = ROOT / "assets"
IMAGES_DIR = ASSETS_DIR / "images"
FONTS_DIR = ASSETS_DIR / "fonts"
WORKSPACE = ROOT / "workspace"
DIST = ROOT / "dist"

HEX = re.compile(r"^#[0-9A-Fa-f]{6}$")
REQUIRED_COLORS = ("ink", "paper", "primary", "accent", "soft")
FONT_ROLES = ("display", "body", "strong")
STORY_TEMPLATES = ("hero", "quote", "offer")
MARKS = ("arch", "sun", "wave")


class ConfigError(ValueError):
    """Raised when a brand or content file is invalid."""


@dataclass(frozen=True)
class FontSpec:
    family: str
    weight: int
    file: str

    @property
    def path(self) -> Path:
        return FONTS_DIR / self.file


@dataclass(frozen=True)
class Brand:
    id: str
    name: str
    tagline: str
    handle: str
    mark: str
    palette: dict
    tile_backgrounds: tuple
    fonts: dict
    voice: dict

    def color(self, key: str) -> str:
        """Resolve a palette role (e.g. 'primary') or pass a hex value through."""
        return self.palette.get(key, key)


@dataclass
class StorySpec:
    template: str
    prefer: list
    fields: dict


@dataclass
class Content:
    captions: dict
    fallback_captions: list
    stories: list = field(default_factory=list)


def list_brands() -> list:
    return sorted(p.name for p in BRANDS_DIR.iterdir() if (p / "brand.json").exists())


def _read(path: Path) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise ConfigError(f"Missing file: {path}") from exc
    except json.JSONDecodeError as exc:
        raise ConfigError(f"Invalid JSON in {path}: {exc}") from exc


def load_brand(brand_id: str) -> Brand:
    raw = _read(BRANDS_DIR / brand_id / "brand.json")
    for key in ("name", "tagline", "handle", "mark", "palette", "tile_backgrounds", "fonts", "voice"):
        if key not in raw:
            raise ConfigError(f"{brand_id}/brand.json: missing '{key}'")
    for role in REQUIRED_COLORS:
        if not HEX.match(raw["palette"].get(role, "")):
            raise ConfigError(f"{brand_id}: palette.{role} must be a #RRGGBB hex colour")
    if raw["mark"] not in MARKS:
        raise ConfigError(f"{brand_id}: mark must be one of {MARKS}")
    for bg in raw["tile_backgrounds"]:
        if bg not in raw["palette"]:
            raise ConfigError(f"{brand_id}: tile_backgrounds entry '{bg}' is not a palette role")
    fonts = {}
    for role in FONT_ROLES:
        spec = raw["fonts"].get(role)
        if not spec:
            raise ConfigError(f"{brand_id}: fonts.{role} is required")
        font = FontSpec(spec["family"], int(spec["weight"]), spec["file"])
        if not font.path.exists():
            raise ConfigError(f"{brand_id}: font file not found: {font.path}")
        fonts[role] = font
    return Brand(brand_id, raw["name"], raw["tagline"], raw["handle"], raw["mark"], raw["palette"],
                 tuple(raw["tile_backgrounds"]), fonts, raw["voice"])


def load_content(brand_id: str) -> Content:
    raw = _read(BRANDS_DIR / brand_id / "content.json")
    stories = []
    for i, s in enumerate(raw.get("stories", [])):
        if s.get("template") not in STORY_TEMPLATES:
            raise ConfigError(f"{brand_id}: story {i + 1} template must be one of {STORY_TEMPLATES}")
        fields = {k: v for k, v in s.items() if k not in ("template", "prefer")}
        stories.append(StorySpec(s["template"], s.get("prefer", []), fields))
    if len(stories) != 3:
        raise ConfigError(f"{brand_id}: exactly 3 stories are required, found {len(stories)}")
    return Content(raw.get("captions", {}), raw.get("fallback_captions", ["{alt}."]), stories)
