"""Real font metrics for SVG text: wrapping and fit-to-box.

SVG has no automatic line wrapping, so every headline is measured with the actual
font file (Pillow) and emitted as explicit <tspan> lines. The text stays live and
editable; only the line breaks are computed.
"""
from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache

from PIL import ImageFont


@lru_cache(maxsize=256)
def _font(path: str, size: int) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(path, size)


def measure(text: str, path, size: float, tracking: float = 0.0) -> float:
    return _font(str(path), max(1, int(round(size)))).getlength(text) + tracking * len(text)


def wrap(text: str, path, size: float, max_w: float, tracking: float = 0.0) -> list:
    lines, current = [], ""
    for word in text.split():
        trial = f"{current} {word}".strip()
        if current and measure(trial, path, size, tracking) > max_w:
            lines.append(current)
            current = word
        else:
            current = trial
    if current:
        lines.append(current)
    return lines


def _balanced(text, path, size, max_w, tracking):
    """Shrink the wrap width while the line count stays the same (avoids orphans)."""
    base = wrap(text, path, size, max_w, tracking)
    best = base
    if len(base) > 1:
        w = max_w
        while w > max_w * 0.55:
            w -= 8
            trial = wrap(text, path, size, w, tracking)
            if len(trial) > len(base):
                break
            best = trial
    return best


@dataclass
class Fit:
    size: int
    lines: list
    overflow: bool


def fit(text, path, *, max_w, max_lines, size, min_size=None, tracking=0.0, balance=False) -> Fit:
    """Largest font size (stepping by 2) at which the text fits max_lines x max_w."""
    min_size = min_size or max(12, int(size * 0.6))
    s = int(size)
    while s >= min_size:
        lines = (_balanced if balance else wrap)(text, path, s, max_w, tracking)
        if len(lines) <= max_lines and all(measure(l, path, s, tracking) <= max_w for l in lines):
            return Fit(s, lines, False)
        s -= 2
    lines = wrap(text, path, min_size, max_w, tracking)[:max_lines]
    return Fit(min_size, lines, True)
