"""Export a project: PNGs, editable SVG sources, HTML contact sheet, manifest, credits, zip."""
from __future__ import annotations

import hashlib
import io
import json
import shutil
import zipfile
from pathlib import Path

from jinja2 import Environment, FileSystemLoader
from PIL import Image

from . import __version__, layout, render
from .config import FONTS_DIR, ROOT
from .project import Project

ZIP_DATE = (2026, 1, 1, 0, 0, 0)   # fixed so archives are byte-identical across runs


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _grid_preview(png_posts: list) -> bytes:
    """3x3 contact sheet using Instagram's 3:4 grid crop (centre of each 4:5 post)."""
    tw, th = 360, 480
    sheet = Image.new("RGB", (tw * 3 + 8, th * 3 + 8), "#111111")
    for n, data in enumerate(png_posts):
        im = Image.open(io.BytesIO(data)).convert("RGB")
        crop_w = int(im.height * 3 / 4)
        left = (im.width - crop_w) // 2
        tile = im.crop((left, 0, left + crop_w, im.height)).resize((tw, th), Image.LANCZOS)
        sheet.paste(tile, (4 + (n % 3) * tw, 4 + (n // 3) * th))
    buf = io.BytesIO()
    sheet.save(buf, "PNG", compress_level=3)
    return buf.getvalue()


def export(project: Project, out_root: Path) -> Path:
    """Write the full deliverable bundle to out_root/<brand>/ and a zip next to it. Returns the zip path."""
    brand = project.brand
    root = out_root / brand.id
    if root.exists():
        shutil.rmtree(root)
    for sub in ("png/posts", "png/stories", "source/svg/posts", "source/svg/stories", "source/fonts"):
        (root / sub).mkdir(parents=True)

    files, png_posts, hashes = {}, [], {}
    for i in range(9):
        name = f"post-{i + 1:02d}"
        canvas = project.post_canvas(i)
        svg = render.to_svg(canvas, brand, font_base="../../fonts/")
        png = render.to_png(svg, layout.POST_W, layout.POST_H)
        (root / f"source/svg/posts/{name}.svg").write_text(svg, encoding="utf-8")
        (root / f"png/posts/{name}.png").write_bytes(png)
        png_posts.append(png)
        hashes[f"png/posts/{name}.png"] = _sha(png)
    for i in range(3):
        name = f"story-{i + 1:02d}"
        svg = render.to_svg(project.story_canvas(i), brand, font_base="../../fonts/")
        png = render.to_png(svg, layout.STORY_W, layout.STORY_H)
        (root / f"source/svg/stories/{name}.svg").write_text(svg, encoding="utf-8")
        (root / f"png/stories/{name}.png").write_bytes(png)
        hashes[f"png/stories/{name}.png"] = _sha(png)
    preview = _grid_preview(png_posts)
    (root / "png/grid-preview.png").write_bytes(preview)
    hashes["png/grid-preview.png"] = _sha(preview)

    for spec in render.font_faces(brand):
        shutil.copy(spec.path, root / "source/fonts" / spec.file)
    for lic in FONTS_DIR.glob("OFL-*.txt"):
        shutil.copy(lic, root / "source/fonts" / lic.name)

    env = Environment(loader=FileSystemLoader(str(ROOT / "templates")), autoescape=False)
    html = env.get_template("preview.html.j2").render(
        brand=brand, p=brand.palette,
        posts=[render.to_svg(project.post_canvas(i, 0.5), brand, "source/fonts/") for i in range(9)],
        stories=[render.to_svg(project.story_canvas(i, 0.5), brand, "source/fonts/") for i in range(3)])
    (root / "preview.html").write_text(html, encoding="utf-8")
    (root / "source/README.txt").write_text(
        "Editable sources\n================\n"
        "Every .svg here is a self-contained, layered file: live <text>, named layers (photo, headline, cta...),\n"
        "images embedded as base64. Open in a browser, Inkscape, Illustrator or Figma (install the fonts in\n"
        "source/fonts first). Regenerate everything from config with:  python -m studio build\n", encoding="utf-8")

    used = {s.image_id for s in project.posts + project.stories}
    credits = [f"# Credits - {brand.name}", "", "All brands, copy and images are fictional or synthetic.", "", "## Images"]
    credits += [f"- `{i}` - {project.library[i].license}" for i in sorted(used)]
    credits += ["", "## Fonts (SIL Open Font License 1.1, see source/fonts/OFL-*.txt)"]
    credits += [f"- {s.family} ({s.file})" for s in render.font_faces(brand)]
    (root / "CREDITS.md").write_text("\n".join(credits) + "\n", encoding="utf-8")

    manifest = {
        "tool": "noomoo-studio", "version": __version__, "brand": brand.id, "brand_name": brand.name,
        "ai": {"provider": project.ai.provider, "model": project.ai.model} if project.ai.enabled else "off (deterministic copy)",
        "posts": [{"n": i + 1, "image": p.image_id, "template": p.template, "caption": p.caption,
                   "png": f"png/posts/post-{i + 1:02d}.png", "svg": f"source/svg/posts/post-{i + 1:02d}.svg"}
                  for i, p in enumerate(project.posts)],
        "stories": [{"n": i + 1, "image": s.image_id, "template": s.template, "fields": s.fields,
                     "png": f"png/stories/story-{i + 1:02d}.png", "svg": f"source/svg/stories/story-{i + 1:02d}.svg"}
                    for i, s in enumerate(project.stories)],
        "sha256": hashes,
    }
    (root / "manifest.json").write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
    (root / "grid_report.json").write_text(json.dumps(project.report, indent=2), encoding="utf-8")

    zip_path = out_root / f"{brand.id}-assets.zip"
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for path in sorted(p for p in root.rglob("*") if p.is_file()):
            info = zipfile.ZipInfo(f"{brand.id}/{path.relative_to(root).as_posix()}", ZIP_DATE)
            info.compress_type = zipfile.ZIP_DEFLATED
            zf.writestr(info, path.read_bytes())
    return zip_path
