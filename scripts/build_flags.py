#!/usr/bin/env python3
"""Prayer-flag bunting used as the README section divider -> assets/flags.svg.
Transparent background so it sits on GitHub light and dark themes; flags sway in a breeze."""
import math, random
from pathlib import Path

random.seed(7)
W, H = 880, 46
COLORS = ["#2f6fb5", "#f4efe4", "#c8423b", "#3f8a4c", "#e2b23a"]  # sky · cloud · fire · water · earth
SAG = 12


def y_at(x):
    t = x / W
    return 5 + SAG * 4 * t * (1 - t)


flags, css = [], []
n = 30
for i in range(n):
    x = 14 + i * (W - 28) / (n - 1)
    y = y_at(x)
    ang = math.degrees(math.atan(SAG * 4 * (1 - 2 * x / W) / W))
    c = COLORS[i % 5]
    w, h = 17, 21 + (i % 3)
    d = 2.6 + random.random() * 1.6
    dl = -random.random() * d
    flags.append(
        f'<g transform="translate({x:.1f} {y:.1f}) rotate({ang:.1f})"><g style="animation:sway {d:.2f}s ease-in-out {dl:.2f}s infinite">'
        f'<path d="M{-w/2:.1f} 0H{w/2:.1f}L{w/2 - 1:.1f} {h}Q0 {h - 3} {-w/2 + 1:.1f} {h}Z" fill="{c}" stroke="rgba(60,40,20,.18)" stroke-width=".6"/>'
        f'<path d="M{-w/2 + 3:.1f} 5H{w/2 - 3:.1f}M{-w/2 + 3:.1f} 9H{w/2 - 4:.1f}M{-w/2 + 3:.1f} 13H{w/2 - 5:.1f}" stroke="rgba(60,40,20,.16)" stroke-width=".8"/>'
        f'</g></g>')
string = "M0 5 " + " ".join(f"L{x} {y_at(x):.2f}" for x in range(0, W + 1, 20))
svg = (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}" height="{H}" role="img" aria-label="Prayer flags">'
       '<style>svg *{transform-box:fill-box}g>g{transform-origin:50% 0}'
       '@keyframes sway{0%,100%{transform:rotate(-7deg) skewX(-3deg)}50%{transform:rotate(7deg) skewX(4deg)}}'
       '@media (prefers-reduced-motion:reduce){*{animation:none!important}}</style>'
       f'<path d="{string}" fill="none" stroke="#9a8a76" stroke-width="1.1"/>{"".join(flags)}</svg>')
out = Path(__file__).resolve().parent.parent / "assets" / "flags.svg"
out.write_text(svg)
print(out.name, len(svg) // 1024, "KB")
