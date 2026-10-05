#!/usr/bin/env python3
"""Rebuild every banner locally: bake the art, then assemble the previews.

  python3 scripts/build_banner.py            # bake (needs Pillow etc.) + assemble
  python3 scripts/build_banner.py --no-bake  # just re-assemble from bake/*.json

Writes assets/preview-{day,dusk,night}.svg and, for the README's <picture> fallback,
assets/day.svg + assets/night.svg (same as the day/night previews). The hourly
GitHub Action only runs scripts/assemble.py (stdlib) against the committed bake/.
"""
import shutil, subprocess, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
S = ROOT / "scripts"

if __name__ == "__main__":
    if "--no-bake" not in sys.argv:
        subprocess.run([sys.executable, str(S / "bake.py"), *[a for a in sys.argv[1:] if a == "--redusk"]], check=True)
    subprocess.run([sys.executable, str(S / "assemble.py"), "--all-previews"], check=True)
    for mode in ("day", "night"):
        shutil.copyfile(ROOT / "assets" / f"preview-{mode}.svg", ROOT / "assets" / f"{mode}.svg")
        print(f"assets/{mode}.svg ← preview-{mode}.svg")
