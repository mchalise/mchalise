#!/usr/bin/env python3
"""Build the clickable "building cards" for the GitHub profile README.

Reads the Kathmandu Block close-ups and career content from ../personal_portfolio_page
and writes one self-contained SVG per stop and theme to assets/cards/:
  assets/cards/<id>-light.svg   warm cream card, terracotta accent
  assets/cards/<id>-dark.svg    night-banner navy card, lamp-glow accent

Each card: the building close-up (cut out of its cream background, webp data URI),
an in-scene style signboard with the org name, period, role and one short line.
Fonts (Fraunces, Inter Tight) are instanced, subset per card and inlined as woff2,
because README SVGs render as <img> and cannot load external files. The entrance
animation is CSS keyframes, staggered by career order; reduced motion shows the
final state. Re-run after the close-ups or stops change:
  python3 scripts/build_cards.py
Needs: Pillow, numpy, opencv-python, fonttools, brotli.
"""
import base64, io, re
from pathlib import Path

import cv2
import numpy as np
from fontTools import subset
from fontTools.ttLib import TTFont
from fontTools.varLib import instancer
from PIL import Image, ImageDraw, ImageFilter, ImageFont

ROOT = Path(__file__).resolve().parent.parent
SITE = ROOT.parent / "personal_portfolio_page"
RAW = SITE / "details" / "raw"
FONTS = SITE / "public" / "fonts"
OUT = ROOT / "assets" / "cards"
OUT.mkdir(parents=True, exist_ok=True)

ORDER = ["ku", "eb", "fgd", "investready", "whitehat", "zenledger", "bats", "freelance", "gurkha"]

# One tight line per stop, trimmed from the summaries in src/stops.ts (no new facts).
LINES = {
    "ku": "The first brick on the block: computer engineering at KU.",
    "eb": "First job: secure web apps for government agencies.",
    "fgd": "Web services behind cross-border digital money.",
    "investready": "Verifying investor eligibility for online equity investing.",
    "whitehat": "Six years placed with US startups, ZenLedger above all.",
    "zenledger": "Crypto tax: joined at MVP, scaled through a $15M Series B.",
    "bats": "Crypto forensics used by IRS investigation units.",
    "freelance": "Advising founders and prototyping web3, AI and compliance.",
    "gurkha": "A senior studio building for international clients.",
}

W, H = 400, 400                 # card viewBox
IMG = (70, 4, 260, 260)         # building image box (x, y, w, h)
PX = 400                        # building image pixels (~2x its README display size)

THEMES = {
    "light": dict(bg="#f6f1e7", edge="#e4d8c4", glow="#e9dcc4", glow_op=0.75, accent="#b4532f",
                  role="#2b2622", line="#6d625a", arrow="#b4532f"),
    "dark": dict(bg="#141c47", edge="#2a346c", glow="#ffb35c", glow_op=0.22, accent="#f3b36a",
                 role="#f4ede0", line="#a9b1d6", arrow="#f3b36a"),
}
SIGN = dict(face="#f4ecd9", rim="#c4ae8a", ink="#2a2521")


# ---------------------------------------------------------------- content
def load_stops():
    src = (SITE / "src" / "stops.ts").read_text()
    out = {}
    for block in re.split(r"\n\t\{\n", src.split("STOPS")[1])[1:]:
        f = {k: re.search(rf'\b{k}: "([^"]*)"', block) for k in ("id", "period", "org", "role")}
        if all(f.values()):
            d = {k: v.group(1) for k, v in f.items()}
            out[d["id"]] = d
    return out


# ---------------------------------------------------------------- fonts
def instance(path, **axes):
    f = instancer.instantiateVariableFont(TTFont(path), axes)
    b = io.BytesIO()
    f.flavor = None
    f.save(b)
    return b.getvalue()


FACES = {
    "S": instance(FONTS / "Fraunces.woff2", opsz=24, wght=620),   # signboard
    "R": instance(FONTS / "InterTight.woff2", wght=430),          # body
    "B": instance(FONTS / "InterTight.woff2", wght=620),          # role / period
}


def pil_font(face, size):
    return ImageFont.truetype(io.BytesIO(FACES[face]), size=int(round(size * 10)))


def text_w(face, size, text, spacing=0.0):
    return pil_font(face, size).getlength(text) / 10 + spacing * max(len(text) - 1, 0)


def woff2_subset(face, text):
    f = TTFont(io.BytesIO(FACES[face]))
    opt = subset.Options()
    opt.flavor = "woff2"
    opt.layout_features = ["kern", "liga"]
    opt.name_IDs = []
    opt.notdef_outline = False
    s = subset.Subsetter(opt)
    s.populate(text=text + " ")
    s.subset(f)
    b = io.BytesIO()
    f.flavor = "woff2"
    f.save(b)
    return base64.b64encode(b.getvalue()).decode()


# ---------------------------------------------------------------- art
def cells():
    cl = np.array(Image.open(RAW / "closeups.jpg").convert("RGB"))
    span = [(0, 338), (344, 680), (686, 1024)]   # 3x3 grid minus the white gutters
    out = {}
    for i, k in enumerate(ORDER):
        r, c = divmod(i, 3)
        out[k] = cl[span[r][0]:span[r][1], span[c][0]:span[c][1]].copy()
    wh = np.array(Image.open(RAW / "whitehat.jpg").convert("RGB"))
    out["whitehat"] = cv2.resize(wh[70:1024, 35:989], (336, 336), interpolation=cv2.INTER_AREA)
    return out


def ink_font(size):
    return ImageFont.truetype(io.BytesIO(FACES["B"]), size)


def repaint_sign(a, quad, text, k=4):
    """Cover a garbled sign face with a matched plate and redraw the text (as build-scene.py does)."""
    big = cv2.resize(a, None, fx=k, fy=k, interpolation=cv2.INTER_CUBIC)
    q = np.float32(quad) * k
    mask = np.zeros(big.shape[:2], np.uint8)
    cv2.fillConvexPoly(mask, q.astype(np.int32), 255)
    px = big[mask > 0]
    lum = px.mean(1)
    face = tuple(int(v) for v in np.median(px[lum >= np.percentile(lum, 55)], axis=0))
    tl, tr, _, bl = q
    pw, ph = int(np.linalg.norm(tr - tl) * 2), int(np.linalg.norm(bl - tl) * 2)
    plate = Image.new("RGBA", (pw, ph), face + (255,))
    d = ImageDraw.Draw(plate)
    size = int(ph * 0.62)
    while ink_font(size).getlength(text) > pw * 0.86:
        size -= 1
    d.text((pw / 2, ph * 0.52), text, font=ink_font(size), fill=(40, 38, 36, 255), anchor="mm")
    m = cv2.getPerspectiveTransform(np.float32([[0, 0], [pw, 0], [pw, ph], [0, ph]]), q)
    warped = cv2.warpPerspective(np.array(plate), m, (big.shape[1], big.shape[0]), flags=cv2.INTER_AREA)
    wim = Image.fromarray(warped, "RGBA").filter(ImageFilter.GaussianBlur(0.35 * k))
    base = Image.fromarray(big).convert("RGBA")
    base.alpha_composite(wim)
    return cv2.resize(np.array(base.convert("RGB")), (a.shape[1], a.shape[0]), interpolation=cv2.INTER_AREA)


def soften(a, poly, r=3.5):
    """Blur a garbled plaque into an unreadable, texture-matched patch."""
    m = np.zeros(a.shape[:2], np.uint8)
    cv2.fillPoly(m, [np.int32(poly)], 255)
    m = cv2.GaussianBlur(m.astype(np.float32) / 255, (0, 0), 1.2)[..., None]
    b = cv2.GaussianBlur(cv2.medianBlur(a, 5), (0, 0), r)
    return (a * (1 - m) + b * m).astype(np.uint8)


# per-cell fixes, in cell pixel coords
SIGN_FIX = {"investready": ([(93, 74), (177, 110.5), (176, 136.5), (92.5, 97)], "InvestReady")}
SOFTEN = {"zenledger": [(190, 199), (235, 185), (237, 197), (200, 216), (190, 214)]}
RESCUE = {   # light parts grabcut confuses with the cream backdrop: forced foreground
    "investready": [("poly", [(204, 151), (299, 109), (299, 251), (207, 294)]),        # white side wall
                    ("poly", [(89, 70), (181, 108), (180, 140), (88, 101)])],          # repainted sign
    "zenledger": [("ring", (141, 65, 29, 39, 12), (143, 68, 16, 26, 12))],             # rooftop ring
    "bats": [("diff", (176, 16, 228, 88))],                                            # satellite dish
}
ERASE = {"gurkha": [(0, 165, 72, 338)], "freelance": [(0, 190, 40, 338)]}
BOTTOM_FADE = {"freelance": 80, "gurkha": 70}


def cutout(k, a):
    h, w = a.shape[:2]
    b = 6
    bg = np.median(np.concatenate([a[:b].reshape(-1, 3), a[:, :b].reshape(-1, 3)]), 0)
    d = np.linalg.norm(a.astype(float) - bg, axis=2)
    m = np.full((h, w), cv2.GC_PR_FGD, np.uint8)
    m[d < 10] = cv2.GC_PR_BGD
    m[:b, :] = m[-b:, :] = cv2.GC_BGD
    m[:, :b] = m[:, -b:] = cv2.GC_BGD
    for mode, *g in RESCUE.get(k, []):
        if mode == "poly":
            cv2.fillPoly(m, [np.int32(g[0])], int(cv2.GC_FGD))
        elif mode == "ring":
            ring = np.zeros_like(m)
            (cx, cy, ax, ay, ang), (ix, iy, bx, by, _) = g
            cv2.ellipse(ring, (cx, cy), (ax, ay), ang, 0, 360, 1, -1)
            cv2.ellipse(ring, (ix, iy), (bx, by), ang, 0, 360, 0, -1)
            m[ring > 0] = cv2.GC_FGD
        else:
            x0, y0, x1, y1 = g[0]
            sub, dd = m[y0:y1, x0:x1], d[y0:y1, x0:x1]
            sub[dd > 12] = cv2.GC_FGD
            sub[dd < 6] = cv2.GC_BGD
    bgm, fgm = np.zeros((1, 65)), np.zeros((1, 65))
    cv2.grabCut(cv2.cvtColor(a, cv2.COLOR_RGB2BGR), m, None, bgm, fgm, 6, cv2.GC_INIT_WITH_MASK)
    fg = ((m == cv2.GC_FGD) | (m == cv2.GC_PR_FGD)).astype(np.uint8)
    for x0, y0, x1, y1 in ERASE.get(k, []):
        fg[y0:y1, x0:x1] = 0
    # keep the building plus loose bits that don't touch the cell edge (neighbours do)
    n, lab, st, _ = cv2.connectedComponentsWithStats(fg, 8)
    big = 1 + int(np.argmax(st[1:, 4]))
    keep = np.zeros_like(fg)
    for j in range(1, n):
        x, y, ww, hh, ar = st[j]
        edge = x <= b + 1 or y <= b + 1 or x + ww >= w - b - 1 or y + hh >= h - b - 1
        if j == big or (not edge and ar > 20):
            keep[lab == j] = 1
    out_a = cv2.GaussianBlur(keep.astype(np.float32), (0, 0), 0.7)
    out_rgb = a.astype(np.float32)
    # fade the frame so nothing ends on a hard cell edge
    yy, xx = np.mgrid[0:h, 0:w]
    edge = np.minimum.reduce([xx, w - 1 - xx, yy, h - 1 - yy]).astype(np.float32)
    fade = np.clip((edge - 3) / 16, 0, 1)
    if k in BOTTOM_FADE:
        fade *= np.clip((h - 1 - yy) / BOTTOM_FADE[k], 0, 1) ** 1.3
    out_a = np.clip(out_a * fade, 0, 1)
    rgba = np.dstack([np.clip(out_rgb, 0, 255), out_a * 255]).astype(np.uint8)
    im = Image.fromarray(rgba, "RGBA").resize((PX, PX), Image.LANCZOS)
    return im


def webp_uri(im, q=82):
    b = io.BytesIO()
    im.save(b, "WEBP", quality=q, alpha_quality=85, method=6)
    return "data:image/webp;base64," + base64.b64encode(b.getvalue()).decode()


# ---------------------------------------------------------------- svg
def esc(s):
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")


def wrap(text, face, size, maxw):
    if text_w(face, size, text) <= maxw:
        return [text]
    words = text.split()
    best = None
    for i in range(1, len(words)):
        a, b = " ".join(words[:i]), " ".join(words[i:])
        wmax = max(text_w(face, size, a), text_w(face, size, b))
        if best is None or wmax < best[0]:
            best = (wmax, [a, b])
    return best[1]


def fit(face, size, text, maxw, spacing=0.0, floor=0.0):
    while text_w(face, size, text, spacing) > maxw and size > floor:
        size -= 0.25
    return size


def f2(v):
    return f"{v:.2f}".rstrip("0").rstrip(".")


def card(i, stop, theme, img_uri):
    t = THEMES[theme]
    delay = i * 0.15
    org, period, role, line = stop["org"], stop["period"], stop["role"], LINES[stop["id"]]
    cx = W / 2

    # signboard
    s_size = fit("S", 21, org, 300)
    s_w = text_w("S", s_size, org) + 34
    s_h, s_y = 36, 240
    s_x = cx - s_w / 2

    p_txt = period.upper()
    p_size = fit("B", 12.5, p_txt, 330, spacing=1.4)
    r_size = fit("B", 17, role, 348)
    l_size = 15.5
    lines = wrap(line, "R", l_size, 336)

    y_p, y_r, y_l = 300, 325, 350
    body = "".join(
        f'<text x="{cx}" y="{f2(y_l + j * 20)}" class="l">{esc(s)}</text>' for j, s in enumerate(lines))

    fonts = "".join(
        f'@font-face{{font-family:{n};src:url(data:font/woff2;base64,{woff2_subset(face, txt)}) format("woff2")}}'
        for n, face, txt in [("CS", "S", org), ("CR", "R", line), ("CB", "B", p_txt + role + "↗")])

    ix, iy, iw, ih = IMG
    css = (
        fonts +
        f".l{{font:400 {l_size}px CR,'Inter Tight',system-ui,sans-serif;fill:{t['line']};text-anchor:middle}}"
        f".p{{font:600 {f2(p_size)}px CB,'Inter Tight',system-ui,sans-serif;letter-spacing:1.4px;fill:{t['accent']};text-anchor:middle}}"
        f".r{{font:600 {f2(r_size)}px CB,'Inter Tight',system-ui,sans-serif;fill:{t['role']};text-anchor:middle}}"
        f".s{{font:600 {f2(s_size)}px CS,Fraunces,Georgia,serif;fill:{SIGN['ink']};text-anchor:middle}}"
        f".a{{font:600 19px CB,'Inter Tight',system-ui,sans-serif;fill:{t['arrow']}}}"
        "@keyframes rise{from{opacity:0;transform:translateY(22px) scale(.96)}to{opacity:1;transform:none}}"
        "@keyframes drop{0%{opacity:0;transform:translateY(-26px)}70%{opacity:1;transform:translateY(3px)}100%{opacity:1;transform:none}}"
        "@keyframes fade{from{opacity:0;transform:translateY(6px)}to{opacity:1;transform:none}}"
        "@keyframes bob{0%,100%{transform:none}50%{transform:translateY(-3px)}}"
        "@keyframes glow{0%,100%{opacity:1}50%{opacity:.72}}"
        ".bd,.sg,.tx{transform-box:fill-box;transform-origin:50% 100%}"
        f".bd{{animation:rise .9s cubic-bezier(.2,.8,.25,1) {f2(delay)}s both}}"
        f".fl{{animation:bob 6s ease-in-out {f2(delay + 1.4)}s infinite}}"
        f".sg{{animation:drop .7s cubic-bezier(.3,.7,.3,1) {f2(delay + .45)}s both}}"
        f".tx{{animation:fade .6s ease-out {f2(delay + .7)}s both}}"
        f".gl{{animation:glow 6s ease-in-out {f2(delay)}s infinite}}"
        "@media (prefers-reduced-motion:reduce){*{animation:none!important}}"
    )
    aria = f"{org} · {period} · {role}"
    return f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}" height="{H}" role="img" aria-label="{esc(aria)}">
<title>{esc(aria)}</title>
<defs><radialGradient id="g" cx="50%" cy="58%" r="50%"><stop offset="0" stop-color="{t['glow']}" stop-opacity="{t['glow_op']}"/><stop offset="1" stop-color="{t['glow']}" stop-opacity="0"/></radialGradient>
<clipPath id="c"><rect width="{W}" height="{H}" rx="22"/></clipPath></defs>
<style>{css}</style>
<g clip-path="url(#c)">
<rect width="{W}" height="{H}" fill="{t['bg']}"/>
<ellipse class="gl" cx="{cx}" cy="150" rx="185" ry="150" fill="url(#g)"/>
<g class="bd"><g class="fl"><image x="{ix}" y="{iy}" width="{iw}" height="{ih}" href="{img_uri}"/></g></g>
<g class="sg">
<rect x="{f2(s_x + 1.5)}" y="{s_y + 3}" width="{f2(s_w)}" height="{s_h}" rx="5" fill="#000" opacity=".16"/>
<rect x="{f2(s_x)}" y="{s_y}" width="{f2(s_w)}" height="{s_h}" rx="5" fill="{SIGN['face']}" stroke="{SIGN['rim']}" stroke-width="2.5"/>
<text x="{cx}" y="{s_y + s_h / 2 + s_size * 0.34:.2f}" class="s">{esc(org)}</text>
</g>
<g class="tx">
<text x="{cx}" y="{y_p}" class="p">{esc(p_txt)}</text>
<text x="{cx}" y="{y_r}" class="r">{esc(role)}</text>
{body}
</g>
<text x="{W - 22}" y="38" class="a tx" text-anchor="end">↗</text>
</g>
<rect x="1" y="1" width="{W - 2}" height="{H - 2}" rx="21" fill="none" stroke="{t['edge']}" stroke-width="2"/>
</svg>
"""


def main():
    stops = load_stops()
    art = cells()
    for k, (quad, text) in SIGN_FIX.items():
        art[k] = repaint_sign(art[k], quad, text)
    for k, poly in SOFTEN.items():
        art[k] = soften(art[k], poly)
    for i, k in enumerate(ORDER):
        uri = webp_uri(cutout(k, art[k]))
        for theme in THEMES:
            svg = card(i, stops[k], theme, uri)
            p = OUT / f"{k}-{theme}.svg"
            p.write_text(svg)
            print(f"{p.relative_to(ROOT)}  {len(svg.encode()) / 1024:.1f} KB")


if __name__ == "__main__":
    main()
