#!/usr/bin/env python3
"""Hourly live step for the profile banner.

Works out the current Kathmandu time, sun phase (day / dusk / night) and the
last 30 days of GitHub activity, then calls scripts/assemble.py to stitch the
pre-baked fragments in bake/ into one SVG.

Pure stdlib. Usage:
  python3 scripts/live.py --out dist/banner.svg
  python3 scripts/live.py --dry-run --now 2026-10-05T21:00:00+05:45
"""
from __future__ import annotations

import argparse
import json
import math
import os
import subprocess
import sys
import urllib.request
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

KTM = ZoneInfo("Asia/Kathmandu")
LAT, LON = 27.7172, 85.3240
WINDOW_DAYS = 30
ROOT = Path(__file__).resolve().parent.parent


# --------------------------------------------------------------------------
# Solar math (NOAA solar calculator algorithm)
# --------------------------------------------------------------------------
def _julian_day(d: date) -> float:
    y, m = d.year, d.month
    if m <= 2:
        y -= 1
        m += 12
    a = y // 100
    b = 2 - a + a // 4
    return math.floor(365.25 * (y + 4716)) + math.floor(30.6001 * (m + 1)) + d.day + b - 1524.5


def _sun_params(jc: float) -> tuple[float, float]:
    """Return (declination_deg, equation_of_time_min) for Julian century jc."""
    l0 = (280.46646 + jc * (36000.76983 + 0.0003032 * jc)) % 360
    m = 357.52911 + jc * (35999.05029 - 0.0001537 * jc)
    e = 0.016708634 - jc * (0.000042037 + 0.0000001267 * jc)
    mr = math.radians(m)
    c = (math.sin(mr) * (1.914602 - jc * (0.004817 + 0.000014 * jc))
         + math.sin(2 * mr) * (0.019993 - 0.000101 * jc)
         + math.sin(3 * mr) * 0.000289)
    true_long = l0 + c
    omega = 125.04 - 1934.136 * jc
    app_long = true_long - 0.00569 - 0.00478 * math.sin(math.radians(omega))
    mean_obl = 23 + (26 + (21.448 - jc * (46.815 + jc * (0.00059 - jc * 0.001813))) / 60) / 60
    obl = mean_obl + 0.00256 * math.cos(math.radians(omega))
    decl = math.degrees(math.asin(math.sin(math.radians(obl)) * math.sin(math.radians(app_long))))
    y = math.tan(math.radians(obl / 2)) ** 2
    l0r = math.radians(l0)
    eot = 4 * math.degrees(
        y * math.sin(2 * l0r) - 2 * e * math.sin(mr)
        + 4 * e * y * math.sin(mr) * math.cos(2 * l0r)
        - 0.5 * y * y * math.sin(4 * l0r) - 1.25 * e * e * math.sin(2 * mr))
    return decl, eot


def _event_utc_minutes(d: date, rising: bool) -> float:
    """UTC minutes after midnight (of date d, UTC) of sunrise/sunset at KTM."""
    jd = _julian_day(d)
    t = 720.0  # first guess: solar noon-ish, refine twice
    for _ in range(3):
        jc = (jd + t / 1440 - 2451545) / 36525
        decl, eot = _sun_params(jc)
        latr, dr = math.radians(LAT), math.radians(decl)
        cos_ha = (math.cos(math.radians(90.833)) / (math.cos(latr) * math.cos(dr))
                  - math.tan(latr) * math.tan(dr))
        ha = math.degrees(math.acos(max(-1.0, min(1.0, cos_ha))))
        if not rising:
            ha = -ha
        t = 720 - 4 * (LON + ha) - eot
    return t


def sun_times(local_day: date) -> tuple[datetime, datetime]:
    """Sunrise and sunset (aware, Kathmandu tz) for a Kathmandu calendar day."""
    # Kathmandu is UTC+5:45, so local morning/evening still fall on the same
    # UTC date (sunrise ~00:10 UTC, sunset ~12:00 UTC).
    base = datetime(local_day.year, local_day.month, local_day.day, tzinfo=timezone.utc)
    out = []
    for rising in (True, False):
        mins = _event_utc_minutes(local_day, rising)
        out.append((base + timedelta(minutes=mins)).astimezone(KTM))
    return out[0], out[1]


def sun_mode(now: datetime) -> str:
    rise, sset = sun_times(now.date())
    if rise - timedelta(minutes=30) <= now <= rise + timedelta(minutes=30):
        return "dusk"  # dawn shares the dusk palette
    if sset - timedelta(minutes=45) <= now <= sset + timedelta(minutes=45):
        return "dusk"
    if now < rise - timedelta(minutes=30) or now > sset + timedelta(minutes=45):
        return "night"
    return "day"


def clock_label(now: datetime) -> str:
    h = now.hour
    if h == 0:
        word = "midnight"
    elif h == 12:
        word = "noon"
    else:
        word = f"{h % 12} {'am' if h < 12 else 'pm'}"
    return f"{word} in Kathmandu"


# --------------------------------------------------------------------------
# GitHub contributions
# --------------------------------------------------------------------------
QUERY = """
query($login: String!, $from: DateTime!, $to: DateTime!) {
  user(login: $login) {
    contributionsCollection(from: $from, to: $to) {
      contributionCalendar {
        totalContributions
        weeks { contributionDays { date contributionCount } }
      }
    }
  }
}
"""


def fallback_contrib(reason: str) -> dict:
    return {"active_days": WINDOW_DAYS, "days_in_window": WINDOW_DAYS,
            "busiest_day": None, "busiest_count": 0, "total": 0,
            "fallback": True, "reason": reason}


def fetch_contrib(now_utc: datetime) -> dict:
    token = os.environ.get("GITHUB_TOKEN", "").strip()
    login = os.environ.get("GH_USER", "").strip() or "mchalise"
    if not token:
        return fallback_contrib("no GITHUB_TOKEN")
    start = now_utc - timedelta(days=WINDOW_DAYS)
    iso = lambda d: d.strftime("%Y-%m-%dT%H:%M:%SZ")
    body = json.dumps({"query": QUERY, "variables": {
        "login": login, "from": iso(start), "to": iso(now_utc)}}).encode()
    req = urllib.request.Request(
        "https://api.github.com/graphql", data=body, method="POST",
        headers={"Authorization": f"bearer {token}",
                 "Content-Type": "application/json",
                 "User-Agent": "mchalise-banner"})
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            data = json.load(r)
        cal = data["data"]["user"]["contributionsCollection"]["contributionCalendar"]
        days = [d for w in cal["weeks"] for d in w["contributionDays"]]
    except Exception as exc:  # network, auth, schema, null user...
        return fallback_contrib(f"api error: {type(exc).__name__}: {exc}"[:200])
    # Calendar is day-granular and may include a 31st partial day; keep last 30.
    days = sorted(days, key=lambda d: d["date"])[-WINDOW_DAYS:]
    active = sum(1 for d in days if d["contributionCount"] > 0)
    busiest = max(days, key=lambda d: d["contributionCount"], default=None)
    return {"active_days": active, "days_in_window": WINDOW_DAYS,
            "busiest_day": busiest["date"] if busiest else None,
            "busiest_count": busiest["contributionCount"] if busiest else 0,
            "total": sum(d["contributionCount"] for d in days)}


# --------------------------------------------------------------------------
def parse_now(s: str | None) -> datetime:
    if not s:
        return datetime.now(timezone.utc).astimezone(KTM)
    s = s.strip().replace("Z", "+00:00")
    dt = datetime.fromisoformat(s)
    if dt.tzinfo is None:  # naive = Kathmandu local
        dt = dt.replace(tzinfo=KTM)
    return dt.astimezone(KTM)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--now", help="ISO time override (naive = Kathmandu local)")
    ap.add_argument("--dry-run", action="store_true", help="print, don't assemble")
    ap.add_argument("--out", default="out/banner.svg")
    args = ap.parse_args(argv)

    now = parse_now(args.now)
    mode, label = sun_mode(now), clock_label(now)
    rise, sset = sun_times(now.date())
    contrib = fetch_contrib(now.astimezone(timezone.utc))

    out = Path(args.out)
    if not out.is_absolute():
        out = Path.cwd() / out
    out.parent.mkdir(parents=True, exist_ok=True)
    contrib_path = out.parent / "contrib.json"
    contrib_path.write_text(json.dumps(contrib, indent=2) + "\n")

    print(f"now      {now.isoformat(timespec='minutes')}")
    print(f"sun      rise {rise:%H:%M}  set {sset:%H:%M}")
    print(f"mode     {mode}")
    print(f"label    {label}")
    print(f"contrib  {json.dumps(contrib)}")
    if args.dry_run:
        return 0

    cmd = [sys.executable, str(ROOT / "scripts" / "assemble.py"),
           "--mode", mode, "--clock", label,
           "--contrib", str(contrib_path), "--out", str(out)]
    print("run      " + " ".join(cmd), flush=True)
    return subprocess.call(cmd, cwd=ROOT)


if __name__ == "__main__":
    raise SystemExit(main())
