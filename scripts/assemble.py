#!/usr/bin/env python3
"""Stitch the animated profile banner from the baked fragments in bake/ (stdlib only).

  python3 scripts/assemble.py --mode night --clock "9 pm" --contrib contrib.json --out out/banner.svg
  python3 scripts/assemble.py --all-previews      # assets/preview-{day,dusk,night}.svg

--mode     day | dusk | night
--clock    label for the little sign, e.g. "9 pm" (→ "9 pm in Kathmandu"); omitted → generic
--contrib  JSON {"active_days", "days_in_window", "busiest_day", "busiest_count", "total"}:
           window rings lit ∝ active_days/days_in_window (min 2), bulb strings twinkle harder
           the busier the busiest day. Missing → everything lit.
Re-bake (scripts/bake.py, needs Pillow) only when the art changes.
"""
import argparse, json, re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MODES = ("day", "dusk", "night")


def f2(v):
    return f"{v:.2f}".rstrip("0").rstrip(".")


def esc(s):
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")


def load(bake, name):
    return json.loads((bake / f"{name}.json").read_text())


def read_contrib(path):
    if not path:
        return None
    p = Path(path)
    if not p.exists():
        return None
    try:
        c = json.loads(p.read_text())
        # live.py writes a fully-lit fallback when the API fails: light everything, but no fake "N active days" line
        return c if isinstance(c, dict) and not c.get("fallback") else None
    except (ValueError, OSError):
        return None


def contrib_line(c):
    n, days = int(c.get("active_days") or 0), int(c.get("days_in_window") or 0)
    unit = "day" if n == 1 else "days"
    if 28 <= days <= 31:
        return f"{n} active {unit} this month"
    if days == 7:
        return f"{n} active {unit} this week"
    if days:
        return f"{n} of {days} days shipping"
    return f"{n} active {unit}"


def clock_hour(label):
    m = re.match(r"\s*(\d{1,2})(?::(\d\d))?\s*([ap])?", label or "", re.I)
    if not m:
        return None
    h, mi = int(m.group(1)) % 12, int(m.group(2) or 0)
    return h, mi


def sign(common, th, clock, contrib, mode):
    adv = common["adv"]
    width = lambda s, size: sum(adv.get(ch, .55) for ch in s) * size
    x, y, w, h = common["vb"]
    if clock:
        l1 = clock if "kathmandu" in clock.lower() else f"{clock} in Kathmandu"
    else:
        l1 = {"day": "Daytime in Kathmandu", "dusk": "Dusk in Kathmandu", "night": "Night in Kathmandu"}[mode]
    l2 = contrib_line(contrib) if contrib else None
    tw = max(width(l1, 16), width(l2, 13) if l2 else 0)
    pw, ph = tw + 52, (52 if l2 else 34)
    right, top = x + w - 22, y + 30
    px = right - pw
    hm = clock_hour(clock) if clock else None
    icon_cx, icon_cy = px + 18, top + ph / 2
    hands = ""
    if hm:
        a_h = (hm[0] + hm[1] / 60) * 30
        a_m = hm[1] * 6
        hands = (f'<line x1="0" y1="0" x2="0" y2="-4.2" transform="rotate({f2(a_h)})" class="ck-h" stroke-width="1.6" stroke-linecap="round"/>'
                 f'<line x1="0" y1="0" x2="0" y2="-6" transform="rotate({f2(a_m)})" class="ck-h" stroke-width="1.2" stroke-linecap="round"/>')
    else:
        hands = '<line x1="0" y1="0" x2="0" y2="-4.2" class="ck-h" stroke-width="1.6" stroke-linecap="round"/><line x1="0" y1="0" x2="4.6" y2="0" class="ck-h" stroke-width="1.2" stroke-linecap="round"/>'
    hx = px + pw / 2
    t = common["timeline"]["sign"]
    txt = f'<text x="{f2(px + 34)}" y="{f2(top + (21 if l2 else 22.5))}" class="ck1">{esc(l1)}</text>'
    if l2:
        txt += f'<text x="{f2(px + 34)}" y="{f2(top + 40)}" class="ck2">{esc(l2)}</text>'
    return (f'<g transform="translate({f2(hx)} {y})"><g style="animation:sign-in .9s cubic-bezier(.3,.7,.3,1.2) {f2(t)}s both;transform-origin:0 0">'
            f'<g transform="translate({f2(-hx)} {-y})">'
            f'<line x1="{f2(px + 16)}" y1="{y}" x2="{f2(px + 16)}" y2="{top + 3}" class="ck-str" stroke-width="1.3"/>'
            f'<line x1="{f2(right - 16)}" y1="{y}" x2="{f2(right - 16)}" y2="{top + 3}" class="ck-str" stroke-width="1.3"/>'
            f'<rect x="{f2(px)}" y="{top}" width="{f2(pw)}" height="{ph}" rx="8" class="ck-plate" stroke-width="1.4" filter="url(#pinsh)"/>'
            f'<circle cx="{f2(px + 16)}" cy="{top + 3}" r="1.8" class="ck-nail"/><circle cx="{f2(right - 16)}" cy="{top + 3}" r="1.8" class="ck-nail"/>'
            f'<g transform="translate({f2(icon_cx)} {f2(icon_cy)})"><circle r="8.5" class="ck-face" stroke-width="1.4"/>{hands}</g>'
            f'{txt}</g></g></g>'), [
        f".ck-plate{{fill:{th['plate']};stroke:{th['plate_stroke']}}}.ck-str{{stroke:{th['plate_stroke']}}}.ck-nail{{fill:{th['plate_stroke']}}}",
        f".ck-face{{fill:none;stroke:{th['plate_ink']}}}.ck-h{{stroke:{th['plate_ink']}}}.ck1{{fill:{th['plate_ink']}}}.ck2{{fill:{th['ink2'] if mode != 'night' else th['ink2']}}}",
    ]


def lights(m, common, contrib):
    th = m["theme"]
    ls = m["lights"]
    if not ls:
        return "", []
    rings = sorted([l for l in ls if l["kind"] == "ring"], key=lambda l: int(l["gid"][1:]))
    frac, inten = 1.0, 1.0
    if contrib:
        days = max(1, int(contrib.get("days_in_window") or 30))
        frac = min(1.0, max(0.0, int(contrib.get("active_days") or 0) / days))
        inten = min(1.0, max(0.3, int(contrib.get("busiest_count") or 0) / 10))
    lit = len(rings) if not contrib else max(2, min(len(rings), round(len(rings) * frac)))
    t0 = common["timeline"]["lights"]
    css = ["@keyframes on{0%{opacity:0}35%{opacity:.75}45%{opacity:.4}100%{opacity:1}}",
           f"@keyframes tw{{0%,100%{{opacity:1}}50%{{opacity:{f2(1 - .6 * inten)}}}}}"]
    out = [f'<g opacity="{th.get("light_op", "1")}">']
    for i, l in enumerate(rings[:lit]):
        css.append(f".{l['gid']}{{animation:on 1.1s ease-out {f2(t0 + i * .26)}s both}}")
        out.append(l["svg"])
    out.append("</g>")
    for l in ls:
        if l["kind"] == "spill":
            op = float(th.get("spill_op", 1)) * (.3 + .7 * (lit / len(rings)))
            out.append(f'<g opacity="{f2(op)}">{l["svg"]}</g>')
            css.append(f".sp{{animation:on 3s ease-in-out {f2(t0)}s both}}")
    sop = float(th.get("string_op", 1)) * (.55 + .45 * inten)
    out.append(f'<g opacity="{f2(sop)}">')
    for l in ls:
        if l["kind"] == "string":
            out.append(l["svg"])
    out.append("</g>")
    css.append(f".sa{{animation:on 1s ease-out {f2(t0 + 1)}s both,tw {f2(2.8 - inten)}s ease-in-out {f2(t0 + 2.2)}s infinite}}")
    css.append(f".sb{{animation:on 1s ease-out {f2(t0 + 1.6)}s both,tw {f2(3.6 - inten)}s ease-in-out {f2(t0 + 3)}s infinite}}")
    return "".join(out), css


def build(mode, clock=None, contrib=None, bake=ROOT / "bake"):
    common, m = load(bake, "common"), load(bake, mode)
    th = m["theme"]
    x, y, w, h = common["vb"]
    body = common["body"]
    light_svg, light_css = lights(m, common, contrib)
    sign_svg, sign_css = sign(common, th, clock, contrib, mode)
    theme_css = [f".ink{{fill:{th['ink']}}}.ink2{{fill:{th['ink2']}}}.halo-c{{flood-color:{th['halo']};flood-opacity:{th['halo_op']}}}",
                 f".fog-c{{fill:{th['fog']}}}.glow-s{{stroke:{th['glow']}}}"]
    style = "\n".join([common["fonts"], *common["css"], *m["css"], *light_css, *theme_css, *sign_css,
                       "svg *{transform-box:view-box}",
                       "@media (prefers-reduced-motion:reduce){*{animation:none!important}}"])
    title = m["title"]
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="{x} {y} {w} {h}" width="{w}" height="{h}" role="img" aria-label="{esc(title)}">'
            f'<title>{esc(title)}</title><style>{style}</style>'
            f'<defs><clipPath id="frame"><rect x="{x}" y="{y}" width="{w}" height="{h}" rx="18"/></clipPath>{"".join(common["defs"])}{"".join(m["defs"])}</defs>'
            f'<g clip-path="url(#frame)"><rect x="{x}" y="{y}" width="{w}" height="{h}" fill="{th["bg"]}"/>{m["backdrop"]}'
            f'<g class="rise"><use href="#base"/>{body["pops"]}{"".join(m["under"])}{light_svg}{"".join(m["life"])}</g>'
            f'{body["fog"]}{body["pins"]}{body["title"]}{body["haki"]}{body["bubble"]}{sign_svg}</g></svg>')


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--mode", choices=MODES, default="day")
    ap.add_argument("--clock", default=None)
    ap.add_argument("--contrib", default=None)
    ap.add_argument("--bake", default=str(ROOT / "bake"))
    ap.add_argument("--out", default=str(ROOT / "out" / "banner.svg"))
    ap.add_argument("--all-previews", action="store_true")
    a = ap.parse_args()
    bake = Path(a.bake)
    contrib = read_contrib(a.contrib)
    if a.all_previews:
        for mode in MODES:
            p = ROOT / "assets" / f"preview-{mode}.svg"
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(build(mode, None, contrib, bake))
            print(f"{p.relative_to(ROOT)}: {p.stat().st_size / 1024:.0f} KB")
        return
    out = Path(a.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(build(a.mode, a.clock, contrib, bake))
    print(f"{out}: {out.stat().st_size / 1024:.0f} KB")


if __name__ == "__main__":
    main()
