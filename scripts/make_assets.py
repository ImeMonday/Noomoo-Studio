"""Generate the 14 self-created, procedurally drawn hospitality images + manifest.

Every image is an SVG scene rendered with resvg and finished with film grain, so the
asset set is fully original (CC0) and reproducible: `python scripts/make_assets.py`.
"""
from __future__ import annotations

import io
import json
import math
import random
from pathlib import Path

import numpy as np
import resvg_py
from PIL import Image

W, H = 1600, 2000
OUT = Path(__file__).resolve().parent.parent / "assets" / "images"


def arch(x, y, w, h):
    r = w / 2
    return f"M{x},{y + h} L{x},{y + r} A{r},{r} 0 0 1 {x + w},{y + r} L{x + w},{y + h} Z"


def lin(i, stops, vertical=True):
    s = "".join(f'<stop offset="{o}" stop-color="{c}"/>' for o, c in stops)
    a = 'x1="0" y1="0" x2="0" y2="1"' if vertical else 'x1="0" y1="0" x2="1" y2="0"'
    return f'<linearGradient id="{i}" {a}>{s}</linearGradient>'


def rad(i, c, a0=1.0, a1=0.0):
    return (f'<radialGradient id="{i}"><stop offset="0" stop-color="{c}" stop-opacity="{a0}"/>'
            f'<stop offset="1" stop-color="{c}" stop-opacity="{a1}"/></radialGradient>')


def palm(cx, cy, n, length, col, rng, op=1.0, spread=150):
    out = []
    for k in range(n):
        a = -spread / 2 + spread * k / max(n - 1, 1) + rng.uniform(-6, 6)
        out.append(f'<ellipse cx="{cx}" cy="{cy - length / 2}" rx="{length * 0.07}" ry="{length / 2}" '
                   f'fill="{col}" opacity="{op}" transform="rotate({a} {cx} {cy})"/>')
    return "".join(out)


def s_facade(r):
    d = lin("sky", [(0, "#f6c1a0"), (.45, "#f29aa6"), (1, "#8f7bb8")]) + rad("sun", "#fff1c9")
    b = f'<rect width="{W}" height="{H}" fill="url(#sky)"/><circle cx="1150" cy="620" r="520" fill="url(#sun)"/>'
    b += '<circle cx="1150" cy="620" r="150" fill="#fff4d6"/>'
    b += '<rect x="170" y="760" width="1260" height="1240" fill="#f5e6d3"/><rect x="170" y="730" width="1260" height="50" fill="#e8d2b8"/>'
    for row in range(3):
        for c in range(5):
            x, y = 250 + c * 240, 880 + row * 320
            b += f'<path d="{arch(x, y, 140, 230)}" fill="#6f4a73"/><path d="{arch(x + 14, y + 14, 112, 200)}" fill="{"#ffd58a" if (row + c) % 3 == 0 else "#7e5a86"}"/>'
    b += palm(300, 1000, 9, 520, "#2c2145", r, .95) + palm(1380, 1100, 8, 440, "#2c2145", r, .95)
    return d, b, "#2c2145"


def s_pool(r):
    d = lin("w", [(0, "#5ee0d6"), (1, "#0a8fa3")]) + lin("wall", [(0, "#fdf3e7"), (1, "#f4d9bd")])
    b = f'<rect width="{W}" height="{H}" fill="url(#wall)"/>'
    for c in range(4):
        b += f'<path d="{arch(110 + c * 370, 260, 300, 620)}" fill="#bfe9e5"/>'
    b += f'<rect y="940" width="{W}" height="1060" fill="url(#w)"/>'
    for i in range(14):
        y = 1030 + i * 68
        b += f'<path d="M0,{y} Q200,{y - 26} 400,{y} T800,{y} T1200,{y} T1600,{y}" stroke="#d9fffb" stroke-width="5" fill="none" opacity=".55"/>'
    b += '<rect y="900" width="1600" height="60" fill="#fff"/>'
    for x in (180, 640):
        b += f'<rect x="{x}" y="1500" width="460" height="46" rx="20" fill="#fff"/><rect x="{x}" y="1440" width="120" height="110" rx="30" fill="#ffd0c2"/>'
    b += '<rect x="1250" y="560" width="14" height="420" fill="#fff"/><path d="M1060,560 Q1257,420 1454,560 Z" fill="#ff7f66"/><path d="M1158,500 Q1257,420 1356,520 L1257,560Z" fill="#fff" opacity=".9"/>'
    return d, b, "#0a8fa3"


def s_breakfast(r):
    d = lin("t", [(0, "#f9f1e4"), (1, "#eadcc4")])
    b = f'<rect width="{W}" height="{H}" fill="url(#t)"/>'
    for i in range(0, 2000, 100):
        b += f'<rect y="{i}" width="{W}" height="50" fill="#fff" opacity=".35"/>'
    b += '<circle cx="640" cy="760" r="430" fill="#fff"/><circle cx="640" cy="760" r="340" fill="#f2ece2"/>'
    b += '<path d="M430,800 Q520,540 700,600 Q820,660 840,780 Q700,720 600,860 Q500,900 430,800Z" fill="#d89a4a"/><path d="M520,740 Q640,650 760,720" stroke="#b97a2d" stroke-width="10" fill="none"/>'
    for i, (x, y) in enumerate([(1180, 560), (1260, 780), (1090, 800)]):
        b += f'<circle cx="{x}" cy="{y}" r="150" fill="#ff9d2e"/><circle cx="{x}" cy="{y}" r="122" fill="#ffc15e"/>'
        for a in range(0, 360, 45):
            b += f'<line x1="{x}" y1="{y}" x2="{x + 122 * math.cos(math.radians(a))}" y2="{y + 122 * math.sin(math.radians(a))}" stroke="#ff9d2e" stroke-width="7"/>'
    b += '<circle cx="520" cy="1480" r="300" fill="#fff"/><circle cx="520" cy="1480" r="210" fill="#4a2c1c"/><circle cx="520" cy="1480" r="190" fill="#7a4a2b"/><path d="M800,1420 q130,0 130,70 t-130,70" stroke="#fff" stroke-width="40" fill="none"/>'
    b += '<rect x="1000" y="1250" width="330" height="520" rx="60" fill="#e7f1f0"/><rect x="1000" y="1250" width="330" height="140" rx="60" fill="#cfe3e1"/>'
    return d, b, "#7a4a2b"


def s_room(r):
    d = lin("wall", [(0, "#e8eef5"), (1, "#c9d6e6")]) + lin("sk", [(0, "#9fd0f5"), (1, "#e6f4ff")])
    b = f'<rect width="{W}" height="{H}" fill="url(#wall)"/><path d="{arch(1000, 240, 440, 760)}" fill="url(#sk)"/>'
    b += '<path d="M1220,240 V1000 M1000,640 H1440" stroke="#fff" stroke-width="14"/>'
    b += '<rect y="1400" width="1600" height="600" fill="#b8996f"/><rect x="120" y="860" width="1050" height="420" rx="40" fill="#2d4a6b"/>'
    b += '<rect x="120" y="1150" width="1250" height="480" rx="50" fill="#fff"/><rect x="120" y="1150" width="1250" height="120" rx="40" fill="#dbe7f3"/>'
    for x in (200, 560):
        b += f'<rect x="{x}" y="1010" width="320" height="200" rx="60" fill="#f4f8fc"/>'
    b += '<rect x="1380" y="1000" width="22" height="420" fill="#222"/><path d="M1300,1000 L1480,1000 L1440,860 L1340,860Z" fill="#ffd27a"/>'
    b += '<ellipse cx="820" cy="1750" rx="520" ry="120" fill="#c8553d" opacity=".9"/>'
    return d, b, "#2d4a6b"


def s_lobby(r):
    d = lin("f", [(0, "#d7c3a5"), (1, "#8d7456")])
    b = '<rect width="1600" height="2000" fill="#f2e6d2"/>'
    cols = ["#f5ead6", "#e9d6b5", "#d9bd90", "#c8a26b", "#b5894c", "#9c6f36", "#7c5524"]
    for i in range(7):
        w, h = 1300 - i * 170, 1750 - i * 230
        x, y = 800 - w / 2, 120 + i * 120
        b += f'<path d="{arch(x, y, w, h)}" fill="{cols[i]}"/>'
    b += '<path d="M0,2000 L560,1280 H1040 L1600,2000Z" fill="url(#f)"/>'
    for i in range(6):
        b += f'<line x1="{800 + (i - 2.5) * 80}" y1="1280" x2="{800 + (i - 2.5) * 330}" y2="2000" stroke="#6e5438" stroke-width="4" opacity=".5"/>'
    b += '<circle cx="800" cy="520" r="90" fill="#fff6d6" opacity=".95"/>'
    return d, b, "#7c5524"


def s_terrace(r):
    d = lin("s", [(0, "#0d1b4c"), (.55, "#4a3f8f"), (1, "#f08a6c")]) + rad("g", "#ffd9a0", .9)
    b = f'<rect width="{W}" height="{H}" fill="url(#s)"/><rect y="1040" width="1600" height="420" fill="#1a2a6b"/>'
    b += '<rect y="1040" width="1600" height="6" fill="#ffb98a"/>'
    for i in range(7):
        b += f'<rect x="{200 + i * 190}" y="1180" width="120" height="6" fill="#ffb98a" opacity=".4"/>'
    b += '<path d="M0,260 Q400,520 800,300 T1600,320" stroke="#2a1f45" stroke-width="6" fill="none"/>'
    for i in range(16):
        x = i * 106
        y = 280 + 160 * math.sin(i / 15 * math.pi) * (0.7 if i % 2 else 1) + 30
        b += f'<circle cx="{x}" cy="{y}" r="60" fill="url(#g)"/><circle cx="{x}" cy="{y}" r="14" fill="#fff3cf"/>'
    b += '<rect y="1460" width="1600" height="540" fill="#241838"/><ellipse cx="800" cy="1620" rx="520" ry="90" fill="#3a2a5a"/>'
    b += '<rect x="780" y="1520" width="40" height="110" fill="#f4e8d0"/><ellipse cx="800" cy="1500" rx="26" ry="60" fill="#ffd27a"/><circle cx="800" cy="1500" r="200" fill="url(#g)"/>'
    return d, b, "#ffd9a0"


def s_cocktail(r):
    d = rad("b1", "#ff9d5c", .8) + rad("b2", "#ff5c8a", .7) + lin("bg", [(0, "#1a0f22"), (1, "#3a1530")])
    b = f'<rect width="{W}" height="{H}" fill="url(#bg)"/>'
    for i in range(14):
        b += f'<circle cx="{r.randint(60, 1540)}" cy="{r.randint(60, 900)}" r="{r.randint(50, 150)}" fill="url(#b{1 + i % 2})"/>'
    b += '<path d="M430,760 H1170 L800,1240 Z" fill="#ffb067" opacity=".95"/><path d="M430,760 H1170 L1100,860 H500Z" fill="#ffd9a8"/>'
    b += '<path d="M400,730 H1200 L820,1260 V1620 H1000 V1680 H600 V1620 H780 V1260 Z" fill="none" stroke="#fff" stroke-width="12" opacity=".9"/>'
    b += '<circle cx="1120" cy="700" r="120" fill="#ffd23f"/><circle cx="1120" cy="700" r="92" fill="#ffe680"/>'
    b += '<rect y="1690" width="1600" height="310" fill="#0d0713"/><rect y="1690" width="1600" height="8" fill="#ff9d5c" opacity=".7"/>'
    return d, b, "#ffb067"


def s_palm(r):
    d = lin("w", [(0, "#f1e2cf"), (1, "#e3cfb4")])
    b = f'<rect width="{W}" height="{H}" fill="url(#w)"/><ellipse cx="900" cy="900" rx="780" ry="1000" fill="#fff7e8" opacity=".6"/>'
    b += palm(1500, 2100, 11, 1500, "#6b4a35", r, .55, 120) + palm(1250, 2200, 9, 1250, "#4a3123", r, .45, 90)
    for i in range(6):
        b += f'<path d="{arch(150 + i * 10, 220 + i * 10, 400 - i * 20, 520)}" fill="none" stroke="#c9a67c" stroke-width="3" opacity=".6"/>'
    return d, b, "#6b4a35"


def s_spa(r):
    d = lin("bg", [(0, "#e7efe4"), (1, "#cfdccb")])
    b = f'<rect width="{W}" height="{H}" fill="url(#bg)"/><rect y="1380" width="1600" height="620" fill="#f6f4ee"/>'
    for i in range(10):
        b += f'<rect y="{1400 + i * 62}" width="1600" height="18" fill="#e5e0d3" opacity=".7"/>'
    for (cx, cy, rx, ry, c) in [(800, 1370, 420, 120, "#7d8a8c"), (800, 1230, 330, 100, "#a39b92"), (800, 1110, 250, 82, "#5f6b6e"), (800, 1010, 170, 64, "#c4b8a6"), (800, 940, 96, 44, "#8c8279")]:
        b += f'<ellipse cx="{cx}" cy="{cy}" rx="{rx}" ry="{ry}" fill="{c}"/><ellipse cx="{cx - rx * .2}" cy="{cy - ry * .3}" rx="{rx * .5}" ry="{ry * .3}" fill="#fff" opacity=".18"/>'
    for a in (-35, -10, 18, 40):
        b += f'<g transform="rotate({a} 1250 1700)">' + "".join(f'<ellipse cx="{1250 + (j % 2 * 2 - 1) * 34}" cy="{1700 - j * 62}" rx="30" ry="14" fill="#6f9a7c"/>' for j in range(8)) + '<line x1="1250" y1="1700" x2="1250" y2="1210" stroke="#4d7a5b" stroke-width="8"/></g>'
    return d, b, "#5f6b6e"


def s_coffee(r):
    d = lin("l", [(0, "#d9c9b0"), (1, "#bfa88a")])
    b = f'<rect width="{W}" height="{H}" fill="url(#l)"/>'
    for i in range(0, 1600, 40):
        b += f'<line x1="{i}" y1="0" x2="{i}" y2="2000" stroke="#a58d6c" stroke-width="2" opacity=".35"/>'
    b += '<circle cx="800" cy="1000" r="560" fill="#f7f3ec"/><circle cx="800" cy="1000" r="420" fill="#fff"/>'
    b += '<circle cx="800" cy="1000" r="330" fill="#3b2216"/><circle cx="800" cy="1000" r="300" fill="#8a5a3a"/>'
    for i, rr in enumerate((250, 200, 150, 100, 50)):
        b += f'<ellipse cx="800" cy="{1000 + i * 4}" rx="{rr}" ry="{rr * 0.9}" fill="{"#f4e4d0" if i % 2 == 0 else "#b27a50"}"/>'
    b += '<path d="M800,780 Q940,1000 800,1240" stroke="#8a5a3a" stroke-width="12" fill="none"/>'
    b += '<path d="M1180,880 q150,0 150,120 q0,120 -150,120" stroke="#f7f3ec" stroke-width="54" fill="none"/>'
    b += '<rect x="1060" y="1500" width="420" height="40" rx="20" fill="#c9ccd0"/><ellipse cx="1480" cy="1520" rx="70" ry="42" fill="#c9ccd0"/>'
    return d, b, "#8a5a3a"


def s_tile(r):
    d = lin("bg", [(0, "#12806e"), (1, "#0b5f55")])
    b = f'<rect width="{W}" height="{H}" fill="url(#bg)"/>'
    for gy in range(0, 2000, 200):
        for gx in range(0, 1600, 200):
            c = "#f6efe0" if (gx + gy) % 400 == 0 else "#ffbe3d"
            b += f'<rect x="{gx + 8}" y="{gy + 8}" width="184" height="184" fill="#0e6f60"/><circle cx="{gx + 100}" cy="{gy + 100}" r="62" fill="{c}" opacity=".9"/><circle cx="{gx + 100}" cy="{gy + 100}" r="26" fill="#0b5f55"/>'
    b += f'<path d="{arch(380, 330, 840, 1670)}" fill="#f0e3cd"/><path d="{arch(450, 400, 700, 1600)}" fill="#e26d4b"/>'
    b += '<rect x="520" y="960" width="560" height="14" fill="#c4502f"/><circle cx="1000" cy="1180" r="34" fill="#ffd27a"/>'
    return d, b, "#e26d4b"


def s_cabana(r):
    d = lin("sk", [(0, "#a8dcf5"), (1, "#eaf8ff")]) + lin("sea", [(0, "#2fb8c9"), (1, "#7fe0e0")]) + lin("sand", [(0, "#f5dfb4"), (1, "#e6c58d")])
    b = f'<rect width="{W}" height="{H}" fill="url(#sk)"/><rect y="760" width="1600" height="520" fill="url(#sea)"/><rect y="1180" width="1600" height="820" fill="url(#sand)"/>'
    for i in range(7):
        b += f'<path d="M0,{900 + i * 48} q200,-24 400,0 t400,0 t400,0 t400,0" stroke="#fff" stroke-width="6" fill="none" opacity=".5"/>'
    for i in range(9):
        b += f'<rect x="{360 + i * 98}" y="520" width="98" height="640" fill="{"#ff6b57" if i % 2 == 0 else "#fff"}"/>'
    b += '<path d="M300,540 L800,240 L1300,540Z" fill="#ff6b57"/><path d="M300,540 L800,240 L1300,540 L1100,540 L800,320 L500,540Z" fill="#fff" opacity=".85"/>'
    b += '<rect x="360" y="520" width="882" height="30" fill="#2a2a2a" opacity=".12"/><rect x="620" y="760" width="360" height="400" fill="#16313a" opacity=".85"/>'
    b += '<ellipse cx="800" cy="1260" rx="420" ry="60" fill="#c9a76a" opacity=".5"/>'
    return d, b, "#ff6b57"


def s_courtyard(r):
    d = lin("w", [(0, "#ffd9b8"), (1, "#f6b78d")])
    b = f'<rect width="{W}" height="{H}" fill="url(#w)"/>'
    for x in (60, 1060):
        b += f'<path d="{arch(x, 200, 480, 1020)}" fill="#b4573a"/><path d="{arch(x + 40, 250, 400, 960)}" fill="#7fb7c9"/>'
    b += '<rect y="1260" width="1600" height="740" fill="#e9c9a6"/>'
    for i in range(10):
        b += f'<line x1="0" y1="{1300 + i * 80}" x2="1600" y2="{1300 + i * 80}" stroke="#c9a47c" stroke-width="4"/>'
    for (cx, cy, rx, c) in [(800, 1620, 380, "#f6f0e6"), (800, 1500, 260, "#e9e1d4"), (800, 1390, 150, "#f6f0e6")]:
        b += f'<ellipse cx="{cx}" cy="{cy}" rx="{rx}" ry="{rx * .24}" fill="{c}"/>'
    b += '<rect x="780" y="1230" width="40" height="190" fill="#e9e1d4"/><path d="M800,1230 q-120,-180 -260,-100 M800,1230 q120,-180 260,-100 M800,1230 v-210" stroke="#8fd3f0" stroke-width="12" fill="none" opacity=".85"/>'
    for (cx, cy, rr) in [(260, 1560, 180), (1360, 1580, 210), (180, 1820, 150)]:
        b += f'<circle cx="{cx}" cy="{cy}" r="{rr}" fill="#3a7d44"/><circle cx="{cx - rr * .3}" cy="{cy - rr * .3}" r="{rr * .5}" fill="#58a35f"/><rect x="{cx - 50}" y="{cy + rr - 20}" width="100" height="90" fill="#b4573a"/>'
    return d, b, "#b4573a"


def s_rooftop(r):
    d = lin("s", [(0, "#0b1030"), (1, "#5a3b7a")])
    b = f'<rect width="{W}" height="{H}" fill="url(#s)"/><circle cx="1180" cy="440" r="150" fill="#fdf3d0"/>'
    for i in range(70):
        b += f'<circle cx="{r.randint(0, 1600)}" cy="{r.randint(0, 800)}" r="{r.choice((2, 3, 4))}" fill="#fff" opacity="{r.uniform(.3, .9):.2f}"/>'
    x = 0
    while x < 1600:
        w, h = r.randint(150, 260), r.randint(380, 900)
        b += f'<rect x="{x}" y="{2000 - h - 300}" width="{w}" height="{h + 300}" fill="#161236"/>'
        for wy in range(2000 - h - 260, 1700, 70):
            for wx in range(x + 20, x + w - 30, 52):
                if r.random() < .35:
                    b += f'<rect x="{wx}" y="{wy}" width="26" height="36" fill="#ffd27a" opacity=".9"/>'
        x += w + 12
    b += '<rect y="1700" width="1600" height="300" fill="#0a0820"/><rect y="1700" width="1600" height="14" fill="#ff8fb1"/>'
    b += '<rect y="1760" width="1600" height="20" fill="#ff8fb1" opacity=".35"/>'
    return d, b, "#ffd27a"


SCENES = [
    # id, fn, category, alt text, tags, focal point (x, y as fractions)
    ("sunset-facade", s_facade, "exterior", "Arched hotel facade at sunset", ["warm", "architecture", "golden-hour"], (.5, .55)),
    ("pool-morning", s_pool, "leisure", "Turquoise pool with loungers and a coral umbrella", ["cool", "pool", "summer"], (.5, .6)),
    ("breakfast-table", s_breakfast, "food", "Breakfast table with croissant, oranges and coffee", ["warm", "breakfast", "table"], (.45, .4)),
    ("room-linen", s_room, "interior", "Guest room with white linen and an arched window", ["cool", "room", "calm"], (.5, .55)),
    ("lobby-arches", s_lobby, "interior", "Receding sandstone arches in the lobby", ["warm", "architecture", "symmetry"], (.5, .5)),
    ("terrace-dusk", s_terrace, "exterior", "Terrace at dusk with string lights and a candle", ["cool", "evening", "lights"], (.5, .7)),
    ("cocktail-bar", s_cocktail, "drink", "Amber cocktail in a coupe glass at the bar", ["dark", "evening", "drink"], (.5, .5)),
    ("palm-shadow", s_palm, "detail", "Palm shadows across a plaster wall", ["warm", "texture", "shadow"], (.7, .6)),
    ("spa-stones", s_spa, "wellness", "Stacked stones with eucalyptus on a white towel", ["neutral", "spa", "calm"], (.5, .55)),
    ("coffee-detail", s_coffee, "food", "Latte art from above on a linen table", ["warm", "coffee", "detail"], (.5, .5)),
    ("tile-door", s_tile, "detail", "Coral arched door framed by green and gold tiles", ["cool", "colour", "tiles"], (.5, .6)),
    ("beach-cabana", s_cabana, "exterior", "Striped coral cabana on the sand", ["warm", "beach", "stripes"], (.5, .4)),
    ("courtyard-fountain", s_courtyard, "exterior", "Sunlit courtyard with a tiered fountain", ["warm", "courtyard", "plants"], (.5, .65)),
    ("rooftop-night", s_rooftop, "exterior", "Rooftop view over a lit skyline at night", ["dark", "evening", "city"], (.5, .5)),
]


def finish(png: bytes, seed: int) -> Image.Image:
    im = Image.open(io.BytesIO(png)).convert("RGB")
    a = np.asarray(im, dtype=np.float32)
    rng = np.random.default_rng(seed)
    a += rng.normal(0, 6.5, a.shape[:2])[..., None]
    yy, xx = np.mgrid[0:a.shape[0], 0:a.shape[1]]
    v = 1 - 0.18 * (((xx / a.shape[1] - .5) ** 2 + (yy / a.shape[0] - .5) ** 2) * 2)
    a *= v[..., None]
    return Image.fromarray(np.clip(a, 0, 255).astype("uint8"))


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    manifest = []
    for n, (sid, fn, cat, alt, tags, focal) in enumerate(SCENES):
        rng = random.Random(1000 + n)
        defs, body, _ = fn(rng)
        svg = (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}" height="{H}">'
               f'<defs>{defs}</defs>{body}</svg>')
        im = finish(bytes(resvg_py.svg_to_bytes(svg_string=svg)), 7 + n)
        im.save(OUT / f"{sid}.jpg", quality=88, optimize=True)
        manifest.append({"id": sid, "file": f"{sid}.jpg", "category": cat, "alt": alt, "tags": tags,
                         "focal": list(focal), "license": "CC0 1.0 - self-created (scripts/make_assets.py)"})
        print("wrote", sid)
    (OUT / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
