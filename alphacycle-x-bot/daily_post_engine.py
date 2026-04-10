"""
Daily AlphaCycle post generation: live ARC context, Claude text, optional dashboard screenshot.

Publishing: do not post to X from this module. Queue for Telegram approval first; after approval
and successful publish, call database.record_daily_post_topic(...) so posted_topics stay accurate.
"""
from __future__ import annotations

import logging
import random
import re
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import anthropic
import requests

import config
import database
import growth_engine

logger = logging.getLogger(__name__)

_BASE_DIR = Path(__file__).resolve().parent
_SCREENSHOT_DIR = _BASE_DIR / "artifacts"
_ARC_SUMMARY_TIMEOUT = 10

# Claude 529 overloaded: wait 10-20 min between retries (up to 3 attempts total).
_DAILY_POST_OVERLOAD_MIN_SLEEP = 600
_DAILY_POST_OVERLOAD_MAX_SLEEP = 1200
_DAILY_POST_OVERLOAD_MAX_ATTEMPTS = 3


def _is_claude_overloaded(exc: BaseException) -> bool:
    """HTTP 529 / overloaded_error from Anthropic messages API."""
    code = getattr(exc, "status_code", None)
    if code == 529:
        return True
    body = getattr(exc, "body", None)
    if isinstance(body, dict):
        err = body.get("error")
        if isinstance(err, dict) and err.get("type") == "overloaded_error":
            return True
    msg = str(exc).lower()
    return "529" in msg and ("overload" in msg or "overloaded" in msg)


def _zone_hist_key(arc_score: float) -> str:
    a = float(arc_score)
    if a <= 29:
        return "deep_value"
    if a <= 39:
        return "accumulation"
    if a <= 59:
        return "expansion"
    if a <= 69:
        return "risk_rising"
    return "euphoria"


def _parse_win_rate_from_sublabel(sublabel: str | None) -> float | None:
    if not sublabel:
        return None
    m = re.search(r"(\d+(?:\.\d+)?)%\s*win rate", str(sublabel), re.I)
    if m:
        try:
            return float(m.group(1))
        except ValueError:
            return None
    return None


def _parse_return_12m_from_label(label: str | None) -> float | None:
    if not label:
        return None
    m = re.search(r"\+(\d+(?:\.\d+)?)%", str(label))
    if m:
        try:
            return float(m.group(1))
        except ValueError:
            return None
    return None


def _safe_get_json(url: str, session: requests.Session, timeout: float) -> dict[str, Any] | None:
    try:
        r = session.get(url, timeout=timeout)
        r.raise_for_status()
        data = r.json()
        return data if isinstance(data, dict) else None
    except Exception as e:
        logger.error("daily_post_engine GET failed %s: %s", url, e)
        return None


def fetch_arc_data() -> dict[str, Any] | None:
    """
    GET config.ARC_API_URL for arc-summary; same host for cycle/btc, anchor, historical-returns.
    Returns a flat dict for prompts and growth_engine, or None on hard failure of arc-summary.
    """
    arc_url = (config.ARC_API_URL or "").strip()
    parsed = urlparse(arc_url)
    host_base = (
        f"{parsed.scheme}://{parsed.netloc}".rstrip("/")
        if parsed.scheme and parsed.netloc
        else ""
    )
    base = host_base or (
        config.ALPHACYCLE_PUBLIC_BASE or "https://alphacycle-production.up.railway.app"
    )
    if not arc_url:
        arc_url = f"{base}/api/arc-summary"
    timeout = _ARC_SUMMARY_TIMEOUT
    with requests.Session() as session:
        summary = _safe_get_json(arc_url, session, timeout)
        if not summary:
            return None

        btc_j = _safe_get_json(f"{base}/api/cycle/btc", session, timeout)
        btc_price = None
        if btc_j:
            btc_price = btc_j.get("current_price")

        anchor = _safe_get_json(f"{base}/api/cycle-anchor", session, timeout)
        est_bottom = None
        if anchor:
            parts = [
                str(anchor.get("next_bottom_estimate") or "").strip(),
                str(anchor.get("expected_cycle_bottom_date") or "").strip(),
            ]
            est_bottom = " | ".join(p for p in parts if p) or None

        hist = _safe_get_json(f"{base}/api/historical-returns", session, timeout)
        return_12m: float | None = None
        win_rate: float | None = None
        arc_raw = summary.get("arc_score")
        try:
            arc_f = float(arc_raw) if arc_raw is not None else 0.0
        except (TypeError, ValueError):
            arc_f = 0.0
        zkey = _zone_hist_key(arc_f)
        zones = (hist or {}).get("zones") if hist else None
        if isinstance(zones, dict):
            z = zones.get(zkey) or {}
            if z.get("avg_12m") is not None:
                try:
                    return_12m = float(z["avg_12m"])
                except (TypeError, ValueError):
                    pass
            if z.get("win_rate_12m") is not None:
                try:
                    win_rate = float(z["win_rate_12m"])
                except (TypeError, ValueError):
                    pass

        er = summary.get("expected_range") or {}
        if isinstance(er, dict):
            if return_12m is None:
                return_12m = _parse_return_12m_from_label(er.get("label"))
            if win_rate is None:
                win_rate = _parse_win_rate_from_sublabel(er.get("sublabel"))

        zone_name = summary.get("zone_name")
        phase_group = summary.get("phase_group")
        out: dict[str, Any] = {
            **summary,
            "zone": zone_name,
            "phase": phase_group,
            "btc_price": btc_price,
            "percentile": summary.get("arc_percentile"),
            "position": summary.get("position"),
            "allocation": summary.get("allocation"),
            "return_12m": return_12m,
            "win_rate": win_rate,
            "days_since_top": summary.get("days_since_top"),
            "est_bottom": est_bottom,
        }
        return out


def summarize_post_one_sentence(post_text: str) -> str | None:
    """
    Claude follow-up: one-sentence angle summary for posted_topics.topic_summary.
    """
    raw = (post_text or "").strip()
    if not raw or not config.CLAUDE_API_KEY:
        return None
    try:
        client = anthropic.Anthropic(api_key=config.CLAUDE_API_KEY)
        response = client.messages.create(
            model=config.CLAUDE_MODEL,
            max_tokens=120,
            system=(
                "Reply with exactly one clear English sentence describing the post's "
                "main angle or thesis. No quotation marks, no hashtags, no emojis, no labels."
            ),
            messages=[{"role": "user", "content": raw[:3500]}],
        )
        block = response.content[0].text.strip()
        line = block.split("\n")[0].strip()
        return line[:500] if line else None
    except Exception as e:
        logger.warning("summarize_post_one_sentence: Claude error: %s", e)
        return None


def generate_daily_post(
    arc_data: dict[str, Any] | None, db_connection
) -> tuple[str | None, str]:
    """
    Build post prompt (topics from database.get_recent_topics via growth_engine),
    call Claude. Returns (post_text_or_none, post_type_key for this UTC weekday).
    db_connection is unused (kept for API compatibility).
    """
    _ = db_connection
    if not arc_data:
        logger.error("generate_daily_post: arc_data is missing")
        return None, ""
    if not config.CLAUDE_API_KEY:
        logger.error("generate_daily_post: CLAUDE_API_KEY not set")
        return None, ""

    weekday_idx = datetime.now(timezone.utc).weekday()
    day_name = datetime.now(timezone.utc).strftime("%A")
    post_type = growth_engine.POST_TYPE_BY_WEEKDAY[int(weekday_idx) % 7]
    logger.info(
        "generate_daily_post: day_of_week=%s (UTC index %s) type=%s",
        day_name,
        weekday_idx,
        post_type,
    )

    try:
        system_prompt = growth_engine.build_post_prompt(
            arc_data,
            day_of_week=int(weekday_idx),
        )
    except Exception as e:
        logger.error("generate_daily_post: build_post_prompt failed: %s", e)
        return None, post_type

    user_msg = (
        "Write only the final post body. Follow the system rules (line count, no hashtags/emojis, "
        "no $BTC tickers, end with Share Lines). No preamble."
    )

    for attempt in range(_DAILY_POST_OVERLOAD_MAX_ATTEMPTS):
        if attempt > 0:
            pause = random.randint(
                _DAILY_POST_OVERLOAD_MIN_SLEEP, _DAILY_POST_OVERLOAD_MAX_SLEEP
            )
            logger.warning(
                "generate_daily_post: Claude overloaded, sleeping %ss then retry %s/%s",
                pause,
                attempt + 1,
                _DAILY_POST_OVERLOAD_MAX_ATTEMPTS,
            )
            time.sleep(pause)
        try:
            client = anthropic.Anthropic(api_key=config.CLAUDE_API_KEY)
            response = client.messages.create(
                model=config.CLAUDE_MODEL,
                max_tokens=900,
                system=system_prompt,
                messages=[{"role": "user", "content": user_msg}],
            )
            text = response.content[0].text.strip()
            logger.info("generate_daily_post: generated %s chars", len(text))
            return text, post_type
        except Exception as e:
            if _is_claude_overloaded(e) and attempt < _DAILY_POST_OVERLOAD_MAX_ATTEMPTS - 1:
                continue
            logger.error("generate_daily_post: Claude API error: %s", e)
            return None, post_type


def _screenshot_playwright(out_path: Path) -> bool:
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        return False
    try:
        _SCREENSHOT_DIR.mkdir(parents=True, exist_ok=True)
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            try:
                page = browser.new_page(viewport={"width": 1400, "height": 900})
                page.goto(
                    config.DAILY_POST_DASHBOARD_URL,
                    wait_until="domcontentloaded",
                    timeout=90000,
                )
                page.wait_for_timeout(5000)
                page.screenshot(path=str(out_path), full_page=False)
            finally:
                browser.close()
        return out_path.is_file()
    except Exception as e:
        logger.error("daily_post_engine: Playwright screenshot failed: %s", e)
        return False


def _screenshot_selenium(out_path: Path) -> bool:
    try:
        from selenium import webdriver
        from selenium.webdriver.chrome.options import Options
    except ImportError:
        return False
    try:
        _SCREENSHOT_DIR.mkdir(parents=True, exist_ok=True)
        opts = Options()
        opts.add_argument("--headless=new")
        opts.add_argument("--window-size=1400,900")
        opts.add_argument("--disable-gpu")
        opts.add_argument("--no-sandbox")
        driver = webdriver.Chrome(options=opts)
        try:
            driver.set_page_load_timeout(90)
            driver.get(config.DAILY_POST_DASHBOARD_URL)
            time.sleep(5)
            driver.save_screenshot(str(out_path))
        finally:
            driver.quit()
        return out_path.is_file()
    except Exception as e:
        logger.error("daily_post_engine: Selenium screenshot failed: %s", e)
        return False


def generate_daily_post_with_image(
    arc_data: dict[str, Any] | None,
    db_connection,
) -> tuple[str | None, str | None]:
    """
    Text via generate_daily_post; optional dashboard PNG. Returns (post_text, image_path or None).
    """
    post_text, _pt = generate_daily_post(arc_data, db_connection)
    if not post_text:
        return None, None

    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_path = _SCREENSHOT_DIR / f"dashboard_{stamp}.png"

    if _screenshot_playwright(out_path):
        return post_text, str(out_path)
    if _screenshot_selenium(out_path):
        return post_text, str(out_path)

    logger.warning("generate_daily_post_with_image: no screenshot backend available or capture failed")
    return post_text, None


def topic_snippet_from_post(post_text: str, max_len: int = 280) -> str:
    """First non-empty line, trimmed, for daily_post_topics.topic_snippet."""
    for line in (post_text or "").splitlines():
        s = line.strip()
        if s:
            return s[:max_len]
    return (post_text or "")[:max_len]
