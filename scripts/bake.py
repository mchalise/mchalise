#!/usr/bin/env python3
"""Bake the heavy, slow-changing pieces of the profile banner into text fragments.

Runs locally (needs Pillow, numpy, opencv-python, fonttools, brotli) and reads the
Kathmandu Block art from ../personal_portfolio_page. Writes bake/*.json: SVG
<defs>/body strings and CSS with every image and font already inlined as data
URIs, so scripts/assemble.py can stitch a banner with nothing but the stdlib
(an hourly GitHub Action picks the mode, the clock label and the commit-lit windows).

  bake/common.json   fonts, rise/pop/pin/title/Haki-greeting pieces shared by all modes
  bake/day.json      day base + clouds, doves, butterfly, strolling Haki
  bake/dusk.json     cleaned golden-hour base + 12 window rings, haze, doves home, lanterns
  bake/night.json    unlit base + 12 window rings, bulb strings, fireflies, lanterns

Run: python3 scripts/bake.py   (then python3 scripts/assemble.py --all-previews)
"""
import base64, importlib.util, io, json, math, random, re, sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageFilter

ROOT = Path(__file__).resolve().parent.parent
SITE = ROOT.parent / "personal_portfolio_page"
SC = SITE / "public" / "scene"
RAW = SITE / "details" / "raw"
FONTS = SITE / "public" / "fonts"
BAKE = ROOT / "bake"
CACHE = BAKE / "cache"
SYS_DEVA = Path("/usr/share/fonts/truetype/google-fonts/Poppins-Medium.ttf")  # has Devanagari

W, H = 1408, 768                     # scene px (site coords)
VB = (96, 28, 1216, 728)             # banner crop (x, y, w, h)
HAKI_K = 1.3
RINGS = 12                           # window light groups, nearest the stupa first
random.seed(108)

# intro timeline (seconds from load)
T_RISE = 1.7
T_POP0, T_POPD, T_POPLEN = 1.35, 0.3, 0.75
POP_ORDER = ["ku", "eb", "fgd", "investready", "whitehat", "zenledger", "bats", "freelance", "gurkha"]
T_PINOUT = T_POP0 + T_POPD * (len(POP_ORDER) - 1) + T_POPLEN + 2.4
T_TITLE = 4.15
T_HAKI = 4.7
T_BUBBLE = 5.25
T_CYCLE0, CYCLE = 5.5, 14.0
T_LIGHTS = 4.4


def webp(im, q=80, **kw):
    b = io.BytesIO()
    im.save(b, "WEBP", quality=q, method=6, **kw)
    return b.getvalue()


def uri(data, mime="image/webp"):
    return f"data:{mime};base64," + base64.b64encode(data).decode()


def frames(path, size=None):
    im = Image.open(path)
    out = []
    for i in range(getattr(im, "n_frames", 1)):
        im.seek(i)
        f = im.convert("RGBA")
        if size:
            f = f.resize(size, Image.LANCZOS)
        out.append(f)
    return out


def strip(fs):
    w, h = fs[0].size
    s = Image.new("RGBA", (w * len(fs), h))
    for i, f in enumerate(fs):
        s.paste(f, (i * w, 0))
    return s


def f2(v):
    return f"{v:.2f}".rstrip("0").rstrip(".")


def sprite_defs(name, path, size=None, q=78):
    fs = frames(path, size)
    w, h = fs[0].size
    return {"id": name, "n": len(fs), "w": w, "h": h, "uri": uri(webp(strip(fs), q, alpha_quality=90))}


def image_def(s):
    return f'<image id="{s["id"]}" width="{s["w"] * s["n"]}" height="{s["h"]}" href="{s["uri"]}"/>'


def sprite_use(s, x, y, dw, dur, cls_extra="", delay=0.0):
    """A sprite clipped to one cell (nested <svg>) whose strip steps through all frames."""
    dh = dw * s["h"] / s["w"]
    anim = f"animation:strip-{s['id']} {f2(dur)}s steps({s['n']}) {f2(-delay)}s infinite"
    return (f'<svg x="{f2(x)}" y="{f2(y)}" width="{f2(dw)}" height="{f2(dh)}" viewBox="0 0 {s["w"]} {s["h"]}" overflow="hidden" class="{cls_extra}">'
            f'<use href="#{s["id"]}" style="{anim}"/></svg>')


def strip_kf(s):
    return f'@keyframes strip-{s["id"]}{{to{{transform:translateX(-{s["w"] * s["n"]}px)}}}}'


def base_def(im, q):
    return f'<image id="base" width="{W}" height="{H}" href="{uri(webp(im, q))}"/>'


def backdrop(im):
    """Tiny blurred copy of the crop, stretched under everything: the fog the block rises out of."""
    x, y, w, h = VB
    s = im.width / W
    small = im.crop((int(x * s), int(y * s), int((x + w) * s), int((y + h) * s))).resize((64, 38), Image.LANCZOS)
    small = small.filter(ImageFilter.GaussianBlur(1.6))
    return f'<image x="{x}" y="{y}" width="{w}" height="{h}" preserveAspectRatio="none" href="{uri(webp(small, 60))}"/>'


# ---------------------------------------------------------------- site data
def hotspots():
    src = (SITE / "src" / "hotspots.ts").read_text()
    out = {}
    for m in re.finditer(r'id: "([\w-]+)", kind: "\w+", poly: (\[\[.*?\]\])', src):
        out[m.group(1)] = json.loads(m.group(2))
    return out


def stops():
    src = (SITE / "src" / "stops.ts").read_text()
    out = {}
    for m in re.finditer(r'id: "(\w+)",\s*year: "([^"]+)",.*?org: "([^"]+)"', src, re.S):
        out[m.group(1)] = (m.group(2), m.group(3))
    return out


# ---------------------------------------------------------------- fonts
class Font:
    """Instanced + subset web font, with advance widths for layout without a browser."""

    def __init__(self, path, family, text, axes=None, features=None):
        from fontTools.ttLib import TTFont
        from fontTools import subset
        f = TTFont(path)
        if axes and "fvar" in f:
            from fontTools.varLib import instancer
            f = instancer.instantiateVariableFont(f, axes)
        self.upm = f["head"].unitsPerEm
        cmap, hmtx = f.getBestCmap(), f["hmtx"]
        self.adv = {c: hmtx[cmap[ord(c)]][0] / self.upm for c in set(text) if ord(c) in cmap}
        opts = subset.Options()
        opts.flavor = "woff2"
        opts.layout_features = features or ["kern", "liga"]
        opts.name_IDs = []
        opts.notdef_outline = True
        sub = subset.Subsetter(opts)
        sub.populate(text=text)
        sub.subset(f)
        b = io.BytesIO()
        f.flavor = "woff2"
        f.save(b)
        self.data = b.getvalue()
        self.family = family
        print(f"  font {family}: {len(self.data) // 1024} KB")

    def css(self):
        return f'@font-face{{font-family:{self.family};src:url({uri(self.data, "font/woff2")}) format("woff2")}}'

    def width(self, s, size, spacing=0.0):
        return sum(self.adv.get(c, 0.55) for c in s) * size + spacing * max(len(s) - 1, 0)


def sign_font_ttf():
    """Static bold Inter Tight for repainting the dusk signboards with build-scene.py's code."""
    from fontTools.ttLib import TTFont
    from fontTools.varLib import instancer
    p = CACHE / "InterTight-700.ttf"
    if not p.exists():
        f = instancer.instantiateVariableFont(TTFont(FONTS / "InterTight.woff2"), {"wght": 700})
        f.flavor = None
        f.save(p)
    return p


# ---------------------------------------------------------------- dusk clean-up
def load_build_scene():
    spec = importlib.util.spec_from_file_location("build_scene", SITE / "scripts" / "build-scene.py")
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def paint_blobs(a):
    """Paint out the stray light pools on the ground right of the block: replace pixels brighter
    than a smooth (cubic) fit of the surrounding backdrop with that fit, feathered."""
    import cv2
    Hh, Ww = a.shape[:2]
    yy, xx = np.mgrid[0:Hh, 0:Ww]
    edge = 440 + (1262 - xx) * (305 / 562)
    R = ((yy > edge + 12) & (yy >= 520)) | ((xx >= 1278) & (yy >= 470))
    lum = a.mean(axis=2)
    X, Y = xx[R] / Ww, yy[R] / Hh
    F = np.stack([np.ones_like(X), X, Y, X * X, X * Y, Y * Y, X ** 3, X * X * Y, X * Y * Y, Y ** 3], 1)
    keep = np.ones(len(X), bool)
    for _ in range(5):
        coef = np.linalg.lstsq(F[keep], lum[R][keep], rcond=None)[0]
        pred = F @ coef
        keep = (lum[R] - pred) < 3
    fit = np.zeros_like(a)
    for c in range(3):
        cc = np.linalg.lstsq(F[keep], a[..., c][R][keep], rcond=None)[0]
        fit[..., c][R] = F @ cc
    m = np.zeros((Hh, Ww), np.float32)
    m[R] = np.clip((lum[R] - pred - 3) / 5, 0, 1)
    m = cv2.dilate(m, np.ones((9, 9), np.uint8))
    m = cv2.GaussianBlur(m, (0, 0), 7)
    # only where the pools are: two soft ellipses, so no seams anywhere else
    zone = np.zeros((Hh, Ww), np.float32)
    for (cx, cy, rx, ry) in [(1325, 650, 200, 115), (1075, 740, 240, 95)]:
        zone = np.maximum(zone, np.clip(2.2 - 2.2 * np.hypot((xx - cx) / rx, (yy - cy) / ry), 0, 1))
    inner = cv2.GaussianBlur(cv2.erode(R.astype(np.uint8), np.ones((9, 9), np.uint8)).astype(np.float32), (0, 0), 3)
    m = (m * inner * zone)[..., None]
    noise = np.random.default_rng(3).normal(0, 1.1, a.shape)
    return a * (1 - m) + (fit + noise) * m


def clean_dusk(force=False):
    p = CACHE / "dusk-clean.webp"
    if p.exists() and not force:
        return Image.open(p).convert("RGB")
    bs = load_build_scene()
    bs.FONT = str(sign_font_ttf())
    a = np.asarray(Image.open(RAW / "dusk.jpg").convert("RGB")).astype(np.float32)
    a = paint_blobs(a)
    im = Image.fromarray(np.clip(a, 0, 255).astype(np.uint8))
    im = im.resize((W * 2, H * 2), Image.LANCZOS).filter(ImageFilter.UnsharpMask(radius=1.4, percent=55, threshold=2))
    im = bs.fix_signs(im, False, 2)
    im.save(p, quality=92, method=6)
    print("  dusk cleaned →", p.relative_to(ROOT))
    return im


# ---------------------------------------------------------------- Haki (small, strolling)
NODES = {"investready": (842, 470), "plaza-f": (770, 440), "plaza-r": (800, 352), "freelance": (815, 300), "lane-b": (757, 305)}
ROUTE = ["investready", "plaza-f", "plaza-r", "freelance", "lane-b"]
SPEED = 46
ROWS = {"down": 0, "side": 1, "up": 2}


def haki(poses, filt, shared):
    """Haki strolls InvestReady → plaza → rooftop studio → back lane and back, posing at each end."""
    sheet = Image.open(SC / "haki" / "walk.webp").convert("RGBA")
    walks = {}
    for name, r in ROWS.items():
        row = sheet.crop((140, 145 * r, 140 * 9, 145 * (r + 1)))
        walks[name] = {"id": f"hk-{name}", "n": 8, "w": 140, "h": 145, "uri": uri(webp(row, 80, alpha_quality=90))}
    ps = [shared[f"hk-{p}"] if f"hk-{p}" in shared else sprite_defs(f"hk-{p}", SC / "haki" / f"{p}.webp", q=76) for p in poses]

    def legs(route):
        out = []
        for a, b in zip(route, route[1:]):
            (ax, ay), (bx, by) = NODES[a], NODES[b]
            dx, dy = bx - ax, by - ay
            if abs(dx) > abs(dy) * 0.9:
                row, face = "side", (-1 if dx < 0 else 1)
            else:
                row, face = ("down" if dy > 0 else "up"), 1
            out.append((NODES[a], NODES[b], row, face, math.dist(NODES[a], NODES[b]) / SPEED))
        return out

    POSE_T = 5.0
    segs, t = [], 0.0
    segs.append((t, t + POSE_T, "pose", 0, NODES[ROUTE[0]])); t += POSE_T
    for leg in legs(ROUTE):
        segs.append((t, t + leg[4], "walk", leg)); t += leg[4]
    segs.append((t, t + POSE_T, "pose", 1, NODES[ROUTE[-1]])); t += POSE_T
    for leg in legs(ROUTE[::-1]):
        segs.append((t, t + leg[4], "walk", leg)); t += leg[4]
    T = t
    pct = lambda v: f2(v / T * 100) + "%"
    eps = 0.0005 * T
    pos_kf = []
    for sg in segs:
        pos_kf += [(sg[0], sg[4]), (sg[1], sg[4])] if sg[2] == "pose" else [(sg[0], sg[3][0]), (sg[1], sg[3][1])]
    move = "@keyframes hk-move{" + "".join(f"{pct(tt)}{{transform:translate({f2(x)}px,{f2(y)}px)}}" for tt, (x, y) in pos_kf) + "}"

    def steps_kf(name, prop, val):
        ks = []
        for sg in segs:
            v = val(sg)
            ks += [(sg[0] + (eps if sg[0] > 0 else 0), v), (sg[1], v)]
        return f"@keyframes {name}{{" + "".join(f"{pct(tt)}{{{prop}:{v}}}" for tt, v in ks) + "}"

    css = [move,
           steps_kf("hk-face", "transform", lambda sg: f"scale({sg[3][3] if sg[2] == 'walk' else 1},1)"),
           *[steps_kf(f"hk-v-{r}", "opacity", lambda sg, r=r: 1 if sg[2] == "walk" and sg[3][2] == r else 0) for r in ROWS],
           steps_kf("hk-p0", "opacity", lambda sg: 1 if sg[2] == "pose" and sg[3] == 0 else 0),
           steps_kf("hk-p1", "opacity", lambda sg: 1 if sg[2] == "pose" and sg[3] == 1 else 0),
           *[strip_kf(w) for w in walks.values()], *[strip_kf(p) for p in ps if p["id"] not in shared]]
    for cls, kf in [("hk", "hk-move"), ("hk-face", "hk-face"), ("hk-p0", "hk-p0"), ("hk-p1", "hk-p1"), *[(f"hk-{r}", f"hk-v-{r}") for r in ROWS]]:
        css.append(f".{cls}{{animation:{kf} {f2(T)}s linear infinite}}")
    k = HAKI_K
    step_dur = 8 / (SPEED / 7.5)
    x0, y0 = NODES[ROUTE[0]]
    body = (f'<g class="hk" transform="translate({x0} {y0})"><g transform="scale({k})" filter="url(#{filt})"><g class="hk-face">'
            + "".join(f'<g class="hk-{r}" opacity="0">{sprite_use(walks[r], -25.1, -51.3, 50.2, step_dur)}</g>' for r in ROWS)
            + f'</g><g class="hk-p0">{sprite_use(ps[0], -30, -54.7, 60, ps[0]["n"] / 12)}</g>'
            f'<g class="hk-p1" opacity="0">{sprite_use(ps[1], -30, -54.7, 60, ps[1]["n"] / 12)}</g></g></g>')
    defs = [*[image_def(w) for w in walks.values()], *[image_def(p) for p in ps if p["id"] not in shared]]
    return defs, css, body


# ---------------------------------------------------------------- shared life
def doves(home=False, n=6):
    dove = sprite_defs("dove", SC / "dove.webp", (56, 61), q=80)
    defs, css, body = [image_def(dove)], [strip_kf(dove)], []
    a, b = (VB[0] + VB[2] + 80, VB[0] + 330) if home else (VB[0] - 80, VB[0] + VB[2] + 80)
    if home:   # dusk: fly in from the right and settle down towards the temple roofs, fading as they land
        css.append(f"@keyframes fly{{0%{{transform:translate({a}px,0);opacity:0}}4%{{opacity:1}}50%{{transform:translate({(a + b) / 2}px,40px)}}62%{{opacity:1}}70%{{transform:translate({b + 120}px,96px);opacity:0}}100%{{transform:translate({b + 120}px,96px);opacity:0}}}}")
    else:
        css.append(f"@keyframes fly{{0%{{transform:translateX({a}px)}}55%{{transform:translateX({b}px)}}100%{{transform:translateX({b}px)}}}}")
    css.append("@keyframes bob{0%,100%{transform:translateY(0)}50%{transform:translateY(-7px)}}")
    for i in range(n):
        y = (60 if home else 70) + random.random() * (70 if home else 120) + (i % 3) * 18
        s = 0.8 + random.random() * 0.4
        lag = i * 0.55 + random.random() * 0.4
        flip = ' transform="scale(-1 1)"' if home else ""
        body.append(f'<g transform="translate(0 {f2(y)})"><g style="animation:fly {30 if home else 26}s linear {f2(-2 + lag)}s infinite both"><g style="animation:bob {f2(2.6 + i * .3)}s ease-in-out infinite">'
                    f'<g{flip}><g transform="scale({f2(s)})" filter="url(#soft)">{sprite_use(dove, -14, -15, 28, 0.9 if not home else 1.1, delay=random.random())}</g></g></g></g></g>')
    return defs, css, body


def lanterns(which):
    lan = Image.open(SC / "fx" / "lantern-float.webp").convert("RGBA").resize((52, 49), Image.LANCZOS)
    defs = [f'<image id="lan" width="26" height="24.5" href="{uri(webp(lan, 80, alpha_quality=90))}"/>']
    css, body = [], []
    for i, (x, dur, lag, sway) in enumerate([(700, 30, 0, 26), (760, 36, 12, -20), (640, 33, 22, 18)]):
        if i not in which:
            continue
        css.append(f"@keyframes lan{i}{{0%{{transform:translate(0,0);opacity:0}}6%{{opacity:1}}50%{{transform:translate({sway}px,-230px)}}85%{{opacity:.9}}100%{{transform:translate({-sway * .4}px,-470px);opacity:0}}}}")
        css.append(f"@keyframes sw{i}{{0%,100%{{transform:rotate(-4deg)}}50%{{transform:rotate(4deg)}}}}")
        body.append(f'<g transform="translate({x} 420)"><g style="animation:lan{i} {dur}s linear {f2(-lag + 6)}s infinite both">'
                    f'<g filter="url(#glow)" style="animation:sw{i} 4s ease-in-out infinite"><use href="#lan" x="-13" y="-24.5"/></g></g></g>')
    return defs, css, body


def fireflies(spots, start=5.5):
    css, body = [], []
    for i, (x, y) in enumerate(spots):
        pts = [(0, 0)] + [((random.random() - .5) * 44, (random.random() - .5) * 30) for _ in range(3)] + [(0, 0)]
        css.append(f"@keyframes ff{i}{{" + "".join(f"{j * 25}%{{transform:translate({f2(px)}px,{f2(py)}px)}}" for j, (px, py) in enumerate(pts)) + "}")
        dur = 9 + random.random() * 7
        blink = 2.2 + random.random() * 2.4
        body.append(f'<g transform="translate({x} {y})"><g style="animation:ff{i} {f2(dur)}s ease-in-out {f2(-random.random() * dur)}s infinite">'
                    f'<circle r="5" fill="url(#ff)" style="animation:blink {f2(blink)}s ease-in-out {f2(start + random.random() * 3)}s infinite both"/></g></g>')
    css.append("@keyframes blink{0%,100%{opacity:0}45%{opacity:1}60%{opacity:.85}}")
    return css, body


GLOW = '<filter id="glow" x="-150%" y="-150%" width="400%" height="400%"><feGaussianBlur in="SourceGraphic" stdDeviation="6" result="b"/><feColorMatrix in="b" type="matrix" values="1 0 0 0 .25  0 .8 0 0 .1  0 0 .4 0 0  0 0 0 1.2 0" result="g"/><feMerge><feMergeNode in="g"/><feMergeNode in="SourceGraphic"/></feMerge></filter>'
FF = '<radialGradient id="ff"><stop offset="0" stop-color="#fff6b0"/><stop offset=".35" stop-color="#ffd84a" stop-opacity=".85"/><stop offset="1" stop-color="#ffb000" stop-opacity="0"/></radialGradient>'
SOFT = '<filter id="soft" x="-20%" y="-20%" width="140%" height="140%"><feDropShadow dx="0" dy="5" stdDeviation="2.5" flood-color="#3c2814" flood-opacity=".16"/></filter>'
HK_SHADOW = '<filter id="hk-shadow" x="-30%" y="-30%" width="160%" height="160%"><feDropShadow dx="0" dy="1.5" stdDeviation="0.8" flood-color="#28190a" flood-opacity=".3"/></filter>'


# ---------------------------------------------------------------- lights
def light_layers(base):
    """Additive window light as plain alpha-over images against this base (out = base + L):
    a = max(L)/255, C = base + L/a. Windows split into RINGS groups by distance from the stupa,
    plus the ambient spill and two alternating bulb-string groups."""
    atlas = np.asarray(Image.open(SC / "lights.webp").convert("RGB"), dtype=np.float32)
    src = (SITE / "src" / "lights.generated.ts").read_text()
    lights = json.loads(re.search(r"LIGHTS = (\[.*?\])(?: as const)?;", src, re.S).group(1))
    D = np.asarray(base, dtype=np.float32)
    windows = sorted([l for l in lights if l["kind"] not in ("string", "spill")], key=lambda l: l["d"])
    spill = [l for l in lights if l["kind"] == "spill"]
    strings = [l for l in lights if l["kind"] == "string"]
    rnd = random.Random(7)
    rnd.shuffle(strings)
    groups = [(f"r{i}", "ring", windows[i * len(windows) // RINGS:(i + 1) * len(windows) // RINGS]) for i in range(RINGS)]
    groups += [("sp", "spill", spill), ("sa", "string", strings[0::2]), ("sb", "string", strings[1::2])]
    out, total = [], 0
    for gid, kind, ls in groups:
        L = np.zeros_like(D)
        for l in ls:
            x, y, w, h, ax, ay = (l[k] for k in ("x", "y", "w", "h", "ax", "ay"))
            x2, y2 = min(x + w, D.shape[1]), min(y + h, D.shape[0])
            L[y:y2, x:x2] += atlas[ay:ay + (y2 - y), ax:ax + (x2 - x)]
        L = np.minimum(L, 255)
        a = L.max(axis=2) / 255.0
        a3 = np.where(a > 1e-3, a, 1)[..., None]
        C = np.clip(D + L / a3, 0, 255)
        im = Image.fromarray(np.dstack([C, a * 255]).astype(np.uint8), "RGBA")
        bb = im.getchannel("A").getbbox()
        if not bb:
            continue
        crop = im.crop(bb)
        data = webp(crop, 78, alpha_quality=85)
        total += len(data)
        out.append({"gid": gid, "kind": kind, "svg": f'<image class="lt {gid}" x="{f2(bb[0] / 2)}" y="{f2(bb[1] / 2)}" width="{f2(crop.width / 2)}" height="{f2(crop.height / 2)}" href="{uri(data)}"/>'})
    print(f"  light layers: {total // 1024} KB")
    return out


# ---------------------------------------------------------------- modes
def build_day(shared):
    base = Image.open(SC / "day.webp").convert("RGB")
    defs = [base_def(base, 74), HK_SHADOW, SOFT,
            '<filter id="hb-f" x="-30%" y="-30%" width="160%" height="160%"><feDropShadow dx="0" dy="2" stdDeviation="1.4" flood-color="#28190a" flood-opacity=".28"/></filter>']
    css, under, life = [], [], []
    for i, (name, w, y, dur, off) in enumerate([("cloud-1", 230, 30, 110, 15), ("cloud-4", 190, 58, 140, 85)]):
        im = Image.open(SC / f"{name}.webp").convert("RGBA")
        h = w * im.height / im.width
        im = im.resize((w * 2, round(h * 2)), Image.LANCZOS)
        defs.append(f'<image id="cl{i}" width="{w}" height="{f2(h)}" href="{uri(webp(im, 70, alpha_quality=80))}"/>')
        css.append(f".cl{i}{{animation:drift {dur}s linear {-off}s infinite}}")
        under.append(f'<g transform="translate(0 {y})"><use href="#cl{i}" class="cl{i}" opacity=".72"/></g>')
    css.append(f"@keyframes drift{{from{{transform:translateX({VB[0] - 380}px)}}to{{transform:translateX({VB[0] + VB[2] + 20}px)}}}}")
    d, c, b = doves(False)
    defs += d; css += c; life += b
    bf = sprite_defs("bf", SC / "fx" / "butterfly.webp", (36, 26), q=80)
    defs.append(image_def(bf)); css.append(strip_kf(bf))
    cx, cy = 300, 405
    pts = [(cx + 46 * math.sin(j / 12 * 2 * math.pi), cy - 22 * math.sin(2 * j / 12 * 2 * math.pi) - 10 * math.cos(j / 12 * 2 * math.pi)) for j in range(13)]
    css.append("@keyframes bf-path{" + "".join(f"{f2(j / 12 * 100)}%{{transform:translate({f2(x)}px,{f2(y)}px)}}" for j, (x, y) in enumerate(pts)) + "}")
    life.append(f'<g style="animation:bf-path 14s ease-in-out infinite">{sprite_use(bf, -9, -7, 18, 1.2)}</g>')
    d, c, b = haki(("wave", "namaste"), "hk-shadow", shared)
    defs += d; css += c; life.append(b)
    theme = {"bg": "#f2ede4", "ink": "#2b1d13", "ink2": "#7a4f2c", "halo": "#fbf6ec", "halo_op": ".9",
             "plate": "#fff8ea", "plate_stroke": "#9a6a3a", "plate_ink": "#2b1d13", "fog": "#f7f2e9", "glow": "#ffcf6e"}
    return {"theme": theme, "backdrop": backdrop(base), "defs": defs, "css": css, "under": under, "lights": [], "life": life,
            "title": "The Kathmandu Block by day: Manish Chalise's career as an isometric city block"}


def build_dusk(shared):
    base = clean_dusk("--redusk" in sys.argv)
    defs = [base_def(base, 72), HK_SHADOW, SOFT, GLOW, FF,
            '<filter id="hb-f" x="-30%" y="-30%" width="160%" height="160%"><feColorMatrix type="matrix" values=".95 0 0 0 .02  0 .88 0 0 0  0 0 .85 0 0  0 0 0 1 0"/><feDropShadow dx="0" dy="2" stdDeviation="1.4" flood-color="#2a1208" flood-opacity=".32"/></filter>',
            '<radialGradient id="haze" cx="12%" cy="0%" r="80%"><stop offset="0" stop-color="#ffb46a" stop-opacity=".55"/><stop offset=".55" stop-color="#ff9a6a" stop-opacity=".12"/><stop offset="1" stop-color="#b07ab8" stop-opacity="0"/></radialGradient>']
    css, under, life = [], [], []
    x, y, w, h = VB
    css.append("@keyframes haze{0%,100%{opacity:.75}50%{opacity:1}}")
    under.append(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" fill="url(#haze)" style="animation:haze 9s ease-in-out infinite"/>')
    lights = light_layers(base)
    d, c, b = doves(True, n=5)
    defs += d; css += c; life += b
    d, c, b = lanterns({0, 2})
    defs += d; css += c; life += b
    c, b = fireflies([(330, 520), (560, 470), (760, 470), (930, 520), (520, 610), (1000, 600)], start=7)
    css += c; life += b
    d, c, b = haki(("wave", "namaste"), "hk-shadow", shared)
    defs += d; css += c; life.append(b)
    theme = {"bg": "#d9a88f", "ink": "#2a160d", "ink2": "#6e3a1f", "halo": "#ffe9d2", "halo_op": ".7",
             "plate": "#fff3e0", "plate_stroke": "#8f5730", "plate_ink": "#2a160d", "fog": "#f6d8c2", "glow": "#ffc46a",
             "light_op": ".62", "string_op": ".8", "spill_op": ".45"}
    return {"theme": theme, "backdrop": backdrop(base), "defs": defs, "css": css, "under": under, "lights": lights, "life": life,
            "title": "The Kathmandu Block at dusk: Manish Chalise's career as an isometric city block"}


def build_night(shared):
    dark = Image.open(SC / "night-dark.webp").convert("RGB")
    defs = [base_def(dark, 72), GLOW, FF,
            '<filter id="hk-night" x="-30%" y="-30%" width="160%" height="160%"><feColorMatrix type="matrix" values=".66 0 0 0 0  0 .66 0 0 0  0 0 .62 0 0  0 0 0 1 0"/><feDropShadow dx="0" dy="1.5" stdDeviation="0.8" flood-color="#000" flood-opacity=".5"/></filter>',
            '<filter id="hb-f" x="-30%" y="-30%" width="160%" height="160%"><feColorMatrix type="matrix" values=".8 0 0 0 .02  0 .76 0 0 .01  0 0 .74 0 .02  0 0 0 1 0"/><feDropShadow dx="0" dy="2" stdDeviation="1.6" flood-color="#000" flood-opacity=".55"/></filter>']
    css, under, life = [], [], []
    lights = light_layers(dark)
    c, b = fireflies([(270, 470), (330, 520), (470, 560), (560, 470), (640, 520), (760, 470), (820, 520), (930, 520), (1050, 500),
                      (1110, 440), (900, 610), (520, 610), (700, 420), (380, 600), (1000, 600), (620, 400)], start=6)
    css += c; life += b
    d, c, b = lanterns({0, 1, 2})
    defs += d; css += c; life += b
    d, c, b = haki(("lantern", "sleepy"), "hk-night", shared)
    defs += d; css += c; life.append(b)
    theme = {"bg": "#141c47", "ink": "#f8e8c6", "ink2": "#e6c48c", "halo": "#0b1030", "halo_op": ".85",
             "plate": "#22284f", "plate_stroke": "#c79a55", "plate_ink": "#f8e8c6", "fog": "#28305e", "glow": "#ffc35a",
             "light_op": "1", "string_op": "1", "spill_op": "1"}
    return {"theme": theme, "backdrop": backdrop(dark), "defs": defs, "css": css, "under": under, "lights": lights, "life": life,
            "title": "The Kathmandu Block at night: Manish Chalise's career as an isometric city block"}


# ---------------------------------------------------------------- common: intro, pins, title, greeting
PIN_ANCHOR = {"ku": (222, 210), "eb": (560, 76), "fgd": (470, 334), "investready": (958, 336), "whitehat": (410, 220),
              "zenledger": (655, 426), "bats": (795, 504), "freelance": (885, 104), "gurkha": (1140, 190)}
PIN_ORG = {"freelance": "Independent", "whitehat": "WhiteHat", "fgd": "First Global Data"}
BUBBLE_L1, BUBBLE_L2, NAMASTE = "Namaste!", "Walk the block →", "नमस्ते"
TITLE, SUBLINE = "Manish Chalise", "Engineer · Kathmandu"


def build_common(shared):
    polys, st = hotspots(), stops()
    ascii_ = "".join(chr(c) for c in range(32, 127)) + "·→–"
    fr = Font(FONTS / "Fraunces.woff2", "Fr", TITLE, {"wght": 620, "opsz": 72})
    it = Font(FONTS / "InterTight.woff2", "It", ascii_, {"wght": 620})
    deva = Font(SYS_DEVA, "Dv", NAMASTE, None, ["*"]) if SYS_DEVA.exists() else None
    fonts = fr.css() + it.css() + (deva.css() if deva else "")

    defs, css, body = [], [], {}
    defs.append('<filter id="popglow" x="-10%" y="-10%" width="120%" height="120%"><feGaussianBlur stdDeviation="3"/></filter>')
    defs.append('<filter id="fogblur" x="-50%" y="-50%" width="200%" height="200%"><feGaussianBlur stdDeviation="34"/></filter>')
    defs.append('<filter id="pinsh" x="-20%" y="-30%" width="140%" height="170%"><feDropShadow dx="0" dy="2" stdDeviation="1.6" flood-color="#1a0f06" flood-opacity=".28"/></filter>')
    defs.append('<filter id="halo" x="-10%" y="-30%" width="120%" height="160%"><feMorphology in="SourceAlpha" operator="dilate" radius="2.2" result="d"/><feGaussianBlur in="d" stdDeviation="3.5" result="b"/><feFlood class="halo-c"/><feComposite in2="b" operator="in" result="h"/><feMerge><feMergeNode in="h"/><feMergeNode in="SourceGraphic"/></feMerge></filter>')

    # rise: the whole block climbs out of its own blur
    css.append(f"@keyframes rise{{0%{{opacity:0;transform:translateY(54px);filter:blur(7px)}}35%{{opacity:1}}100%{{opacity:1;transform:none;filter:blur(0)}}}}")
    css.append(f".rise{{animation:rise {T_RISE}s cubic-bezier(.2,.75,.25,1) both}}")
    css.append("@keyframes fog{0%{opacity:1;transform:translateY(0)}100%{opacity:0;transform:translateY(-120px)}}")
    x, y, w, h = VB
    body["fog"] = (f'<g class="fog" opacity="0" style="animation:fog 2.6s ease-out .1s both" filter="url(#fogblur)">'
                   f'<ellipse class="fog-c" cx="420" cy="690" rx="420" ry="120"/><ellipse class="fog-c" cx="980" cy="700" rx="460" ry="130"/>'
                   f'<ellipse class="fog-c" cx="700" cy="560" rx="520" ry="150" opacity=".8"/></g>')

    # pops: same image, clipped to each building, bounced from its base
    css.append("@keyframes pop{0%{opacity:1;transform:scale(1)}38%{transform:scale(1.065) translateY(-4px)}68%{transform:scale(.988)}88%{transform:scale(1.006)}99%{opacity:1;transform:scale(1)}100%{opacity:0;transform:scale(1)}}")
    css.append("@keyframes popglow{0%{opacity:0}30%{opacity:.6}100%{opacity:0}}")
    pops, pins = [], []
    css.append("@keyframes pin-in{0%{opacity:0;transform:translateY(14px) scale(.8)}60%{opacity:1;transform:translateY(-3px) scale(1.03)}100%{opacity:1;transform:none}}")
    css.append("@keyframes pin-out{to{opacity:0;transform:translateY(-8px)}}")
    for i, sid in enumerate(POP_ORDER):
        poly = polys[sid]
        pts = " ".join(f"{px},{py}" for px, py in poly)
        ox = sum(p[0] for p in poly) / len(poly)
        oy = max(p[1] for p in poly)
        t = T_POP0 + i * T_POPD
        defs.append(f'<clipPath id="cp-{sid}"><polygon points="{pts}"/></clipPath>')
        loc = " ".join(f"{f2(px - ox)},{f2(py - oy)}" for px, py in poly)
        pops.append(f'<g transform="translate({f2(ox)} {f2(oy)})"><g opacity="0" style="animation:pop {T_POPLEN}s cubic-bezier(.3,.6,.3,1) {f2(t)}s both;transform-origin:0 0">'
                    f'<g transform="translate({f2(-ox)} {f2(-oy)})" clip-path="url(#cp-{sid})"><use href="#base"/></g>'
                    f'<polygon points="{loc}" class="glow-s" fill="none" stroke-width="4.5" stroke-linejoin="round" filter="url(#popglow)" opacity="0" style="animation:popglow {T_POPLEN + .2}s ease-out {f2(t)}s both"/>'
                    f'</g></g>')
        year, org = st[sid]
        org = PIN_ORG.get(sid, org)
        ax, ay = PIN_ANCHOR[sid]
        fs = 15
        tw = it.width(f"{year} · {org}", fs)
        bw, bh = tw + 22, 27
        bx = min(max(ax - bw / 2, x + 8), x + w - 8 - bw)
        by = ay - 15 - bh
        pins.append(f'<g opacity="0" style="animation:pin-in .55s cubic-bezier(.3,.7,.3,1.3) {f2(t + .18)}s both"><g style="animation:pin-out .5s ease-in {f2(T_PINOUT)}s forwards">'
                    f'<g filter="url(#pinsh)"><line x1="{ax}" y1="{f2(by + bh)}" x2="{ax}" y2="{ay - 3}" class="pin-stem" stroke-width="1.6"/>'
                    f'<circle cx="{ax}" cy="{ay - 2}" r="3" class="pin-dot"/>'
                    f'<rect x="{f2(bx)}" y="{f2(by)}" width="{f2(bw)}" height="{bh}" rx="6" class="pin-box" stroke-width="1.3"/></g>'
                    f'<text x="{f2(bx + bw / 2)}" y="{f2(by + 18.6)}" text-anchor="middle" class="pin-t"><tspan class="pin-y">{year}</tspan> · {org}</text></g></g>')
    body["pops"] = "".join(pops)
    body["pins"] = "".join(pins)
    css.append(".pin-t{font:600 15px It,sans-serif;fill:#2a1c11}.pin-y{fill:#b0451c}.pin-box{fill:#fff7e6;stroke:#8d5f33}.pin-stem{stroke:#8d5f33}.pin-dot{fill:#b0451c}")

    # title: letter by letter
    tx, ty, tsz = 124, 92, 46
    letters, cx = [], tx
    for j, ch in enumerate(TITLE):
        if ch != " ":
            letters.append(f'<text x="{f2(cx)}" y="{ty}" class="tl" style="animation-delay:{f2(T_TITLE + j * .055)}s">{ch}</text>')
        cx += fr.adv[ch] * tsz + 0.4
    title_w = cx - tx
    css.append(f"@keyframes tl{{0%{{opacity:0;transform:translateY(22px)}}55%{{opacity:1}}100%{{opacity:1;transform:none}}}}")
    css.append(f".tl{{font:620 {tsz}px Fr,Georgia,serif;animation:tl .7s cubic-bezier(.2,.85,.25,1.25) both}}")
    css.append("@keyframes sub{0%{opacity:0;transform:translateX(-10px)}100%{opacity:1;transform:none}}")
    sub = f'<text x="{tx + 2}" y="{ty + 30}" class="sub" style="animation:sub .7s ease-out {f2(T_TITLE + len(TITLE) * .055 + .1)}s both">{SUBLINE.upper()}</text>'
    css.append(".sub{font:620 14.5px It,sans-serif;letter-spacing:2.6px}")
    body["title"] = f'<g filter="url(#halo)"><g class="ink">{"".join(letters)}</g><g class="ink2">{sub}</g></g>'
    print(f"  title width ≈ {title_w:.0f}px (x {tx}–{tx + title_w:.0f})")

    # Haki's greeting, bottom-right corner
    wave, nam = shared["hk-wave"], shared["hk-namaste"]
    defs += [image_def(wave), image_def(nam)]
    css += [strip_kf(wave), strip_kf(nam)]
    fx, fy, dw = 1226, 744, 170           # feet + drawn cell size
    sx, sy = fx - dw / 2, fy - dw * 54.7 / 60
    css.append("@keyframes hb-in{0%{opacity:0;transform:translateY(16px) scale(.55)}55%{opacity:1;transform:translateY(-6px) scale(1.07)}80%{transform:scale(.98)}100%{opacity:1;transform:none}}")
    pc = lambda s: f2(s / CYCLE * 100) + "%"
    css.append(f"@keyframes cy-a{{0%,{pc(6.8)}{{opacity:1}}{pc(7.15)},{pc(13.55)}{{opacity:0}}100%{{opacity:1}}}}")
    css.append(f"@keyframes cy-b{{0%,{pc(6.95)}{{opacity:0}}{pc(7.35)},{pc(13.3)}{{opacity:1}}{pc(13.6)},100%{{opacity:0}}}}")
    cyc = lambda k: f"animation:{k} {CYCLE}s linear {T_CYCLE0}s infinite both"
    body["haki"] = (f'<g transform="translate({fx} {fy})"><g style="animation:hb-in .8s cubic-bezier(.3,.7,.3,1) {T_HAKI}s both;transform-origin:0 0">'
                    f'<ellipse cx="0" cy="-3" rx="38" ry="7" fill="#1a0e05" opacity=".16"/>'
                    f'<g filter="url(#hb-f)" transform="translate({-fx} {-fy})">'
                    f'<g style="{cyc("cy-a")}">{sprite_use(wave, sx, sy, dw, wave["n"] / 12)}</g>'
                    f'<g opacity="0" style="{cyc("cy-b")}">{sprite_use(nam, sx, sy, dw, nam["n"] / 12)}</g></g></g></g>')

    # speech bubble: typed English, then नमस्ते (Haki switches to namaste)
    f1, f2_ = 17.5, 16
    w1, w2 = it.width(BUBBLE_L1, f1), it.width(BUBBLE_L2, f2_)
    pad = 13
    bw = max(w1, w2) + pad * 2 + 4
    bh = 62
    tail = (fx - 30, sy + 62)          # tip near Haki's cheek
    bx1 = tail[0] - 14
    bx0, by0 = bx1 - bw, tail[1] - bh + 6
    tx0 = bx0 + pad
    l1y, l2y = by0 + 25, by0 + 47
    defs.append(f'<clipPath id="tl1"><rect x="{f2(tx0 - 1)}" y="{f2(l1y - 15)}" width="{f2(w1 + 8)}" height="20"/></clipPath>')
    defs.append(f'<clipPath id="tl2"><rect x="{f2(tx0 - 1)}" y="{f2(l2y - 14)}" width="{f2(w2 + 8)}" height="20"/></clipPath>')

    def type_kf(name, text, size, t0):
        ks, acc = [(0, 0.0)], 0.0
        for j, ch in enumerate(text):
            acc += it.adv.get(ch, .55) * size
            ks.append((t0 + (j + 1) * .065, acc + (6 if j == len(text) - 1 else 0)))
        tend = ks[-1][0]
        rows = [f"{pc(t)}{{transform:translateX({f2(v)}px)}}" for t, v in ks]
        rows.append(f"{pc(13.62)}{{transform:translateX({f2(acc + 6)}px)}}")
        rows.append(f"{pc(13.64)},100%{{transform:translateX(0)}}")
        return f"@keyframes {name}{{" + "".join(rows) + "}", tend, acc + 6

    k1, e1, full1 = type_kf("ty1", BUBBLE_L1, f1, 0.15)
    k2, e2, full2 = type_kf("ty2", BUBBLE_L2, f2_, e1 + .3)
    css += [k1, k2]
    tyc = lambda k: f"animation:{k} {CYCLE}s steps(1,end) {T_CYCLE0}s infinite both"
    path = (f"M{f2(bx0 + 12)} {f2(by0)}H{f2(bx1 - 12)}Q{f2(bx1)} {f2(by0)} {f2(bx1)} {f2(by0 + 12)}V{f2(tail[1] - 16)}"
            f"L{f2(tail[0])} {f2(tail[1] - 6)}L{f2(bx1)} {f2(tail[1] - 4)}V{f2(by0 + bh - 12)}"
            f"Q{f2(bx1)} {f2(by0 + bh)} {f2(bx1 - 12)} {f2(by0 + bh)}H{f2(bx0 + 12)}Q{f2(bx0)} {f2(by0 + bh)} {f2(bx0)} {f2(by0 + bh - 12)}"
            f"V{f2(by0 + 12)}Q{f2(bx0)} {f2(by0)} {f2(bx0 + 12)} {f2(by0)}Z")
    css.append("@keyframes bub-in{0%{opacity:0;transform:scale(.3)}60%{opacity:1;transform:scale(1.06)}100%{opacity:1;transform:none}}")
    css.append(f".bt1{{font:700 {f1}px It,sans-serif;fill:#2a1c11}}.bt2{{font:600 {f2_}px It,sans-serif;fill:#6b4325}}.bt3{{font:500 28px Dv,sans-serif;fill:#2a1c11}}.bub{{fill:#fffaf0;stroke:#8d5f33}}")
    deva_t = (f'<text x="{f2((bx0 + bx1) / 2)}" y="{f2(by0 + bh / 2 + 10)}" text-anchor="middle" class="bt3">{NAMASTE}</text>' if deva else
              f'<text x="{f2((bx0 + bx1) / 2)}" y="{f2(by0 + bh / 2 + 6)}" text-anchor="middle" class="bt1">Namaste 🙏</text>')
    body["bubble"] = (f'<g transform="translate({f2(tail[0])} {f2(tail[1])})"><g style="animation:bub-in .5s cubic-bezier(.3,.7,.3,1.2) {T_BUBBLE}s both;transform-origin:0 0">'
                      f'<g transform="translate({f2(-tail[0])} {f2(-tail[1])})">'
                      f'<path d="{path}" class="bub" stroke-width="1.4" filter="url(#pinsh)"/>'
                      f'<g style="{cyc("cy-a")}"><text x="{f2(tx0)}" y="{f2(l1y)}" class="bt1">{BUBBLE_L1}</text><text x="{f2(tx0)}" y="{f2(l2y)}" class="bt2">{BUBBLE_L2.replace("→", "&#8594;")}</text>'
                      f'<g clip-path="url(#tl1)"><rect x="{f2(tx0 - 1)}" y="{f2(l1y - 15)}" width="{f2(w1 + 8)}" height="20" class="bub-c" transform="translate({f2(full1)} 0)" style="{tyc("ty1")}"/></g>'
                      f'<g clip-path="url(#tl2)"><rect x="{f2(tx0 - 1)}" y="{f2(l2y - 14)}" width="{f2(w2 + 8)}" height="20" class="bub-c" transform="translate({f2(full2)} 0)" style="{tyc("ty2")}"/></g></g>'
                      f'<g opacity="0" style="{cyc("cy-b")}">{deva_t}</g></g></g></g>')
    css.append(".bub-c{fill:#fffaf0}")

    # clock sign appears with the title
    css.append("@keyframes sign-in{0%{opacity:0;transform:translateY(-14px) rotate(-3deg)}70%{opacity:1;transform:translateY(2px) rotate(1deg)}100%{opacity:1;transform:none}}")
    css.append(".ck1{font:700 16px It,sans-serif}.ck2{font:600 13px It,sans-serif;letter-spacing:.2px}")
    return {"fonts": fonts, "defs": defs, "css": css, "body": body,
            "adv": {c: round(v, 4) for c, v in it.adv.items()},
            "timeline": {"lights": T_LIGHTS, "sign": T_TITLE + 1.3, "pops_end": T_POP0 + T_POPD * len(POP_ORDER) + T_POPLEN},
            "vb": VB, "has_deva": bool(deva)}


def main():
    BAKE.mkdir(exist_ok=True)
    CACHE.mkdir(exist_ok=True)
    only = [a for a in sys.argv[1:] if not a.startswith("--")]
    shared = {"hk-wave": sprite_defs("hk-wave", SC / "haki" / "wave.webp", q=76),
              "hk-namaste": sprite_defs("hk-namaste", SC / "haki" / "namaste.webp", q=76)}
    jobs = {"common": lambda: build_common(shared), "day": lambda: build_day(shared),
            "dusk": lambda: build_dusk(shared), "night": lambda: build_night(shared)}
    for name, fn in jobs.items():
        if only and name not in only:
            continue
        print(f"baking {name}…")
        data = fn()
        p = BAKE / f"{name}.json"
        p.write_text(json.dumps(data, ensure_ascii=False, separators=(",", ":")))
        print(f"  {p.relative_to(ROOT)}: {p.stat().st_size // 1024} KB")


if __name__ == "__main__":
    main()
