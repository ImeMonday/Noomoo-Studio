"""Image analysis (colour, light, texture), smart cropping and embedding."""
from __future__ import annotations

import base64
import io
import json
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

import numpy as np
from PIL import Image, ImageOps

from . import colors
from .config import IMAGES_DIR


@dataclass
class ImageInfo:
    id: str
    path: Path
    category: str
    alt: str
    tags: list
    focal: tuple
    license: str
    dominant: tuple      # (r, g, b)
    lab: tuple           # CIE Lab of the dominant colour
    lightness: float     # mean L*, 0-100
    chroma: float        # mean colourfulness
    edge: float          # mean gradient energy (detail)
    size: tuple


def _saliency_focal(lum: np.ndarray) -> tuple:
    gy, gx = np.gradient(lum)
    g = np.hypot(gx, gy)
    g = np.where(g >= np.percentile(g, 75), g, 0)
    if g.sum() == 0:
        return (0.5, 0.5)
    ys, xs = np.mgrid[0:g.shape[0], 0:g.shape[1]]
    cx = float((g * xs).sum() / g.sum()) / g.shape[1]
    cy = float((g * ys).sum() / g.sum()) / g.shape[0]
    return (min(max(cx, 0.3), 0.7), min(max(cy, 0.3), 0.7))


@lru_cache(maxsize=512)
def _analyze(path: str, mtime: int, meta_json: str) -> ImageInfo:
    meta = json.loads(meta_json)
    with Image.open(path) as im:
        im = ImageOps.exif_transpose(im).convert("RGB")
        size = im.size
        small = im.copy()
    small.thumbnail((96, 120))
    q = small.quantize(colors=5, method=Image.Quantize.MEDIANCUT)
    used = q.getcolors()                                     # [(pixel_count, palette_index)]
    raw = np.array(q.getpalette(), dtype=float).reshape(-1, 3)
    pal = raw[[i for _, i in used]]
    cnt = np.array([c for c, _ in used], dtype=float)
    lab_pal = colors.rgb_to_lab(pal)
    chroma_pal = np.hypot(lab_pal[:, 1], lab_pal[:, 2])
    weight = cnt * (1 + chroma_pal / 40)
    dom = pal[int(np.argmax(weight))]   # most prominent, colourful cluster
    tiny = np.asarray(small.resize((48, 60)), dtype=float)
    lab = colors.rgb_to_lab(tiny.reshape(-1, 3))
    lum = lab[:, 0].reshape(60, 48)
    gy, gx = np.gradient(lum)
    focal = tuple(meta["focal"]) if "focal" in meta else _saliency_focal(lum)
    return ImageInfo(
        id=meta["id"], path=Path(path), category=meta.get("category", "upload"),
        alt=meta.get("alt", meta["id"]), tags=list(meta.get("tags", [])), focal=focal,
        license=meta.get("license", "user supplied"),
        dominant=tuple(int(round(v)) for v in dom),
        lab=tuple(float(v) for v in colors.rgb_to_lab(dom)[0]),
        lightness=float(lum.mean()), chroma=float(np.hypot(lab[:, 1], lab[:, 2]).mean()),
        edge=float(np.hypot(gx, gy).mean()), size=size)


def analyze(path: Path, meta: dict) -> ImageInfo:
    return _analyze(str(path), path.stat().st_mtime_ns, json.dumps(meta, sort_keys=True))


def load_library(uploads_dir: Path | None = None) -> dict:
    """Bundled images plus any user uploads, keyed by image id."""
    lib = {}
    sources = [(IMAGES_DIR, IMAGES_DIR / "manifest.json")]
    if uploads_dir is not None:
        sources.append((uploads_dir, uploads_dir / "manifest.json"))
    for folder, manifest in sources:
        if manifest.exists():
            for meta in json.loads(manifest.read_text(encoding="utf-8")):
                lib[meta["id"]] = analyze(folder / meta["file"], meta)
    return lib


def crop_to(im: Image.Image, w: int, h: int, focal) -> Image.Image:
    """Largest crop with aspect w:h centred on the focal point, resized to w x h."""
    sw, sh = im.size
    target = w / h
    cw, ch = (int(round(sh * target)), sh) if sw / sh > target else (sw, int(round(sw / target)))
    x = min(max(focal[0] * sw - cw / 2, 0), sw - cw)
    y = min(max(focal[1] * sh - ch / 2, 0), sh - ch)
    return im.crop((int(x), int(y), int(x) + cw, int(y) + ch)).resize((w, h), Image.LANCZOS)


@lru_cache(maxsize=256)
def _data_uri(path: str, mtime: int, w: int, h: int, fx: float, fy: float, quality: int) -> str:
    with Image.open(path) as im:
        out = crop_to(ImageOps.exif_transpose(im).convert("RGB"), w, h, (fx, fy))
    buf = io.BytesIO()
    out.save(buf, "JPEG", quality=quality, optimize=True)
    return "data:image/jpeg;base64," + base64.b64encode(buf.getvalue()).decode("ascii")


def data_uri(info: ImageInfo, w: int, h: int, quality: int = 80) -> str:
    """Focal-point crop of the image, embedded as a base64 JPEG data URI."""
    return _data_uri(str(info.path), info.path.stat().st_mtime_ns, w, h,
                     round(info.focal[0], 3), round(info.focal[1], 3), quality)
