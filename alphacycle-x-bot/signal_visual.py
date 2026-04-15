import logging
import os
from datetime import datetime, timezone
from io import BytesIO

import httpx
from PIL import Image, ImageDraw, ImageFont

logger = logging.getLogger(__name__)

ZONE_COLORS = {
    "Deep Value": "#00DC78",
    "Accumulation": "#00B4D8",
    "Expansion": "#58A6FF",
    "Risk Rising": "#FF9500",
    "Euphoria": "#FF3B3B",
}

BG_COLOR = "#0a0a0f"
TEXT_PRIMARY = "#E0E0E0"
TEXT_SECONDARY = "#888888"

WIDTH = 1200
HEIGHT = 675


async def fetch_arc_data(api_url: str) -> dict:
    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.get(api_url)
        resp.raise_for_status()
        return resp.json()


def _hex_to_rgb(hex_color: str) -> tuple[int, int, int]:
    h = hex_color.lstrip("#")
    return tuple(int(h[i : i + 2], 16) for i in (0, 2, 4))


def _load_font(size: int):
    font_paths = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/TTF/DejaVuSans-Bold.ttf",
    ]
    for path in font_paths:
        if os.path.exists(path):
            return ImageFont.truetype(path, size)
    return ImageFont.load_default()


def generate_signal_image(
    arc_score: float,
    zone_name: str,
    btc_price: float,
    date_str: str | None = None,
) -> BytesIO:
    if date_str is None:
        date_str = datetime.now(timezone.utc).strftime("%B %d, %Y")

    zone_color = ZONE_COLORS.get(zone_name, "#58A6FF")
    zone_rgb = _hex_to_rgb(zone_color)
    bg_rgb = _hex_to_rgb(BG_COLOR)

    img = Image.new("RGB", (WIDTH, HEIGHT), bg_rgb)
    draw = ImageDraw.Draw(img)

    font_score = _load_font(120)
    font_zone = _load_font(32)
    font_data = _load_font(22)

    # Zone-Farbe Glow (dezenter Ring um Score)
    center_x, center_y = WIDTH // 2, HEIGHT // 2 - 30
    glow_radius = 160
    for r in range(glow_radius, glow_radius - 40, -1):
        alpha = int(25 * (glow_radius - r) / 40)
        glow_color = (
            min(bg_rgb[0] + zone_rgb[0] * alpha // 255, 255),
            min(bg_rgb[1] + zone_rgb[1] * alpha // 255, 255),
            min(bg_rgb[2] + zone_rgb[2] * alpha // 255, 255),
        )
        draw.ellipse(
            [center_x - r, center_y - r, center_x + r, center_y + r],
            outline=glow_color,
        )

    # "ARC" Label ueber dem Score
    arc_label = "ARC"
    bbox = draw.textbbox((0, 0), arc_label, font=font_zone)
    lw = bbox[2] - bbox[0]

    # ARC Score (zentral, gross)
    score_text = str(int(round(arc_score)))
    bbox_score = draw.textbbox((0, 0), score_text, font=font_score)
    sw, sh = bbox_score[2] - bbox_score[0], bbox_score[3] - bbox_score[1]

    draw.text(
        (center_x - lw // 2, center_y - sh // 2 - 60),
        arc_label,
        fill=_hex_to_rgb(TEXT_SECONDARY),
        font=font_zone,
    )

    draw.text(
        (center_x - sw // 2, center_y - sh // 2 - 15),
        score_text,
        fill=_hex_to_rgb(zone_color),
        font=font_score,
    )

    # Zone Name (unter dem Score)
    zone_upper = zone_name.upper()
    bbox = draw.textbbox((0, 0), zone_upper, font=font_zone)
    zw = bbox[2] - bbox[0]
    draw.text(
        (center_x - zw // 2, center_y + sh // 2 + 10),
        zone_upper,
        fill=_hex_to_rgb(zone_color),
        font=font_zone,
    )

    # BTC Preis + Datum (unten mittig)
    btc_text = f"BTC ${btc_price:,.0f}  ·  {date_str}"
    bbox = draw.textbbox((0, 0), btc_text, font=font_data)
    bw = bbox[2] - bbox[0]
    draw.text(
        (center_x - bw // 2, HEIGHT - 100),
        btc_text,
        fill=_hex_to_rgb(TEXT_SECONDARY),
        font=font_data,
    )

    # KEIN alphacycle.app Link — wird spaeter hinzugefuegt wenn Dashboard fertig
    buf = BytesIO()
    img.save(buf, format="PNG", quality=95)
    buf.seek(0)
    return buf


async def generate_from_api(api_url: str) -> tuple[BytesIO, dict]:
    data = await fetch_arc_data(api_url)
    buf = generate_signal_image(
        arc_score=data.get("arc_score", 50),
        zone_name=data.get("zone_name", "Expansion"),
        btc_price=data.get("btc_price", 0),
    )
    return buf, data
