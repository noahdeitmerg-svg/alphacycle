"""
Headless Chromium screenshot of alphacycle.app hero, crop to 1500x500 (X header).
Optional upload via Tweepy v1.1 update_profile_banner (OAuth 1.0a, Read+Write).
"""
from __future__ import annotations

import asyncio
import logging
import os
from datetime import datetime, timezone
from pathlib import Path

logger = logging.getLogger(__name__)

_BASE_DIR = Path(__file__).resolve().parent
_DEFAULT_BANNERS = _BASE_DIR / "banners"


def _default_output_dir() -> str:
    raw = (os.getenv("BANNER_OUTPUT_DIR") or "").strip()
    if raw:
        return raw
    return str(_DEFAULT_BANNERS)


def _default_url() -> str:
    return (os.getenv("BANNER_PAGE_URL") or "https://alphacycle.app").strip()


async def generate_banner(
    url: str | None = None,
    output_dir: str | None = None,
    width: int = 1500,
    height: int = 500,
) -> str | None:
    """
    Open dashboard URL, wait for hero ARC score, viewport screenshot, crop to width x height.
    Returns path to final PNG or None on hard failure.
    """
    url = url or _default_url()
    output_dir = output_dir or _default_output_dir()
    os.makedirs(output_dir, exist_ok=True)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    filepath = os.path.join(output_dir, f"banner_{timestamp}.png")

    try:
        from playwright.async_api import async_playwright
    except ImportError:
        logger.error("[BANNER] playwright not installed (pip install playwright; playwright install chromium)")
        return None

    full_screenshot = os.path.join(output_dir, f"full_{timestamp}.png")
    browser = None
    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            try:
                page = await browser.new_page(viewport={"width": 1600, "height": 900})
                await page.goto(url, wait_until="load", timeout=60000)
                try:
                    await page.wait_for_function(
                        """() => {
                            const el = document.querySelector('#btc-score-val');
                            if (!el) return false;
                            const t = (el.textContent || '').trim();
                            return /^\\d+(\\.\\d+)?$/.test(t);
                        }""",
                        timeout=25000,
                    )
                except Exception as e:
                    logger.warning("[BANNER] ARC score element not ready: %s — proceeding", e)
                await asyncio.sleep(3)
                await page.screenshot(path=full_screenshot, full_page=False)
            finally:
                try:
                    await browser.close()
                except Exception:
                    pass
                browser = None
    except Exception as e:
        logger.error("[BANNER] Playwright failed: %s", e)
        if os.path.isfile(full_screenshot):
            try:
                os.remove(full_screenshot)
            except OSError:
                pass
        return None

    try:
        from PIL import Image

        img = Image.open(full_screenshot)
        img_width, img_height = img.size
        target_w, target_h = width, height
        left = max(0, (img_width - target_w) // 2)
        top = 0
        right = min(img_width, left + target_w)
        bottom = min(target_h, img_height)
        banner = img.crop((left, top, right, bottom))
        if banner.size != (target_w, target_h):
            banner = banner.resize((target_w, target_h), Image.Resampling.LANCZOS)
        banner.save(filepath, "PNG", optimize=True)
        try:
            os.remove(full_screenshot)
        except OSError:
            pass
        logger.info("[BANNER] Generated: %s", filepath)
        return filepath
    except ImportError:
        logger.warning("[BANNER] Pillow not installed — keeping uncropped full screenshot")
        try:
            os.replace(full_screenshot, filepath)
        except OSError:
            os.rename(full_screenshot, filepath)
        return filepath
    except Exception as e:
        logger.error("[BANNER] Crop/save failed: %s", e)
        if os.path.isfile(full_screenshot):
            try:
                os.remove(full_screenshot)
            except OSError:
                pass
        return None


def update_x_banner(filepath: str) -> bool:
    """
    Upload PNG as X profile header (Tweepy v1.1; requires Read+Write on the app).
    """
    try:
        import tweepy

        import config

        if not all(
            (
                config.TWITTER_API_KEY,
                config.TWITTER_API_SECRET,
                config.TWITTER_ACCESS_TOKEN,
                config.TWITTER_ACCESS_SECRET,
            )
        ):
            logger.error("[BANNER] Twitter OAuth credentials missing")
            return False

        auth = tweepy.OAuth1UserHandler(
            config.TWITTER_API_KEY,
            config.TWITTER_API_SECRET,
            config.TWITTER_ACCESS_TOKEN,
            config.TWITTER_ACCESS_SECRET,
        )
        api = tweepy.API(auth)
        api.update_profile_banner(filepath)
        logger.info("[BANNER] X profile banner updated")
        return True
    except Exception as e:
        logger.error("[BANNER] X banner upload failed: %s", e)
        return False


async def generate_and_upload_banner() -> tuple[str | None, bool]:
    """
    Generate banner PNG and upload to X. Returns (filepath, upload_ok).
    """
    fp = await generate_banner()
    if not fp:
        return None, False
    ok = await asyncio.to_thread(update_x_banner, fp)
    return fp, ok


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

    async def _run() -> None:
        fp, ok = await generate_and_upload_banner()
        if fp:
            print(f"Banner saved: {fp}")
        if ok:
            print("X banner updated.")
        else:
            print("X banner update failed or skipped — upload manually if needed.")

    asyncio.run(_run())


if __name__ == "__main__":
    main()
