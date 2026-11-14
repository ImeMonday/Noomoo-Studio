import xml.etree.ElementTree as ET

import pytest

from studio import colors, layout, render, textfit

NS = {"svg": "http://www.w3.org/2000/svg"}


def all_canvases(project):
    return [project.post_canvas(i) for i in range(9)] + [project.story_canvas(i) for i in range(3)]


def test_no_text_overflows_its_box(project):
    for c in all_canvases(project):
        for b in c["blocks"].values():
            assert not b.overflow, f"{c['title']}: {b.id} overflowed"


def test_story_text_stays_inside_instagram_safe_zone(project):
    for i in range(3):
        c = project.story_canvas(i)
        for b in c["blocks"].values():
            assert b.top >= layout.SAFE_TOP, f"{b.id} too high ({b.top})"
            assert b.bottom <= layout.SAFE_BOTTOM + 30, f"{b.id} too low ({b.bottom})"


def test_text_fits_horizontally(project):
    for c in all_canvases(project):
        for b in c["blocks"].values():
            if b.id.startswith("wordmark"):
                continue
            spec = next(s for s in project.brand.fonts.values() if s.family == b.family and s.weight == b.weight)
            for line in b.lines:
                assert textfit.measure(line, spec.path, b.size, b.tracking) <= c["w"] - 2 * 60


def test_contrast_on_solid_backgrounds(project):
    for i, post in enumerate(project.posts):
        if post.template != "arch":
            continue
        c = project.post_canvas(i)
        bg = next(it["fill"] for it in c["items"] if it["id"] == "background")
        assert colors.contrast(c["blocks"]["caption"].fill, bg) >= 4.5
    quote = project.story_canvas(1)
    bg = next(it["fill"] for it in quote["items"] if it["id"] == "background")
    assert all(colors.contrast(b.fill, bg) >= 4.5 for b in quote["blocks"].values() if b.id != "attribution")
    offer = project.story_canvas(2)
    assert colors.contrast(offer["blocks"]["title"].fill, project.brand.color("paper")) >= 4.5


def test_svg_is_valid_xml_with_live_editable_text(project):
    svg = project.story_svg(0)
    root = ET.fromstring(svg)
    texts = {t.get("id"): " ".join("".join(ts.itertext()) for ts in t.findall("svg:tspan", NS))
             for t in root.iter("{http://www.w3.org/2000/svg}text")}
    assert texts["headline"] == project.stories[0].fields["headline"]
    assert texts["cta"] == project.stories[0].fields["cta"]
    assert root.get("viewBox") == "0 0 1080 1920"
    assert "<image" in svg and "base64" in svg


def test_every_svg_uses_only_bundled_fonts(project):
    for i in range(3):
        root = ET.fromstring(project.story_svg(i))
        families = {t.get("font-family") for t in root.iter("{http://www.w3.org/2000/svg}text")}
        assert families <= {s.family for s in project.brand.fonts.values()}


def test_fit_shrinks_long_copy_instead_of_overflowing(project):
    spec = project.brand.fonts["display"]
    short = textfit.fit("Short", spec.path, max_w=900, max_lines=2, size=120)
    long = textfit.fit("A considerably longer headline that needs to wrap onto several lines " * 2, spec.path,
                       max_w=900, max_lines=2, size=120)
    assert short.size == 120 and not short.overflow
    assert long.size < 120 or long.overflow


def test_png_dimensions_and_render(project):
    from PIL import Image
    import io
    png = render.to_png(project.post_svg(0), layout.POST_W, layout.POST_H)
    assert Image.open(io.BytesIO(png)).size == (1080, 1350)
