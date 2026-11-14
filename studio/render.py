"""SVG rendering (Jinja2) and PNG rasterisation (resvg)."""
from __future__ import annotations

import resvg_py
from jinja2 import Environment, FileSystemLoader, StrictUndefined

from .config import FONTS_DIR, ROOT, Brand

_ENV = Environment(loader=FileSystemLoader(str(ROOT / "templates")), autoescape=True, trim_blocks=True,
                   lstrip_blocks=True, undefined=StrictUndefined)


def font_faces(brand: Brand) -> list:
    seen, out = set(), []
    for spec in brand.fonts.values():
        if spec.file not in seen:
            seen.add(spec.file)
            out.append(spec)
    return out


def to_svg(canvas: dict, brand: Brand, font_base: str = "fonts/") -> str:
    """Render a canvas to a standalone SVG. `font_base` is where @font-face URLs point."""
    xml = _ENV.get_template("canvas.svg.j2").render(c=canvas, fonts=font_faces(brand), font_base=font_base)
    return "\n".join(line for line in xml.splitlines() if line.strip()) + "\n"


def to_png(svg: str, width: int, height: int) -> bytes:
    """Rasterise with resvg using only the bundled fonts (identical output on every machine)."""
    return bytes(resvg_py.svg_to_bytes(svg_string=svg, width=width, height=height,
                                       font_dirs=[str(FONTS_DIR)], skip_system_fonts=True))
