# AlphaCycle Content Factory

Generates **daily ARC regime graphics** for Instagram and YouTube from the live API.
Square (1080×1080) for IG feed/Reels covers, landscape (1920×1080) for YouTube.

## Why this exists (and why it won't get you banned)

The X/Twitter account was banned because the bot performed **platform-side
automation** (logging in and acting like a human). Meta and YouTube ban the same
thing. This tool does the **opposite**: it only *generates image files*. It never
logs into or posts to any social platform.

**Safe publishing flow:**
1. Run this script (or schedule it) → produces PNGs in `output/`.
2. Publish through an **official scheduler**: Meta Business Suite / Buffer / Later
   (Instagram Graph API) and YouTube Studio. Never password-login bots.
3. Add a short **human caption / voiceover / take** per post — this clears
   YouTube's "inauthentic content" rule and keeps engagement real.
4. Never auto-follow / auto-like / auto-comment / auto-DM. Ever.

See `docs/GTM_STRATEGY.md` §4 for the full allowed-vs-risky breakdown.

## Usage

```bash
pip install Pillow
python content-factory/generate.py                 # square + landscape
python content-factory/generate.py --format square # IG only
python content-factory/generate.py --out some/dir  # custom output dir
```

Output: `output/arc-ig-YYYY-MM-DD.png` and `output/arc-yt-YYYY-MM-DD.png`.

Data source: `ARC_API_URL` env (defaults to the Railway `/api/arc-summary`).

## Schedule it (optional, runs locally)

- **Windows Task Scheduler:** daily task running
  `python C:\path\to\alphacycle-main\content-factory\generate.py`
- **cron (VPS/Mac):** `0 12 * * * cd /path/alphacycle-main && python content-factory/generate.py`

Then a human reviews `output/` and schedules the post via Meta Business Suite /
YouTube Studio. Keep a human in the loop — that's the whole point.

## Design

Dark brand background, large ARC score in the zone color, the 5-zone bar with a
live marker, BTC price + Fear & Greed + cycle phase, date, and the
`alphacycle.app · Not financial advice` footer. Zone colors match
`backend/arc_config.py` (Deep Value / Accumulation / Expansion / Risk Rising / Euphoria).
