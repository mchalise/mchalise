#!/usr/bin/env python3
""""Tools of the trade" panel for the GitHub profile README, in the site fonts.
  assets/stack-light.svg / assets/stack-dark.svg
Icons live in scripts/icons/ (see NOTICE.md). Edit GROUPS below and re-run:
  python3 scripts/build_stack.py
"""
import base64, re, sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import build_cards as bc

ROOT = bc.ROOT
ICONS = Path(__file__).resolve().parent / "icons"

GROUPS = [
    ("AI & LLMs", [("claude", "Claude"), ("openai", "OpenAI"), ("langchain", "LangChain"), ("vectordb", "Vector DBs"),
                   ("agents", "AI agents"), ("llm", "LLM apps")]),
    ("Languages", [("ruby", "Ruby"), ("go", "Go"), ("typescript", "TypeScript"), ("javascript", "JavaScript"),
                   ("python", "Python"), ("php", "PHP"), ("solidity", "Solidity"), ("bash", "Bash")]),
    ("Backend", [("rails", "Rails"), ("nodejs", "Node.js"), ("express", "Express"), ("laravel", "Laravel"),
                 ("sidekiq", "Sidekiq"), ("microservices", "Microservices"), ("api", "REST & SOAP")]),
    ("Frontend", [("react", "React"), ("nextjs", "Next.js"), ("angularjs", "AngularJS")]),
    ("Cloud & DevOps", [("aws", "AWS"), ("ecs", "ECS / Fargate"), ("lambda", "Lambda"), ("rds", "RDS"), ("s3", "S3"),
                        ("docker", "Docker"), ("kubernetes", "Kubernetes"), ("githubactions", "GitHub Actions"),
                        ("datadog", "Datadog"), ("honeybadger", "Honeybadger")]),
    ("Data & Web3", [("postgresql", "PostgreSQL"), ("redis", "Redis"), ("mongodb", "MongoDB"), ("bitcoin", "Bitcoin"),
                     ("ethereum", "Ethereum"), ("pipeline", "On-chain pipelines")]),
]
OFF = [("guitar", "Guitar"), ("basketball", "Basketball"), ("football", "Football"), ("cricket", "Cricket"),
       ("chakra", "Energy Healing & Meditation (Grandmaster)")]
OFF_TEXT = " · ".join(nm for _, nm in OFF)

THEMES = {
    "light": dict(bg="#fbf7ef", edge="#eadfcb", chip="#ffffff", chip_edge="#e8dcc8", ink="#2b2622", muted="#7d7168",
                  accent="#b4532f", rule="#eadfcb"),
    "dark": dict(bg="#121933", edge="#27305c", chip="#1a2248", chip_edge="#2c376b", ink="#f1eadc", muted="#a5adcf",
                 accent="#f3b36a", rule="#27305c"),
}
RECOLOR_DARK = {"express", "nextjs", "aws", "ethereum", "solidity"}   # near-black logos -> cream on navy
W, PAD, LABEL_W = 880, 28, 150
CH, IC, GAP = 34, 18, 8
NAME = ("R", 14.2)


def icon_uri(k, theme):
    png = ICONS / f"{k}-{theme}.png"            # per-theme raster first (e.g. silhouette recoloured for navy)
    if not png.exists():
        png = ICONS / f"{k}.png"
    if png.exists():
        return "data:image/png;base64," + base64.b64encode(png.read_bytes()).decode()
    s = (ICONS / f"{k}.svg").read_text()
    s = re.sub(r"<metadata>.*?</metadata>", "", s, flags=re.S)
    if theme == "dark" and k in RECOLOR_DARK:
        def fix(m):
            h = m.group(1)
            h = "".join(c * 2 for c in h) if len(h) == 3 else h
            r, g, b = (int(h[i:i + 2], 16) for i in (0, 2, 4))
            return 'fill="#ece4d6"' if (0.2126 * r + 0.7152 * g + 0.0722 * b) < 80 else m.group(0)
        s = re.sub(r'fill="#([0-9a-fA-F]{3,6})"', fix, s)
    return "data:image/svg+xml;base64," + base64.b64encode(s.encode()).decode()


def balanced(widths, avail):
    """indices where a new line starts, minimising the widest line for the fewest lines that fit"""
    from itertools import combinations
    n = len(widths)
    span = lambda a, b: sum(widths[a:b]) + GAP * (b - a - 1)
    for lines in range(1, n + 1):
        best = None
        for cut in combinations(range(1, n), lines - 1):
            edges = (0, *cut, n)
            m = max(span(a, b) for a, b in zip(edges, edges[1:]))
            if m <= avail and (best is None or m < best[0]):
                best = (m, set(cut))
        if best:
            return best[1]
    return set(range(1, n))


def chips(body, items, y, n, t, theme, x_start, x_max, big=()):
    widths = [12 + IC + 8 + bc.text_w(*NAME, nm) + 14 + (8 if k in big else 0) for k, nm in items]
    breaks = balanced(widths, x_max - x_start)
    x = x_start
    for j, ((k, name), w) in enumerate(zip(items, widths)):
        if j in breaks:
            x, y = x_start, y + CH + 10
        d = 0.12 + n * 0.022
        ic = IC + (8 if k in big else 0)
        body.append(f'<g class="chip" style="animation-delay:{d:.3f}s"><rect x="{x:.1f}" y="{y}" width="{w:.1f}" height="{CH}" rx="{CH / 2}" fill="{t["chip"]}" stroke="{t["chip_edge"]}"/>'
                    f'<image x="{x + 12 - (4 if k in big else 0):.1f}" y="{y + (CH - ic) / 2:.1f}" width="{ic}" height="{ic}" href="{icon_uri(k, theme)}"/>'
                    f'<text class="nm" x="{x + 12 + ic + 8 - (4 if k in big else 0):.1f}" y="{y + CH / 2 + 5:.1f}">{name.replace("&", "&amp;")}</text></g>')
        x += w + GAP
        n += 1
    return y, n


def build(theme):
    t = THEMES[theme]
    x_start, x_max = PAD + LABEL_W, W - PAD
    y, body, n = PAD + 4, [], 0
    for gi, (label, items) in enumerate(GROUPS):
        body.append(f'<text class="lab" style="animation-delay:{0.05 + gi * 0.08:.2f}s" x="{PAD + 6}" y="{y + CH / 2 + 4.5:.1f}">{label.upper().replace("&", "&amp;")}</text>')
        y, n = chips(body, items, y, n, t, theme, x_start, x_max)
        y += CH + (18 if gi < len(GROUPS) - 1 else 0)
        if gi < len(GROUPS) - 1:
            body.append(f'<line x1="{x_start}" x2="{x_max}" y1="{y - 9}" y2="{y - 9}" stroke="{t["rule"]}" stroke-dasharray="2 5" stroke-linecap="round"/>')
    y += 22
    body.append(f'<line x1="{PAD}" x2="{W - PAD}" y1="{y - 12}" y2="{y - 12}" stroke="{t["rule"]}"/>')
    y += 4
    body.append(f'<text class="lab" style="animation-delay:.6s" x="{PAD + 6}" y="{y + CH / 2 + 4.5:.1f}">OFF THE KEYBOARD</text>')
    y, n = chips(body, OFF, y, n, t, theme, x_start, x_max, big={"chakra"})
    y += CH
    H = y + PAD - 4
    text_all = "".join(g[0].upper() for g in GROUPS) + "".join(nm for g in GROUPS for _, nm in g[1]) + OFF_TEXT + "OFF THE KEYBOARD"
    fonts = "".join(f'@font-face{{font-family:{f};src:url(data:font/woff2;base64,{bc.woff2_subset(f, text_all)}) format("woff2")}}' for f in ("S", "R", "B"))
    css = (fonts +
           f'.lab,.offl{{font:11.5px B;letter-spacing:1.6px;fill:{t["accent"]}}}'
           f'.nm{{font:14.2px R;fill:{t["ink"]}}}'
           '.chip{animation:pop .5s cubic-bezier(.2,.9,.3,1.25) both;transform-box:fill-box;transform-origin:50% 50%}'
           '.lab{animation:fade .6s ease-out both}'
           '@keyframes pop{from{opacity:0;transform:translateY(6px) scale(.92)}to{opacity:1;transform:none}}'
           '@keyframes fade{from{opacity:0}to{opacity:1}}'
           '@media (prefers-reduced-motion:reduce){*{animation:none!important}}')
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H:.0f}" width="{W}" height="{H:.0f}" role="img" '
            f'aria-label="Tools of the trade: ' + "; ".join(f'{g[0]}: ' + ", ".join(nm for _, nm in g[1]) for g in GROUPS).replace("&", "&amp;") +
            f'. Off the keyboard: {OFF_TEXT.replace("&", "&amp;")}">'
            f'<style>{css}</style><rect x="1" y="1" width="{W - 2}" height="{H - 2:.0f}" rx="18" fill="{t["bg"]}" stroke="{t["edge"]}"/>'
            + "".join(body) + "</svg>")


if __name__ == "__main__":
    for theme in THEMES:
        svg = build(theme)
        p = ROOT / "assets" / f"stack-{theme}.svg"
        p.write_text(svg)
        print(p.name, f"{len(svg.encode()) / 1024:.0f} KB")
