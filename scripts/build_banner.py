#!/usr/bin/env python3
"""Build the animated day/night banners for the GitHub profile README.

Reads the Kathmandu Block assets from ../personal_portfolio_page and writes
self-contained SVGs (all images inlined as webp data URIs) to assets/:
  assets/day.svg    light theme: clouds, doves, butterfly, Haki (Habre Care's red panda) strolling
  assets/night.svg  dark theme: window-by-window dusk, twinkling strings,
                    fireflies, sky lanterns, Haki with his lantern

GitHub renders README SVGs as <img>, so no JS and no external files:
everything is CSS keyframes inside the SVG. Re-run after the scene changes:
  python3 scripts/build_banner.py
"""
import base64, io, json, math, random, re
from pathlib import Path
from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
SITE = ROOT.parent / "personal_portfolio_page"
SC = SITE / "public" / "scene"
OUT = ROOT / "assets"
OUT.mkdir(exist_ok=True)
random.seed(108)

W, H = 1408, 768                     # scene render px (site coords)
VB = (96, 28, 1216, 728)             # banner crop (x, y, w, h)
HAKI_K = 1.3                         # Haki a touch bigger than on the site so he reads at README width


def webp(im, q=80, **kw):
    b = io.BytesIO()
    im.save(b, "WEBP", quality=q, method=6, **kw)
    return b.getvalue()


def uri(data):
    return "data:image/webp;base64," + base64.b64encode(data).decode()


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


# ---------------------------------------------------------------- sprites
def sprite_defs(name, path, size=None, q=78):
    fs = frames(path, size)
    s = strip(fs)
    w, h = fs[0].size
    return {"id": name, "n": len(fs), "w": w, "h": h, "uri": uri(webp(s, q, alpha_quality=90)), "bytes": None}


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


# ---------------------------------------------------------------- Haki
NODES = {  # lane graph nodes from the site (src/actors.ts), render px
    "investready": (842, 470), "plaza-f": (770, 440), "plaza-r": (800, 352),
    "freelance": (815, 300), "lane-b": (757, 305),
}
ROUTE = ["investready", "plaza-f", "plaza-r", "freelance", "lane-b"]
SPEED = 46  # px/s, same stroll speed as the site
ROWS = {"down": 0, "side": 1, "up": 2}


def haki(night):
    """Haki strolls InvestReady → plaza → rooftop studio → back lane and back, posing at each end."""
    sheet = Image.open(SC / "haki" / "walk.webp").convert("RGBA")       # 9 cols × 3 rows of 140×145 (down · side · up)
    walks = {}
    for name, r in ROWS.items():
        row = sheet.crop((140, 145 * r, 140 * 9, 145 * (r + 1)))       # cols 1..8
        walks[name] = {"id": f"hk-{name}", "n": 8, "w": 140, "h": 145, "uri": uri(webp(row, 80, alpha_quality=90))}
    poses = ("lantern", "sleepy") if night else ("wave", "namaste")
    ps = [sprite_defs(f"hk-{p}", SC / "haki" / f"{p}.webp", q=76) for p in poses]

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
        if sg[2] == "pose":
            pos_kf += [(sg[0], sg[4]), (sg[1], sg[4])]
        else:
            pos_kf += [(sg[0], sg[3][0]), (sg[1], sg[3][1])]
    move = "@keyframes hk-move{" + "".join(
        f"{pct(tt)}{{transform:translate({f2(x)}px,{f2(y)}px)}}" for tt, (x, y) in pos_kf) + "}"

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
           *[strip_kf(w) for w in walks.values()], *[strip_kf(p) for p in ps]]
    for cls, kf in [("hk", "hk-move"), ("hk-face", "hk-face"), ("hk-p0", "hk-p0"), ("hk-p1", "hk-p1"),
                    *[(f"hk-{r}", f"hk-v-{r}") for r in ROWS]]:
        css.append(f".{cls}{{animation:{kf} {f2(T)}s linear infinite}}")
    k = HAKI_K
    step_dur = 8 / (SPEED / 7.5)          # site: one frame per 7.5px walked
    flt = ' filter="url(#hk-night)"' if night else ' filter="url(#hk-shadow)"'
    x0, y0 = NODES[ROUTE[0]]
    # walk cell drawn 50.2×52 at feet (-25.1,-51.3); pose 60×60 at (-30,-54.7)  (site styles.css)
    body = (f'<g class="hk" transform="translate({x0} {y0})"><g transform="scale({k})"{flt}><g class="hk-face">'
            + "".join(f'<g class="hk-{r}" opacity="0">{sprite_use(walks[r], -25.1, -51.3, 50.2, step_dur)}</g>' for r in ROWS)
            + f'</g><g class="hk-p0">{sprite_use(ps[0], -30, -54.7, 60, ps[0]["n"] / 12)}</g>'
            f'<g class="hk-p1" opacity="0">{sprite_use(ps[1], -30, -54.7, 60, ps[1]["n"] / 12)}</g>'
            f'</g></g>')
    defs = [*[image_def(w) for w in walks.values()], *[image_def(p) for p in ps]]
    return defs, css, body


# ---------------------------------------------------------------- day
def build_day():
    base = Image.open(SC / "day.webp").convert("RGB")                  # 2816×1536
    defs, css, body = [], [], []
    defs.append('<filter id="hk-shadow" x="-30%" y="-30%" width="160%" height="160%"><feDropShadow dx="0" dy="1.5" stdDeviation="0.8" flood-color="#28190a" flood-opacity=".3"/></filter>')
    defs.append('<filter id="soft" x="-20%" y="-20%" width="140%" height="140%"><feDropShadow dx="0" dy="5" stdDeviation="2.5" flood-color="#3c2814" flood-opacity=".16"/></filter>')
    body.append(f'<image width="{W}" height="{H}" href="{uri(webp(base, 74))}"/>')

    # two small clouds high in the sky (bigger ones covered the rooftops)
    clouds = [("cloud-1", 230, 30, 110, 15), ("cloud-4", 190, 58, 140, 85)]
    for i, (name, w, y, dur, off) in enumerate(clouds):
        im = Image.open(SC / f"{name}.webp").convert("RGBA")
        h = w * im.height / im.width
        im = im.resize((w * 2, round(h * 2)), Image.LANCZOS)
        defs.append(f'<image id="cl{i}" width="{w}" height="{f2(h)}" href="{uri(webp(im, 70, alpha_quality=80))}"/>')
        css.append(f".cl{i}{{animation:drift {dur}s linear {-off}s infinite}}")
        body.append(f'<g transform="translate(0 {y})"><use href="#cl{i}" class="cl{i}" opacity=".72"/></g>')
    css.append(f"@keyframes drift{{from{{transform:translateX({VB[0] - 380}px)}}to{{transform:translateX({VB[0] + VB[2] + 20}px)}}}}")

    # dove flock: crosses the sky every ~24s
    dove = sprite_defs("dove", SC / "dove.webp", (56, 61), q=80)
    defs.append(image_def(dove)); css.append(strip_kf(dove))
    flock = []
    for i in range(6):
        y = 70 + random.random() * 120 + (i % 3) * 18
        s = 0.8 + random.random() * 0.4
        lag = i * 0.55 + random.random() * 0.4
        flock.append((y, s, lag))
    css.append(f"@keyframes fly{{0%{{transform:translateX({VB[0] - 80}px)}}55%{{transform:translateX({VB[0] + VB[2] + 80}px)}}100%{{transform:translateX({VB[0] + VB[2] + 80}px)}}}}")
    css.append("@keyframes bob{0%,100%{transform:translateY(0)}50%{transform:translateY(-7px)}}")
    for i, (y, s, lag) in enumerate(flock):
        body.append(f'<g transform="translate(0 {f2(y)})"><g style="animation:fly 26s linear {f2(-2 + lag)}s infinite"><g style="animation:bob {f2(2.6 + i * .3)}s ease-in-out infinite">'
                    f'<g transform="scale({f2(s)})" filter="url(#soft)">{sprite_use(dove, -14, -15, 28, 0.9, delay=random.random())}</g></g></g></g>')

    # butterfly looping around the KU flower beds
    bf = sprite_defs("bf", SC / "fx" / "butterfly.webp", (36, 26), q=80)
    defs.append(image_def(bf)); css.append(strip_kf(bf))
    cx, cy = 300, 405
    pts = []
    for j in range(13):
        a = j / 12 * 2 * math.pi
        pts.append((cx + 46 * math.sin(a), cy - 22 * math.sin(2 * a) - 10 * math.cos(a)))
    css.append("@keyframes bf-path{" + "".join(f"{f2(j / 12 * 100)}%{{transform:translate({f2(x)}px,{f2(y)}px)}}" for j, (x, y) in enumerate(pts)) + "}")
    body.append(f'<g style="animation:bf-path 14s ease-in-out infinite">{sprite_use(bf, -9, -7, 18, 1.2)}</g>')

    d, c, b = haki(False)
    defs += d; css += c; body.append(b)
    return defs, css, body, "#f2ede4"


# ---------------------------------------------------------------- night
def build_night():
    dark = Image.open(SC / "night-dark.webp").convert("RGB")           # unlit, 2816×1536
    atlas = Image.open(SC / "lights.webp").convert("RGB")
    src = (SITE / "src" / "lights.generated.ts").read_text()
    lights = json.loads(re.search(r"LIGHTS = (\[.*?\])(?: as const)?;", src, re.S).group(1))
    defs, css, body = [], [], []
    defs.append('<filter id="hk-night" x="-30%" y="-30%" width="160%" height="160%"><feColorMatrix type="matrix" values=".66 0 0 0 0  0 .66 0 0 0  0 0 .62 0 0  0 0 0 1 0"/><feDropShadow dx="0" dy="1.5" stdDeviation="0.8" flood-color="#000" flood-opacity=".5"/></filter>')
    defs.append('<filter id="glow" x="-150%" y="-150%" width="400%" height="400%"><feGaussianBlur in="SourceGraphic" stdDeviation="6" result="b"/><feColorMatrix in="b" type="matrix" values="1 0 0 0 .25  0 .8 0 0 .1  0 0 .4 0 0  0 0 0 1.2 0" result="g"/><feMerge><feMergeNode in="g"/><feMergeNode in="SourceGraphic"/></feMerge></filter>')
    defs.append('<radialGradient id="ff"><stop offset="0" stop-color="#fff6b0"/><stop offset=".35" stop-color="#ffd84a" stop-opacity=".85"/><stop offset="1" stop-color="#ffb000" stop-opacity="0"/></radialGradient>')
    body.append(f'<image width="{W}" height="{H}" href="{uri(webp(dark, 72))}"/>')

    # light groups: windows light up in rings out from the stupa (the site's dusk),
    # bulb strings get two alternating twinkle groups
    import numpy as np
    D = np.asarray(dark, dtype=np.float32)
    A = np.asarray(atlas, dtype=np.float32)
    windows = sorted([l for l in lights if l["kind"] not in ("string", "spill")], key=lambda l: l["d"])
    spill = [l for l in lights if l["kind"] == "spill"]
    strings = [l for l in lights if l["kind"] == "string"]
    RINGS = 6
    groups = [(f"r{i}", windows[i * len(windows) // RINGS:(i + 1) * len(windows) // RINGS]) for i in range(RINGS)]
    random.shuffle(strings)
    groups += [("sp", spill), ("sa", strings[0::2]), ("sb", strings[1::2])]
    total = 0
    for gid, ls in groups:
        L = np.zeros_like(D)
        for l in ls:
            x, y, w, h, ax, ay = (l[k] for k in ("x", "y", "w", "h", "ax", "ay"))
            x2, y2 = min(x + w, D.shape[1]), min(y + h, D.shape[0])
            L[y:y2, x:x2] += A[ay:ay + (y2 - y), ax:ax + (x2 - x)]
        L = np.minimum(L, 255)
        # additive light as plain alpha-over: out = dark + o·L  ⇔  a = max(L)/255, C = dark + L/a
        a = L.max(axis=2) / 255.0
        a3 = np.where(a > 1e-3, a, 1)[..., None]
        C = np.clip(D + L / a3, 0, 255)
        rgba = np.dstack([C, a * 255]).astype(np.uint8)
        im = Image.fromarray(rgba, "RGBA")
        bb = im.getchannel("A").getbbox()
        if not bb:
            continue
        crop = im.crop(bb)
        data = webp(crop, 78, alpha_quality=85)
        total += len(data)
        x0, y0 = bb[0] / 2, bb[1] / 2
        body.append(f'<image class="lt {gid}" x="{f2(x0)}" y="{f2(y0)}" width="{f2(crop.width / 2)}" height="{f2(crop.height / 2)}" href="{uri(data)}"/>')
    print(f"  light layers: {total // 1024} KB")
    css.append("@keyframes on{0%{opacity:0}35%{opacity:.75}45%{opacity:.4}100%{opacity:1}}")
    css.append("@keyframes tw{0%,100%{opacity:1}50%{opacity:.45}}")
    for i in range(RINGS):
        css.append(f".r{i}{{animation:on 1.1s ease-out {f2(0.25 + i * 0.4)}s both}}")
    css.append(".sp{animation:on 3s ease-in-out .3s both}")
    css.append(".sa{animation:on 1s ease-out 1.4s both,tw 2.8s ease-in-out 2.6s infinite}")
    css.append(".sb{animation:on 1s ease-out 2.1s both,tw 3.6s ease-in-out 3.4s infinite}")

    # fireflies over the lanes and plants
    spots = [(270, 470), (330, 520), (470, 560), (560, 470), (640, 520), (760, 470), (820, 520), (930, 520), (1050, 500),
             (1110, 440), (900, 610), (520, 610), (700, 420), (380, 600), (1000, 600), (620, 400)]
    for i, (x, y) in enumerate(spots):
        pts = [(0, 0)] + [((random.random() - .5) * 44, (random.random() - .5) * 30) for _ in range(3)] + [(0, 0)]
        css.append(f"@keyframes ff{i}{{" + "".join(f"{j * 25}%{{transform:translate({f2(px)}px,{f2(py)}px)}}" for j, (px, py) in enumerate(pts)) + "}")
        dur = 9 + random.random() * 7
        blink = 2.2 + random.random() * 2.4
        body.append(f'<g transform="translate({x} {y})"><g style="animation:ff{i} {f2(dur)}s ease-in-out {f2(-random.random() * dur)}s infinite">'
                    f'<circle r="5" fill="url(#ff)" style="animation:blink {f2(blink)}s ease-in-out {f2(3 + random.random() * 3)}s infinite both"/></g></g>')
    css.append("@keyframes blink{0%,100%{opacity:0}45%{opacity:1}60%{opacity:.85}}")

    # sky lanterns rising from the stupa plaza
    lan = Image.open(SC / "fx" / "lantern-float.webp").convert("RGBA").resize((52, 49), Image.LANCZOS)
    defs.append(f'<image id="lan" width="26" height="24.5" href="{uri(webp(lan, 80, alpha_quality=90))}"/>')
    for i, (x, dur, lag, sway) in enumerate([(700, 30, 0, 26), (760, 36, 12, -20), (640, 33, 22, 18)]):
        css.append(f"@keyframes lan{i}{{0%{{transform:translate(0,0);opacity:0}}6%{{opacity:1}}50%{{transform:translate({sway}px,-230px)}}85%{{opacity:.9}}100%{{transform:translate({-sway * .4}px,-470px);opacity:0}}}}")
        css.append(f"@keyframes sw{i}{{0%,100%{{transform:rotate(-4deg)}}50%{{transform:rotate(4deg)}}}}")
        body.append(f'<g transform="translate({x} 420)"><g style="animation:lan{i} {dur}s linear {f2(-lag + 4)}s infinite both">'
                    f'<g filter="url(#glow)" style="animation:sw{i} 4s ease-in-out infinite"><use href="#lan" x="-13" y="-24.5"/></g></g></g>')

    d, c, b = haki(True)
    defs += d; css += c; body.append(b)
    return defs, css, body, "#141c47"


# ---------------------------------------------------------------- write
def write(name, build, title):
    defs, css, body, bg = build()
    x, y, w, h = VB
    style = "\n".join(css + [
        "svg *{transform-box:view-box}",
        "@media (prefers-reduced-motion:reduce){*{animation:none!important}}",
    ])
    svg = (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="{x} {y} {w} {h}" width="{w}" height="{h}" role="img" aria-label="{title}">'
           f'<title>{title}</title><style>{style}</style>'
           f'<defs><clipPath id="frame"><rect x="{x}" y="{y}" width="{w}" height="{h}" rx="18"/></clipPath>{"".join(defs)}</defs>'
           f'<g clip-path="url(#frame)"><rect x="{x}" y="{y}" width="{w}" height="{h}" fill="{bg}"/>{"".join(body)}</g></svg>')
    p = OUT / name
    p.write_text(svg)
    print(f"{p.relative_to(ROOT)}: {len(svg) / 1024:.0f} KB")


if __name__ == "__main__":
    write("day.svg", build_day, "The Kathmandu Block by day: Manish Chalise's career as an isometric city block")
    write("night.svg", build_night, "The Kathmandu Block at night: Manish Chalise's career as an isometric city block")
