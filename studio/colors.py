"""Colour maths: WCAG contrast, CIE Lab and perceptual distance."""
from __future__ import annotations

import numpy as np


def hex_to_rgb(value: str) -> tuple:
    value = value.lstrip("#")
    return tuple(int(value[i:i + 2], 16) for i in (0, 2, 4))


def rgb_to_hex(rgb) -> str:
    return "#%02X%02X%02X" % tuple(int(round(v)) for v in rgb)


def _linear(c):
    c = np.asarray(c, dtype=float) / 255.0
    return np.where(c <= 0.04045, c / 12.92, ((c + 0.055) / 1.055) ** 2.4)


def luminance(rgb) -> float:
    r, g, b = _linear(rgb)
    return float(0.2126 * r + 0.7152 * g + 0.0722 * b)


def contrast(a: str, b: str) -> float:
    la, lb = luminance(hex_to_rgb(a)), luminance(hex_to_rgb(b))
    hi, lo = max(la, lb), min(la, lb)
    return (hi + 0.05) / (lo + 0.05)


def best_text(bg: str, candidates) -> str:
    """Return the candidate colour with the highest WCAG contrast against bg."""
    return max(candidates, key=lambda c: contrast(bg, c))


_M = np.array([[0.4124564, 0.3575761, 0.1804375],
               [0.2126729, 0.7151522, 0.0721750],
               [0.0193339, 0.1191920, 0.9503041]])
_WHITE = np.array([0.95047, 1.0, 1.08883])


def rgb_to_lab(rgb) -> np.ndarray:
    """(N,3) sRGB 0-255 -> (N,3) CIE Lab."""
    xyz = (_linear(np.atleast_2d(rgb)) @ _M.T) / _WHITE
    f = np.where(xyz > 0.008856, np.cbrt(xyz), 7.787 * xyz + 16 / 116)
    return np.stack([116 * f[:, 1] - 16, 500 * (f[:, 0] - f[:, 1]), 200 * (f[:, 1] - f[:, 2])], axis=1)


def delta_e(a, b) -> float:
    return float(np.linalg.norm(np.asarray(a, dtype=float) - np.asarray(b, dtype=float)))
