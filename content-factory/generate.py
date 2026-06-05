#!/usr/bin/env python3
"""
AlphaCycle Content Factory — daily ARC regime graphics for Instagram / YouTube.

Ban-safe by design: this script ONLY *generates* image files from the live API.
It does NOT post anywhere. Publish the output through an OFFICIAL scheduler
(Meta Business Suite / Buffer / Later for Instagram; YouTube Studio for Shorts),
ideally with a short human caption/voiceover — never via login-automation bots.
That separation is exactly what keeps accounts alive (see docs/GTM_STRATEGY.md §4).

Usage:
    python content-factory/generate.py                 # square + landscape
    python content-factory/generate.py --format square
    python content-factory/generate.py --out some/dir

Requires: Pillow  (pip install Pillow)
"""
import argparse
import json
import os
import sys
import urllib.request
from datetime import datetime, timezone

try:
    from PIL import Image, ImageDraw, ImageFont
except ImportError:
    print("Pillow is required:  pip install Pillow", file=sys.stderr)
    sys.exit(1)

API = os.getenv("ARC_API_URL", "https://alphacycle-production.up.railway.app/api/arc-summary")

BG = (10, 10, 15)
CARD = (18, 20, 28)
WHITE = (255, 255, 255)
GREY = (150, 160, 175)
DIM = (90, 98, 112)

# Zone bands + colors (match backend arc_config.ARC_ZONES / SYSTEM_TRUTH)
ZONES = [
    (0, 30, "DEEP VALUE", (0, 220, 120)),
    (30, 40, "ACCUMULATION", (0, 180, 216)),
    (40, 60, "EXPANSION", (88, 166, 255)),
    (60, 70, "RISK RISING", (255, 149, 0)),
    (70, 100, "EUPHORIA", (255, 59, 59)),
]


def zone_for(arc):
    for lo, hi, name, color in ZONES:
        if lo <= arc < hi:
            return name, color
    return "EUPHORIA", (255, 59, 59)


def fetch():
    req = urllib.request.Request(API, headers={"User-Agent": "alphacycle-content-factory"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read().decode())


def font(size, bold=True):
    """Best-effort font loading across OSes; falls back to PIL default."""
    candidates = (
        ["arialbd.ttf", "Arial Bold.ttf", "DejaVuSans-Bold.ttf"] if bold
        else ["arial.ttf", "Arial.ttf", "DejaVuSans.ttf"]
    )
    for name in candidates:
        try:
            return ImageFont.truetype(name, size)
        except Exception:
            continue
    # search common dirs
    dirs = ["/usr/share/fonts/truetype/dejavu", "C:/Windows/Fonts", "/Library/Fonts"]
    fname = "DejaVuSans-Bold.ttf" if bold else "DejaVuSans.ttf"
    for d in dirs:
        p = os.path.join(d, fname)
        if os.path.exists(p):
            try:
                return ImageFont.truetype(p, size)
            except Exception:
                pass
    return ImageFont.load_default()


def center_text(draw, cx, y, text, fnt, fill):
    bbox = draw.textbbox((0, 0), text, font=fnt)
    w = bbox[2] - bbox[0]
    draw.text((cx - w / 2, y), text, font=fnt, fill=fill)
    return bbox[3] - bbox[1]


def render(data, W, H, path):
    arc = float(data.get("arc_score") or data.get("arc_display") or 50)
    zone_name, zcol = zone_for(arc)
    btc = data.get("btc_price")
    fg = data.get("fear_greed")
    phase = data.get("phase_context") or ""
    date_s = datetime.now(timezone.utc).strftime("%b %d, %Y").upper()

    img = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(img)
    cx = W // 2
    scale = H / 1080.0

    # Header
    center_text(d, cx, int(70 * scale), "ALPHACYCLE", font(int(40 * scale)), WHITE)
    center_text(d, cx, int(122 * scale), "BITCOIN CYCLE INTELLIGENCE", font(int(20 * scale), False), GREY)

    # Big ARC number
    num = str(int(round(arc)))
    nf = font(int(260 * scale))
    bbox = d.textbbox((0, 0), num, font=nf)
    nw, nh = bbox[2] - bbox[0], bbox[3] - bbox[1]
    ny = int(H * 0.26)
    d.text((cx - nw / 2, ny), num, font=nf, fill=zcol)
    base = ny + nh + int(76 * scale)
    center_text(d, cx, base, "ARC RISK INDEX  ·  0-100", font(int(22 * scale), False), GREY)
    center_text(d, cx, base + int(46 * scale), zone_name, font(int(54 * scale)), zcol)

    # Zone bar
    bar_y = int(H * 0.70)
    bar_x0, bar_x1 = int(W * 0.10), int(W * 0.90)
    bar_w = bar_x1 - bar_x0
    seg_h = int(26 * scale)
    for lo, hi, name, color in ZONES:
        sx = bar_x0 + int(bar_w * lo / 100.0)
        ex = bar_x0 + int(bar_w * hi / 100.0)
        d.rectangle([sx, bar_y, ex, bar_y + seg_h], fill=color)
    # marker
    mx = bar_x0 + int(bar_w * min(max(arc, 0), 100) / 100.0)
    d.polygon([(mx, bar_y - int(16 * scale)), (mx - int(12 * scale), bar_y - int(2 * scale)),
               (mx + int(12 * scale), bar_y - int(2 * scale))], fill=WHITE)
    d.line([(mx, bar_y), (mx, bar_y + seg_h)], fill=WHITE, width=max(2, int(3 * scale)))

    # Stats row
    stats = []
    if btc:
        try:
            stats.append("BTC  $" + format(int(round(float(btc))), ",d"))
        except Exception:
            pass
    if fg is not None:
        stats.append("FEAR & GREED  " + str(int(round(float(fg)))))
    if phase:
        stats.append(str(phase).upper())
    sy = bar_y + seg_h + int(54 * scale)
    center_text(d, cx, sy, "   ·   ".join(stats), font(int(28 * scale), False), WHITE)

    # Footer
    center_text(d, cx, H - int(96 * scale), date_s, font(int(22 * scale), False), DIM)
    center_text(d, cx, H - int(62 * scale), "alphacycle.app   ·   Not financial advice", font(int(20 * scale), False), DIM)

    img.save(path, "PNG")
    return path


def main():
    ap = argparse.ArgumentParser(description="AlphaCycle daily regime graphics")
    ap.add_argument("--format", choices=["square", "landscape", "both"], default="both")
    ap.add_argument("--out", default=os.path.join(os.path.dirname(__file__), "output"))
    args = ap.parse_args()

    os.makedirs(args.out, exist_ok=True)
    try:
        data = fetch()
    except Exception as e:
        print(f"Failed to fetch ARC data: {e}", file=sys.stderr)
        sys.exit(1)

    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    made = []
    if args.format in ("square", "both"):
        made.append(render(data, 1080, 1080, os.path.join(args.out, f"arc-ig-{stamp}.png")))
    if args.format in ("landscape", "both"):
        made.append(render(data, 1920, 1080, os.path.join(args.out, f"arc-yt-{stamp}.png")))

    print(f"ARC={data.get('arc_score')} zone={data.get('zone_name')} btc={data.get('btc_price')}")
    for p in made:
        print("wrote", p)


if __name__ == "__main__":
    main()
