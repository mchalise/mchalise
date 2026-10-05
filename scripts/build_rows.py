#!/usr/bin/env python3
"""Career rows for the GitHub profile README, drawn as SVG so they can use the
site's fonts (Fraunces + Inter Tight). GitHub forces its system font on README text;
an <img> SVG with inlined, subset woff2 is the only way around it.

  assets/rows/<id>-light.svg / <id>-dark.svg   one per chapter, newest first in the README
Icons come from assets/thumbs/<id>.png (written by build_cards.py).
  python3 scripts/build_rows.py
"""
import base64, io, sys
from pathlib import Path
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parent))
import build_cards as bc  # fonts, measuring, wrapping helpers

ROOT = bc.ROOT
OUT = ROOT / "assets" / "rows"
OUT.mkdir(parents=True, exist_ok=True)
THUMBS = ROOT / "assets" / "thumbs"

# newest first; text kept to what src/stops.ts says
ROWS = [
    ("gurkha", "Now", "Gurkha Labs", "Kathmandu", "Chief Technology Officer",
     "A senior studio building for international clients, with AI agents as the amplifier.", None),
    ("freelance", "2024–26", "Independent consultant", "Kathmandu", "Freelance",
     "Web3 concepts, LLM prototypes and product guidance for early founders.", None),
    ("zenledger", "2017–23", "ZenLedger", "Seattle, remote · via WhiteHat", "Founding Engineer & Lead Software Engineer",
     "Joined at MVP, scaled through a $15M Series B. Led a team of up to 15; rewrote the tax engine from Rails to Go: 70% less compute, 60% faster.",
     [("100K+", "customers"), ("$50B+", "assets tracked"), ("10B+", "transaction rows"), ("100+", "exchanges & chains")]),
    ("bats", "Federal", "BATS", "ZenLedger’s government line", "Engineering Lead · crypto forensics",
     "Crypto forensics used by IRS Criminal and Civil Investigation units.", None),
    ("investready", "2015–17", "InvestReady", "Eepos IT", "Freelance developer",
     "Built the investor-eligibility verification platform for online equity investing.", None),
    ("fgd", "2014–15", "First Global Data", "Toronto, remote", "Software Engineer",
     "REST and SOAP services behind cross-border digital money.", None),
    ("eb", "2013–14", "EB Pearls", "Kathmandu", "Web Application Developer",
     "Secure web applications and security audits for government agencies.", None),
    ("ku", "2009–13", "Kathmandu University", "Dhulikhel", "B.E. Computer Engineering",
     "The first brick on the block.", None),
]

THEMES = {
    "light": dict(bg="#fbf7ef", edge="#eadfcb", ink="#2b2622", muted="#7d7168", accent="#b4532f",
                  pill="#f4e3d3", pill_ink="#9a4426", shadow="#6b4a2a", shadow_op=0.18, stat="#f5ecdf"),
    "dark": dict(bg="#121933", edge="#27305c", ink="#f4ede0", muted="#a5adcf", accent="#f3b36a",
                 pill="#2a2d45", pill_ink="#f3b36a", shadow="#000000", shadow_op=0.45, stat="#182042"),
}
W = 880
F = {"org": ("S", 23), "place": ("R", 14), "role": ("B", 15.5), "line": ("R", 14.2), "pill": ("B", 12.5),
     "num": ("S", 17), "lab": ("R", 12)}


def esc(s):
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def thumb_uri(k):
    im = Image.open(THUMBS / f"{k}.png")
    b = io.BytesIO()
    im.save(b, "WEBP", quality=86, alpha_quality=90, method=6)
    return "data:image/webp;base64," + base64.b64encode(b.getvalue()).decode()


def row(i, k, year, org, place, role, line, stats, theme):
    t = THEMES[theme]
    x0 = 118                       # text column
    pill_w = bc.text_w(*F["pill"], year.upper(), 1.2) + 26
    maxw = W - x0 - pill_w - 56
    lines = bc.wrap(line, *F["line"], maxw)
    y = 40
    parts = []
    org_w = bc.text_w(*F["org"], org)
    parts.append(f'<text class="org" x="{x0}" y="{y}">{esc(org)}</text>')
    parts.append(f'<text class="place" x="{bc.f2(x0 + org_w + 10)}" y="{y - 1}">{esc(place)}</text>')
    y += 25
    parts.append(f'<text class="role" x="{x0}" y="{y}">{esc(role)}</text>')
    for ln in lines:
        y += 21
        parts.append(f'<text class="line" x="{x0}" y="{y}">{esc(ln)}</text>')
    if stats:
        y += 16
        sx = x0
        for num, lab in stats:
            w = max(bc.text_w(*F["num"], num), bc.text_w(*F["lab"], lab)) + 24
            parts.append(f'<g class="stat"><rect x="{bc.f2(sx)}" y="{y}" width="{bc.f2(w)}" height="46" rx="10" fill="{t["stat"]}" stroke="{t["edge"]}"/>'
                         f'<text class="num" x="{bc.f2(sx + 12)}" y="{y + 21}">{esc(num)}</text>'
                         f'<text class="lab" x="{bc.f2(sx + 12)}" y="{y + 37}">{esc(lab)}</text></g>')
            sx += w + 8
        y += 46
    H = max(y + 24, 108)
    cy = H / 2
    # year pill (NOW gets a live dot)
    live = year == "Now"
    extra = 14 if live else 0
    px = W - 22 - pill_w - extra
    pill = (f'<g class="pill"><rect x="{bc.f2(px)}" y="{bc.f2(cy - 14)}" width="{bc.f2(pill_w + extra)}" height="28" rx="14" fill="{t["pill"]}"/>'
            + (f'<circle class="dot" cx="{bc.f2(px + 14)}" cy="{bc.f2(cy)}" r="3.6" fill="{t["accent"]}"/>' if live else "")
            + f'<text class="pt" x="{bc.f2(px + 13 + extra)}" y="{bc.f2(cy + 4.5)}">{esc(year.upper())}</text></g>')
    text_all = org + place + role + line + "".join(a + b for a, b in (stats or [])) + year.upper()
    fonts = "".join(f'@font-face{{font-family:{n};src:url(data:font/woff2;base64,{bc.woff2_subset(n, text_all)}) format("woff2")}}' for n in ("S", "R", "B"))
    d = 0.05 + i * 0.07
    css = (fonts +
           f'.org{{font:23px S;fill:{t["ink"]};letter-spacing:-.2px}}'
           f'.place{{font:14px R;fill:{t["muted"]}}}'
           f'.role{{font:15.5px B;fill:{t["accent"]}}}'
           f'.line{{font:14.2px R;fill:{t["muted"]}}}'
           f'.num{{font:17px S;fill:{t["ink"]}}}.lab{{font:12px R;fill:{t["muted"]}}}'
           f'.pt{{font:12.5px B;fill:{t["pill_ink"]};letter-spacing:1.2px}}'
           f'.in{{animation:in .7s cubic-bezier(.2,.8,.2,1) {d:.2f}s both}}'
           f'.ic{{animation:ic .8s cubic-bezier(.2,.9,.25,1.2) {d:.2f}s both;transform-box:fill-box;transform-origin:50% 100%}}'
           '@keyframes in{from{opacity:0;transform:translateX(-10px)}to{opacity:1;transform:none}}'
           '@keyframes ic{from{opacity:0;transform:translateY(8px) scale(.9)}to{opacity:1;transform:none}}'
           '.dot{animation:pulse 2s ease-in-out infinite}@keyframes pulse{0%,100%{opacity:1}50%{opacity:.25}}'
           '@media (prefers-reduced-motion:reduce){*{animation:none!important}}')
    icon = (f'<ellipse cx="62" cy="{bc.f2(cy + 30)}" rx="30" ry="6" fill="{t["shadow"]}" opacity="{t["shadow_op"]}" filter="url(#blur)"/>'
            f'<image class="ic" x="22" y="{bc.f2(cy - 42)}" width="80" height="80" href="{thumb_uri(k)}"/>')
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {bc.f2(H)}" width="{W}" height="{bc.f2(H)}" role="img" '
            f'aria-label="{esc(org)}, {esc(year)}: {esc(role)}. {esc(line)}">'
            f'<style>{css}</style><defs><filter id="blur" x="-50%" y="-200%" width="200%" height="500%"><feGaussianBlur stdDeviation="3"/></filter></defs>'
            f'<rect x="1" y="1" width="{W - 2}" height="{bc.f2(H - 2)}" rx="16" fill="{t["bg"]}" stroke="{t["edge"]}"/>'
            f'<rect x="1" y="18" width="3.5" height="{bc.f2(H - 36)}" rx="1.75" fill="{t["accent"]}" opacity=".85"/>'
            f'{icon}<g class="in">{"".join(parts)}</g>{pill}</svg>')


def main():
    for i, r in enumerate(ROWS):
        for theme in THEMES:
            svg = row(i, *r, theme)
            p = OUT / f"{r[0]}-{theme}.svg"
            p.write_text(svg)
        print(f"{r[0]}: {len(svg.encode()) / 1024:.1f} KB")


if __name__ == "__main__":
    main()
