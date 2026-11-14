"""Layout engine: turns brand + slot data into a canvas description (shapes and text blocks).

This is plain data, so it can be unit-tested (safe zones, overflow, contrast) without
rendering. Jinja then draws a canvas as SVG without making any layout decisions.
"""
from __future__ import annotations

from dataclasses import dataclass

from . import colors, textfit
from .config import Brand

POST_W, POST_H = 1080, 1350
STORY_W, STORY_H = 1080, 1920
SAFE_TOP, SAFE_BOTTOM = 250, 1580   # Instagram overlays UI above and below this band in Stories
MARGIN = 80


@dataclass
class Block:
    id: str
    x: float
    y: float            # baseline of the first line
    size: int
    lh: float
    lines: list
    family: str
    weight: int
    fill: str
    anchor: str = "start"
    tracking: float = 0.0
    overflow: bool = False

    @property
    def lh_px(self) -> float:
        return round(self.size * self.lh, 2)

    @property
    def top(self) -> float:
        return self.y - self.size * 0.80

    @property
    def bottom(self) -> float:
        return self.y + (len(self.lines) - 1) * self.lh_px + self.size * 0.22

    def place_top(self, top: float) -> "Block":
        self.y = round(top + self.size * 0.80, 2)
        return self

    def place_bottom(self, bottom: float) -> "Block":
        self.y = round(bottom - self.size * 0.22 - (len(self.lines) - 1) * self.lh_px, 2)
        return self

    @property
    def width(self) -> float:
        return 0.0


def text_block(brand: Brand, role: str, text: str, *, id: str, x: float, max_w: float, max_lines: int,
               size: int, fill: str, min_size: int | None = None, lh: float = 1.15, anchor: str = "start",
               tracking: float = 0.0, balance: bool = False) -> Block:
    spec = brand.fonts[role]
    f = textfit.fit(text, spec.path, max_w=max_w, max_lines=max_lines, size=size, min_size=min_size,
                    tracking=tracking, balance=balance)
    return Block(id, x, 0.0, f.size, lh, f.lines, spec.family, spec.weight, fill, anchor, tracking, f.overflow)


def text_width(brand: Brand, role: str, text: str, size: int, tracking: float = 0.0) -> float:
    return textfit.measure(text, brand.fonts[role].path, size, tracking)


def arch_path(x: float, y: float, w: float, h: float) -> str:
    r = w / 2
    return f"M{x},{y + h} L{x},{y + r} A{r},{r} 0 0 1 {x + w},{y + r} L{x + w},{y + h} Z"


def canvas(kind: str, w: int, h: int, title: str, template: str) -> dict:
    return {"kind": kind, "w": w, "h": h, "title": title, "template": template, "defs": [], "items": [], "blocks": {}}


def add_text(c: dict, b: Block) -> Block:
    c["items"].append({"t": "text", "b": b})
    c["blocks"][b.id] = b
    return b


def lockup(c: dict, brand: Brand, *, x: float, baseline: float, size: int, fill: str, anchor: str = "start",
           id: str = "wordmark") -> None:
    """Brand mark + wordmark (live text), anchored left or centred on x."""
    s = round(size * 0.95)
    gap = round(size * 0.35)
    tw = text_width(brand, "display", brand.name, size)
    left = x if anchor == "start" else x - (s + gap + tw) / 2
    c["items"].append({"t": "mark", "shape": brand.mark, "x": round(left, 1), "y": round(baseline - s, 1),
                       "s": s, "fill": fill, "id": f"{id}-mark"})
    b = Block(id, round(left + s + gap, 1), baseline, size, 1.0, [brand.name], brand.fonts["display"].family,
              brand.fonts["display"].weight, fill)
    add_text(c, b)


def pill(c: dict, brand: Brand, *, id: str, text: str, x: float, top: float, h: int, bg: str, fg: str,
         size: int = 30, pad: int = 38, max_w: float = 920) -> tuple:
    """Rounded label with live text. Returns (right_edge, bottom)."""
    w = min(max_w, text_width(brand, "strong", text, size) + pad * 2)
    c["items"].append({"t": "rect", "id": f"{id}-bg", "x": x, "y": top, "w": round(w, 1), "h": h, "rx": h / 2, "fill": bg})
    b = text_block(brand, "strong", text, id=id, x=round(x + pad, 1), max_w=w - pad * 2, max_lines=1, size=size, fill=fg,
                   min_size=22)
    b.y = round(top + h / 2 + size * 0.35, 2)
    add_text(c, b)
    return x + w, top + h


# -- Instagram posts (1080 x 1350, 4:5) -----------------------------------------------------------

def post_canvas(brand: Brand, slot, info, href_fn, uid: str, n: int) -> dict:
    ink, paper = brand.color("ink"), brand.color("paper")
    title = f"{brand.name} post {n}: {info.alt}"
    c = canvas("post", POST_W, POST_H, title, slot.template)
    if slot.template == "arch":
        bg = brand.color(slot.bg)
        fg = colors.best_text(bg, [ink, paper])
        c["items"].append({"t": "rect", "id": "background", "x": 0, "y": 0, "w": POST_W, "h": POST_H, "rx": 0, "fill": bg})
        c["defs"].append({"t": "clip", "id": f"{uid}-arch", "d": arch_path(160, 100, 760, 940)})
        c["items"].append({"t": "image", "id": "photo", "x": 160, "y": 100, "w": 760, "h": 940,
                           "href": href_fn(info, 760, 940), "alt": info.alt, "clip": f"{uid}-arch"})
        cap = text_block(brand, "display", slot.caption, id="caption", x=POST_W / 2, max_w=800, max_lines=2, size=58,
                         min_size=38, lh=1.1, anchor="middle", fill=fg, balance=True).place_top(1098)
        add_text(c, cap)
        lockup(c, brand, x=POST_W / 2, baseline=1298, size=28, fill=fg, anchor="middle")
    else:
        c["items"].append({"t": "image", "id": "photo", "x": 0, "y": 0, "w": POST_W, "h": POST_H,
                           "href": href_fn(info, POST_W, POST_H), "alt": info.alt})
        c["defs"] += [{"t": "grad", "id": f"{uid}-scrim", "color": ink, "stops": [(0, 0), (1, 0.8)]},
                      {"t": "grad", "id": f"{uid}-top", "color": ink, "stops": [(0, 0.45), (1, 0)]}]
        c["items"] += [{"t": "rect", "id": "scrim", "x": 0, "y": 700, "w": POST_W, "h": 650, "rx": 0, "fill": f"url(#{uid}-scrim)"},
                       {"t": "rect", "id": "scrim-top", "x": 0, "y": 0, "w": POST_W, "h": 240, "rx": 0, "fill": f"url(#{uid}-top)"}]
        lockup(c, brand, x=MARGIN, baseline=120, size=34, fill=paper)
        cap = text_block(brand, "display", slot.caption, id="caption", x=MARGIN, max_w=800, max_lines=2, size=68,
                         min_size=42, lh=1.06, fill=paper, balance=True).place_bottom(POST_H - 90)
        add_text(c, cap)
    return c


# -- Instagram stories (1080 x 1920, 9:16) --------------------------------------------------------

def story_canvas(brand: Brand, slot, info, href_fn, uid: str, n: int) -> dict:
    f = slot.fields
    ink, paper, primary, accent = (brand.color(k) for k in ("ink", "paper", "primary", "accent"))
    c = canvas("story", STORY_W, STORY_H, f"{brand.name} story {n}: {info.alt}", slot.template)
    if slot.template == "hero":
        _hero(c, brand, f, info, href_fn, uid, ink, paper, accent)
    elif slot.template == "quote":
        _quote(c, brand, f, info, href_fn, uid, ink, paper, primary, accent)
    else:
        _offer(c, brand, f, info, href_fn, ink, paper, primary, accent)
    return c


def _hero(c, brand, f, info, href_fn, uid, ink, paper, accent):
    c["items"].append({"t": "image", "id": "photo", "x": 0, "y": 0, "w": STORY_W, "h": STORY_H,
                       "href": href_fn(info, STORY_W, STORY_H), "alt": info.alt})
    c["defs"] += [{"t": "grad", "id": f"{uid}-top", "color": ink, "stops": [(0, 0.5), (1, 0)]},
                  {"t": "grad", "id": f"{uid}-bot", "color": ink, "stops": [(0, 0), (0.45, 0.55), (1, 0.9)]}]
    c["items"] += [{"t": "rect", "id": "scrim-top", "x": 0, "y": 0, "w": STORY_W, "h": 460, "rx": 0, "fill": f"url(#{uid}-top)"},
                   {"t": "rect", "id": "scrim-bottom", "x": 0, "y": 620, "w": STORY_W, "h": 1300, "rx": 0,
                    "fill": f"url(#{uid}-bot)"}]
    lockup(c, brand, x=MARGIN, baseline=322, size=40, fill=paper)
    cta_top = SAFE_BOTTOM - 100
    cta_text = f.get("cta", "")
    cta_w = min(920, text_width(brand, "strong", cta_text, 36) + 96)
    c["items"].append({"t": "rect", "id": "cta-bg", "x": MARGIN, "y": cta_top, "w": round(cta_w, 1), "h": 100, "rx": 50, "fill": accent})
    cta = text_block(brand, "strong", cta_text, id="cta", x=MARGIN + 48, max_w=cta_w - 96, max_lines=1, size=36, fill=ink)
    cta.y = cta_top + 50 + 36 * 0.35
    add_text(c, cta)
    body = text_block(brand, "body", f.get("body", ""), id="body", x=MARGIN, max_w=840, max_lines=3, size=42, min_size=32,
                      lh=1.35, fill=paper).place_bottom(cta_top - 56)
    head = text_block(brand, "display", f.get("headline", ""), id="headline", x=MARGIN, max_w=920, max_lines=4, size=132,
                      min_size=72, lh=1.03, fill=paper, balance=True).place_bottom(body.top - 40)
    kick_h = 68
    pill(c, brand, id="kicker", text=f.get("kicker", ""), x=MARGIN, top=head.top - 40 - kick_h, h=kick_h, bg=accent, fg=ink, size=30)
    add_text(c, head)
    add_text(c, body)


def _quote(c, brand, f, info, href_fn, uid, ink, paper, primary, accent):
    fg = colors.best_text(primary, [paper, ink])
    c["items"].append({"t": "rect", "id": "background", "x": 0, "y": 0, "w": STORY_W, "h": STORY_H, "rx": 0, "fill": primary})
    c["defs"].append({"t": "clip", "id": f"{uid}-arch", "d": arch_path(170, 280, 740, 740)})
    c["items"].append({"t": "image", "id": "photo", "x": 170, "y": 280, "w": 740, "h": 740,
                       "href": href_fn(info, 740, 740), "alt": info.alt, "clip": f"{uid}-arch"})
    quote = text_block(brand, "display", f.get("quote", ""), id="quote", x=STORY_W / 2, max_w=840, max_lines=4, size=76,
                       min_size=44, lh=1.14, anchor="middle", fill=fg, balance=True).place_top(1090)
    add_text(c, quote)
    sub = accent if colors.contrast(accent, primary) >= 4.5 else fg
    attr = text_block(brand, "body", f.get("attribution", ""), id="attribution", x=STORY_W / 2, max_w=800, max_lines=1,
                      size=36, min_size=26, anchor="middle", fill=sub).place_top(quote.bottom + 36)
    add_text(c, attr)
    lockup(c, brand, x=STORY_W / 2, baseline=SAFE_BOTTOM - 20, size=32, fill=fg, anchor="middle")


def _offer(c, brand, f, info, href_fn, ink, paper, primary, accent):
    c["items"].append({"t": "rect", "id": "background", "x": 0, "y": 0, "w": STORY_W, "h": STORY_H, "rx": 0, "fill": paper})
    c["items"].append({"t": "image", "id": "photo", "x": 0, "y": 0, "w": STORY_W, "h": 920,
                       "href": href_fn(info, STORY_W, 920), "alt": info.alt})
    c["items"].append({"t": "rect", "id": "card", "x": 0, "y": 860, "w": STORY_W, "h": 1100, "rx": 64, "fill": paper})
    pill(c, brand, id="kicker", text=f.get("kicker", ""), x=MARGIN, top=826, h=68, bg=accent, fg=ink, size=30)
    title = text_block(brand, "display", f.get("title", ""), id="title", x=MARGIN, max_w=920, max_lines=2, size=104,
                       min_size=60, lh=1.04, fill=ink, balance=True).place_top(960)
    add_text(c, title)
    y = title.bottom + 52
    for i, line in enumerate(f.get("details", [])[:3]):
        b = text_block(brand, "body", line, id=f"detail-{i + 1}", x=MARGIN + 44, max_w=820, max_lines=1, size=38,
                       min_size=28, fill=ink)
        b.y = round(y + 38 * 0.8, 2)
        c["items"].append({"t": "circle", "id": f"bullet-{i + 1}", "cx": MARGIN + 12, "cy": round(y + 38 * 0.5, 1), "r": 10, "fill": primary})
        add_text(c, b)
        y += 62
    cta_top = SAFE_BOTTOM - 100
    cta_text = f.get("cta", "")
    cta_w = min(920, text_width(brand, "strong", cta_text, 36) + 96)
    c["items"].append({"t": "rect", "id": "cta-bg", "x": MARGIN, "y": cta_top, "w": round(cta_w, 1), "h": 100, "rx": 50, "fill": ink})
    cta = text_block(brand, "strong", cta_text, id="cta", x=MARGIN + 48, max_w=cta_w - 96, max_lines=1, size=36,
                     fill=colors.best_text(ink, [paper, accent]))
    cta.y = cta_top + 50 + 36 * 0.35
    add_text(c, cta)
