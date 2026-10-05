# Banner pipeline

The profile banner is split into a slow, local **bake** step and a fast,
hourly **assemble** step in GitHub Actions.

1. **Bake (on the Mac, only after art changes).** Run `python3 scripts/bake.py`.
   It renders the heavy artwork into static fragments under `bake/`.
2. **Commit `bake/`** (with any script changes) and push to `main`. The push
   triggers the workflow too.
3. **Action assembles hourly.** `.github/workflows/banner.yml` runs at :07 every
   hour. `scripts/live.py`:
   - works out Kathmandu time (UTC+5:45) and today's sunrise/sunset (NOAA
     algorithm) to pick a mode: `night`, `dusk` (dawn/dusk window) or `day`;
   - builds a clock label such as `9 pm in Kathmandu`;
   - pulls the last 30 days of contributions via GraphQL into `contrib.json`
     (public contributions only with `GITHUB_TOKEN`; a failed call falls back
     to neutral values rather than failing the run);
   - calls `scripts/assemble.py --mode … --clock … --contrib … --out dist/banner.svg`.

   `dist/` is force-pushed as a single commit to the orphan `output` branch,
   so `main` history stays clean.
4. **README** embeds
   `https://raw.githubusercontent.com/mchalise/mchalise/output/banner.svg`.

## First run

The `output` branch doesn't exist until the workflow runs once. In the repo on
GitHub go to **Actions → banner → Run workflow** (branch `main`). Do the same
any time you want a refresh without waiting for the hour.

If the push step is refused, check **Settings → Actions → General → Workflow
permissions** is set to "Read and write permissions".

## Local testing

```sh
python3 scripts/live.py --dry-run                                  # now
python3 scripts/live.py --dry-run --now 2026-10-05T17:50           # naive = Kathmandu local
GITHUB_TOKEN=$(gh auth token) python3 scripts/live.py --out out/banner.svg
```

Note: raw.githubusercontent.com caches for about 5 minutes, and GitHub's image
proxy (camo) may cache the README image a little longer.
