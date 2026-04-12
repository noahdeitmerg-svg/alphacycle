"""
backtest_engine.py - Alpha Cycle Intelligence v3.0

Historical backtest: file cache /tmp/backtest_cache.json.
Once loaded, only missing days (1-2) fetched. ARC = ma_200w*0.35 + drawdown*0.25 + macro_liq*0.25 + fg_to_score(fear_greed)*0.15.
macro_liq from FRED Net Liquidity (WALCL - TGA - RRP) when available.
Return: [{"date": "YYYY-MM-DD", "price": float (close), "high": float, "low": float, "score": float}, ...]
"""

import asyncio
import csv
import json
import logging
import math
import os
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Dict, Any

import httpx

logger = logging.getLogger(__name__)

# 5-zone buckets for historical returns (aligned with phaseOf / get_zone_name)
ZONES = [(0, 29), (30, 39), (40, 59), (60, 69), (70, 100)]
ZONE_NAMES = ["Deep Value", "Accumulation", "Expansion", "Risk Rising", "Euphoria"]

try:
    from scoring import drawdown_score, drawdown_score_hl, ma_deviation_score, safe_float, fg_to_score, arc_display_score
    from arc_config import ARC_WEIGHTS
except ImportError:  # pragma: no cover
    from backend.scoring import drawdown_score, drawdown_score_hl, ma_deviation_score, safe_float, fg_to_score, arc_display_score
    from backend.arc_config import ARC_WEIGHTS


HTTP_TIMEOUT = httpx.Timeout(60.0, connect=10.0)
WINDOW_200W = 200  # 200 weekly data points = 200-week MA
CACHE_FILE = Path("/tmp/backtest_cache.json")
DAILY_CACHE_FILE = Path("/tmp/daily_full_cache.json")
CSV_PATH = Path(__file__).resolve().parent.parent / "data" / "btc_daily_kraken.csv"
# Bump when daily merge or daily-ARC methodology changes; stale files rebuild on next load.
DAILY_PRICE_CACHE_EPOCH = "20260410-arc-daily-parity"


async def _fetch_since(since_ts: int) -> List[Dict[str, Any]]:
    """Fetch only new candles since given timestamp."""
    async with httpx.AsyncClient(timeout=HTTP_TIMEOUT, follow_redirects=True) as client:
        resp = await client.get(
            "https://api.kraken.com/0/public/OHLC",
            params={"pair": "XBTUSD", "interval": 10080, "since": since_ts},
        )
        data = resp.json()
    if data.get("error") or "result" not in data:
        return []
    keys = [k for k in data["result"] if k != "last"]
    if not keys:
        return []
    out = []
    for c in data["result"][keys[0]]:
        try:
            close = float(c[4])
            high = float(c[2])
            low = float(c[3])
            if close > 0:
                dt = datetime.utcfromtimestamp(int(c[0])).date().isoformat()
                out.append({"date": dt, "price": close, "high": high, "low": low})
        except (IndexError, TypeError, ValueError):
            continue
    return out


async def _load_or_build_cache() -> List[Dict[str, Any]]:
    """Load from file cache or build from scratch."""
    today = datetime.utcnow().date().isoformat()

    if CACHE_FILE.exists():
        try:
            cached = json.loads(CACHE_FILE.read_text())
            if cached and isinstance(cached, list):
                if len(cached) < 400:  # expect ~720 weekly candles
                    try:
                        CACHE_FILE.unlink()
                    except Exception:
                        pass
                    raise Exception("cache too short, refetch")
                last_date = cached[-1]["date"]
                if last_date >= today:
                    return cached
                since_ts = int(datetime.fromisoformat(last_date).timestamp())
                new_candles = await _fetch_since(since_ts)
                if new_candles:
                    cached.extend(new_candles)
                    seen = set()
                    deduped = []
                    for item in cached:
                        if item["date"] not in seen:
                            seen.add(item["date"])
                            deduped.append(item)
                    cached = sorted(deduped, key=lambda x: x["date"])
                CACHE_FILE.write_text(json.dumps(cached))
                return cached
        except Exception as e:
            logger.warning("backtest cache load failed: %s", e)

    history = await _fetch_btc_history()
    if history:
        try:
            CACHE_FILE.write_text(json.dumps(history))
        except Exception:
            pass
    return history


async def _fetch_btc_history() -> List[Dict[str, Any]]:
    """Kraken OHLC weekly (interval=10080). 720 weeks = ~13.8y. since=2013-10-10. ARC chart ~10y from ~2014."""
    import time as _time
    since = 1381363200  # 2013-10-10, Kraken BTC live
    all_candles: List[list] = []

    async with httpx.AsyncClient(timeout=HTTP_TIMEOUT, follow_redirects=True) as client:
        while True:
            resp = await client.get(
                "https://api.kraken.com/0/public/OHLC",
                params={"pair": "XBTUSD", "interval": 10080, "since": since},
            )
            data = resp.json()
            if data.get("error") or "result" not in data:
                logger.warning(
                    "Kraken OHLC error: %s since=%s",
                    data.get("error"),
                    since,
                )
                break
            keys = [k for k in data["result"] if k != "last"]
            if not keys:
                break
            candles = data["result"][keys[0]]
            if not candles:
                break
            all_candles.extend(candles)
            last = data["result"].get("last", 0)
            if last <= since or len(candles) < 10:
                break
            since = last
            await asyncio.sleep(1.2)

    out = []
    seen = set()
    for c in all_candles:
        try:
            ts = int(c[0])
            if ts in seen:
                continue
            seen.add(ts)
            close = float(c[4])
            high = float(c[2])
            low = float(c[3])
            if close > 0:
                dt = datetime.utcfromtimestamp(ts).date().isoformat()
                out.append({"date": dt, "price": close, "high": high, "low": low})
        except (IndexError, TypeError, ValueError):
            continue
    return sorted(out, key=lambda x: x["date"])


def _load_csv_history() -> List[Dict[str, Any]]:
    """Load static Kraken BTC/USD daily OHLC from bundled CSV (2013-10-06 to 2023-12-31)."""
    if not CSV_PATH.exists():
        logger.warning("CSV not found at %s", CSV_PATH)
        return []
    out = []
    try:
        with open(CSV_PATH, "r") as f:
            reader = csv.DictReader(f)
            for row in reader:
                try:
                    ts = int(row["timestamp"])
                    close = float(row["close"])
                    high = float(row["high"])
                    low = float(row["low"])
                    if close > 0:
                        dt = datetime.utcfromtimestamp(ts).date().isoformat()
                        out.append({"date": dt, "price": close, "high": high, "low": low})
                except (KeyError, ValueError, TypeError):
                    continue
        logger.info(
            "CSV loaded: %s daily candles (%s to %s)",
            len(out),
            out[0]["date"] if out else "?",
            out[-1]["date"] if out else "?",
        )
    except Exception as e:
        logger.error("CSV load failed: %s", e)
    return sorted(out, key=lambda x: x["date"]) if out else []


async def _fetch_gap_from_cryptocompare(start_date: str, end_date: str) -> List[Dict[str, Any]]:
    """Fetch daily BTC/USD candles from CryptoCompare (Kraken exchange) for a specific date range."""
    try:
        start_ts = int(datetime.fromisoformat(start_date).timestamp())
        end_ts = int(datetime.fromisoformat(end_date).timestamp())
        days_needed = (end_ts - start_ts) // 86400 + 1

        params = {
            "fsym": "BTC",
            "tsym": "USD",
            "limit": min(days_needed, 2000),
            "toTs": end_ts,
            "e": "Kraken",
        }
        if os.environ.get("CRYPTOCOMPARE_KEY"):
            params["api_key"] = os.environ["CRYPTOCOMPARE_KEY"]

        async with httpx.AsyncClient(timeout=HTTP_TIMEOUT, follow_redirects=True) as client:
            resp = await client.get(
                "https://min-api.cryptocompare.com/data/v2/histoday",
                params=params,
            )
            data = resp.json()

        if data.get("Response") != "Success" or "Data" not in data:
            logger.warning("CryptoCompare gap fetch failed: %s", data.get("Message", "unknown"))
            return []

        entries = data.get("Data", {}).get("Data", [])
        out = []
        for entry in entries:
            try:
                ts = int(entry["time"])
                close = float(entry["close"])
                high = float(entry["high"])
                low = float(entry["low"])
                dt = datetime.utcfromtimestamp(ts).date().isoformat()
                if close > 0 and dt >= start_date and dt <= end_date:
                    out.append({"date": dt, "price": close, "high": high, "low": low})
            except (KeyError, ValueError, TypeError):
                continue

        logger.info(
            "CryptoCompare gap fill: %s candles (%s to %s)",
            len(out),
            out[0]["date"] if out else "?",
            out[-1]["date"] if out else "?",
        )
        return out
    except Exception as e:
        logger.warning("CryptoCompare gap fetch error: %s", e)
        return []


async def _fetch_btc_daily_full() -> List[Dict[str, Any]]:
    """
    DISABLED — Kraken daily OHLC API only returns ~720 most recent candles.
    Pagination does not retrieve historical data beyond that window.
    Replaced by CSV-based loading in _load_or_build_daily_cache().
    """
    logger.warning("_fetch_btc_daily_full() is disabled — use CSV-based cache loader")
    return []


async def _load_or_build_daily_cache() -> List[Dict[str, Any]]:
    """
    Build complete daily BTC price history from three sources:
    1. Static CSV: Kraken official OHLC 2013-10-06 to 2023-12-31
    2. Gap bridge: CryptoCompare e=Kraken for any gap between CSV and API
    3. Kraken live API: most recent ~720 daily candles

    Result is cached in /tmp/daily_full_cache.json with incremental updates.
    """
    today = datetime.utcnow().date().isoformat()

    # Try file cache first (wrapped dict with epoch; legacy bare list is discarded once)
    if DAILY_CACHE_FILE.exists():
        try:
            raw = json.loads(DAILY_CACHE_FILE.read_text())
            cached: Optional[List[Dict[str, Any]]] = None
            if isinstance(raw, list):
                logger.info(
                    "Daily cache legacy format (bare list): removing for epoch %s",
                    DAILY_PRICE_CACHE_EPOCH,
                )
                try:
                    DAILY_CACHE_FILE.unlink()
                except OSError:
                    pass
            elif isinstance(raw, dict) and isinstance(raw.get("daily_bars"), list):
                if raw.get("epoch") != DAILY_PRICE_CACHE_EPOCH:
                    logger.info(
                        "Daily cache epoch mismatch (%s != %s): removing file",
                        raw.get("epoch"),
                        DAILY_PRICE_CACHE_EPOCH,
                    )
                    try:
                        DAILY_CACHE_FILE.unlink()
                    except OSError:
                        pass
                else:
                    cached = raw["daily_bars"]
            else:
                logger.warning("Daily cache unknown shape: removing file")
                try:
                    DAILY_CACHE_FILE.unlink()
                except OSError:
                    pass

            if cached and isinstance(cached, list) and len(cached) > 2000:
                last_date = cached[-1]["date"]
                if last_date >= today:
                    return cached
                # Drop last entry (may be incomplete) and fetch incremental update
                cached = cached[:-1]
                since_ts = int(datetime.fromisoformat(cached[-1]["date"]).timestamp())
                async with httpx.AsyncClient(timeout=HTTP_TIMEOUT, follow_redirects=True) as client:
                    resp = await client.get(
                        "https://api.kraken.com/0/public/OHLC",
                        params={"pair": "XBTUSD", "interval": 1440, "since": since_ts},
                    )
                    data = resp.json()
                if not data.get("error") and "result" in data:
                    keys = [k for k in data["result"] if k != "last"]
                    if keys:
                        for c in data["result"][keys[0]]:
                            try:
                                close = float(c[4])
                                high = float(c[2])
                                low = float(c[3])
                                if close > 0:
                                    dt = datetime.utcfromtimestamp(int(c[0])).date().isoformat()
                                    cached.append({"date": dt, "price": close, "high": high, "low": low})
                            except (IndexError, TypeError, ValueError):
                                continue
                # Dedupe and sort
                seen = set()
                deduped = []
                for item in cached:
                    if item["date"] not in seen:
                        seen.add(item["date"])
                        deduped.append(item)
                cached = sorted(deduped, key=lambda x: x["date"])
                payload = {"epoch": DAILY_PRICE_CACHE_EPOCH, "daily_bars": cached}
                DAILY_CACHE_FILE.write_text(json.dumps(payload))
                logger.info("Daily cache incremental update: %s points to %s", len(cached), cached[-1]["date"])
                return cached
        except Exception as e:
            logger.warning("Daily cache load failed, rebuilding: %s", e)

    # === FULL REBUILD ===

    # 1. Load static CSV (2013 to 2023)
    csv_data = _load_csv_history()
    if not csv_data:
        logger.error("CSV history empty — cannot build daily cache")
        return []
    csv_end_date = csv_data[-1]["date"]
    logger.info("CSV base loaded: %s points, ends %s", len(csv_data), csv_end_date)

    # 2. Fetch Kraken API (recent ~720 days)
    since_ts = int(datetime.utcnow().timestamp()) - 750 * 86400
    kraken_recent: List[Dict[str, Any]] = []
    try:
        async with httpx.AsyncClient(timeout=HTTP_TIMEOUT, follow_redirects=True) as client:
            resp = await client.get(
                "https://api.kraken.com/0/public/OHLC",
                params={"pair": "XBTUSD", "interval": 1440, "since": since_ts},
            )
            data = resp.json()
        if not data.get("error") and "result" in data:
            keys = [k for k in data["result"] if k != "last"]
            if keys:
                for c in data["result"][keys[0]]:
                    try:
                        close = float(c[4])
                        high = float(c[2])
                        low = float(c[3])
                        if close > 0:
                            dt = datetime.utcfromtimestamp(int(c[0])).date().isoformat()
                            kraken_recent.append({"date": dt, "price": close, "high": high, "low": low})
                    except (IndexError, TypeError, ValueError):
                        continue
        logger.info(
            "Kraken API recent: %s points (%s to %s)",
            len(kraken_recent),
            kraken_recent[0]["date"] if kraken_recent else "?",
            kraken_recent[-1]["date"] if kraken_recent else "?",
        )
    except Exception as e:
        logger.warning("Kraken API fetch failed: %s", e)

    # 3. Detect and bridge gap
    api_start_date = kraken_recent[0]["date"] if kraken_recent else today
    gap_data: List[Dict[str, Any]] = []

    if csv_end_date < api_start_date:
        gap_start = (datetime.fromisoformat(csv_end_date) + timedelta(days=1)).date().isoformat()
        gap_end = (datetime.fromisoformat(api_start_date) - timedelta(days=1)).date().isoformat()
        gap_days = (datetime.fromisoformat(gap_end) - datetime.fromisoformat(gap_start)).days + 1

        if gap_days > 0:
            logger.info(
                "Gap detected: %s to %s (%s days) — fetching from CryptoCompare",
                gap_start,
                gap_end,
                gap_days,
            )
            gap_data = await _fetch_gap_from_cryptocompare(gap_start, gap_end)
            if not gap_data:
                logger.warning("Gap bridge failed — %s days will be missing", gap_days)

    # 4. Merge all three sources
    all_data = csv_data + gap_data + kraken_recent

    # Dedupe by date (later entries override earlier for overlapping dates)
    by_date: Dict[str, Dict[str, Any]] = {}
    for item in all_data:
        by_date[item["date"]] = item
    merged = sorted(by_date.values(), key=lambda x: x["date"])

    # 5. Save to file cache
    if merged:
        try:
            DAILY_CACHE_FILE.write_text(
                json.dumps({"epoch": DAILY_PRICE_CACHE_EPOCH, "daily_bars": merged})
            )
        except Exception:
            pass
        logger.info(
            "Daily cache built: %s points (%s to %s)",
            len(merged),
            merged[0]["date"],
            merged[-1]["date"],
        )

    return merged


async def _fetch_fred(series_id: str) -> list:
    """Fetch FRED series observations from 2013-01-01. Returns [{"t": ms, "v": float}, ...]."""
    FRED_KEY = os.getenv("FRED_API_KEY", "")
    if not FRED_KEY:
        return []
    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            r = await client.get(
                "https://api.stlouisfed.org/fred/series/observations",
                params={
                    "series_id": series_id,
                    "api_key": FRED_KEY,
                    "file_type": "json",
                    "observation_start": "2013-01-01",
                },
            )
            data = r.json()
        return [
            {
                "t": int(datetime.strptime(o["date"], "%Y-%m-%d").timestamp()) * 1000,
                "v": float(o["value"]),
            }
            for o in data.get("observations", [])
            if o.get("value", ".") != "."
        ]
    except Exception:
        return []


def _get_net_liq_score(date_str: str, net_liq_by_date: Dict[str, float], history_so_far: List[float]) -> float:
    """Net Liq 52w trend score for date_str. Returns 0-100; 50 if not enough data."""
    available = [(d, v) for d, v in net_liq_by_date.items() if d <= date_str]
    if len(available) < 2:
        return 50.0
    available.sort()
    cur = available[-1][1]
    prev_idx = max(0, len(available) - 53)
    prev = available[prev_idx][1]
    if prev == 0:
        return 50.0
    pct = (cur - prev) / abs(prev) * 100
    return max(0.0, min(100.0, 50 - pct * 2.0))


def _get_net_liq_impulse_score(date_str: str, net_liq_by_date: Dict[str, float]) -> float:
    """Net Liq impulse score matching compute_arc_score() methodology.
    Uses 30d + 90d change with coefficients 2.5 and 1.5."""
    available = sorted([(d, v) for d, v in net_liq_by_date.items() if d <= date_str])
    if len(available) < 22:
        return 50.0
    cur = available[-1][1]
    prev_30d = available[-22][1]
    prev_90d = available[-65][1] if len(available) >= 65 else available[0][1]
    change_30d = (cur - prev_30d) / abs(prev_30d) * 100 if prev_30d != 0 else 0.0
    change_90d = (cur - prev_90d) / abs(prev_90d) * 100 if prev_90d != 0 else 0.0
    impulse = 50.0 - change_30d * 2.5 - change_90d * 1.5
    return max(0.0, min(100.0, impulse))


async def _fetch_fg_history() -> Dict[str, float]:
    """Fetch full F&G history from Alternative.me. Returns {date_str: value}."""
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            r = await client.get(
                "https://api.alternative.me/fng/",
                params={"limit": 0, "format": "json"},
            )
            data = r.json()
        result: Dict[str, float] = {}
        for item in data.get("data", []):
            try:
                dt = datetime.utcfromtimestamp(int(item["timestamp"])).date().isoformat()
                result[dt] = float(item["value"])
            except Exception:
                continue
        logger.info("F&G history: %s pts", len(result))
        return result
    except Exception as e:
        logger.warning("F&G history failed: %s", e)
        return {}


def _rsi_to_fg(prices_so_far: List[float]) -> float:
    """
    Derive F&G proxy from RSI when real data unavailable.
    Uses RSI on weekly prices; returns 0-100 where low RSI ~ fear, high RSI ~ greed.
    """
    if len(prices_so_far) < 15:
        return 50.0
    try:
        deltas = [prices_so_far[i] - prices_so_far[i - 1] for i in range(1, len(prices_so_far))]
        period = 14
        gains = [max(0.0, d) for d in deltas[-period:]]
        losses = [max(0.0, -d) for d in deltas[-period:]]
        ag = sum(gains) / len(gains) if gains else 0.0
        al = sum(losses) / len(losses) if losses else 0.0
        if al == 0:
            rsi = 100.0 if ag > 0 else 50.0
        else:
            rsi = 100 - (100 / (1 + ag / al))
        rsi = max(0.0, min(100.0, rsi))
        return rsi
    except Exception:
        return 50.0


async def run_backtest() -> Dict[str, Any]:
    """
    DEPRECATED — temporary migration/rollback safety path only.
    Use run_daily_backtest_full() as the authoritative ARC backtest.
    Uses weekly candles inconsistent with live ARC methodology.
    Remove after daily migration is validated.

    Run historical backtest. Returns {"results": [{"date", "price", "score"}, ...], "error": "..."} on failure.
    """
    try:
        history = await _load_or_build_cache()
    except Exception as e:
        return {"results": [], "error": f"Fetch failed: {e!s}"}
    if not history:
        return {"results": [], "error": "No price history from API"}

    walcl_raw, tga_raw, rrp_raw, fg_history = await asyncio.gather(
        _fetch_fred("WALCL"),
        _fetch_fred("WTREGEN"),
        _fetch_fred("RRPONTSYD"),
        _fetch_fg_history(),
    )
    tga_dict = {item["t"]: item["v"] for item in tga_raw}
    rrp_dict = {item["t"]: item["v"] for item in rrp_raw}
    net_liq_by_date: Dict[str, float] = {}
    for item in walcl_raw:
        t = item["t"]
        w = float(item.get("v", 0))
        if w <= 0:
            continue
        tga_val = 0.0
        rrp_val = 0.0
        for delta in [0, 86400000, -86400000, 172800000, -172800000, 604800000, -604800000]:
            if t + delta in tga_dict:
                tga_val = tga_dict[t + delta]
                break
        for delta in [0, 86400000, -86400000, 172800000, -172800000, 604800000, -604800000]:
            if t + delta in rrp_dict:
                # FRED RRPONTSYD in billions; WALCL/TGA in millions
                rrp_val = float(rrp_dict[t + delta]) * 1000
                break
        net = w - tga_val - rrp_val
        date_str = datetime.utcfromtimestamp(t // 1000).date().isoformat()
        net_liq_by_date[date_str] = net

    prices: List[float] = [safe_float(item["price"], 0.0) for item in history]
    results: List[Dict[str, Any]] = []

    try:
        for idx, item in enumerate(history):
            price = prices[idx]
            if price <= 0:
                continue
            if idx + 1 < WINDOW_200W:
                continue
            window_prices = prices[idx + 1 - WINDOW_200W : idx + 1]
            if not window_prices:
                continue
            ma_200w = sum(window_prices) / len(window_prices)
            if not math.isfinite(ma_200w) or ma_200w <= 0:
                continue
            weekly_high = safe_float(history[idx].get("high", price), price)
            weekly_low = safe_float(history[idx].get("low", price), price)
            ma_200w_score = ma_deviation_score(weekly_high, ma_200w)
            prices_so_far = prices[: idx + 1]
            dd_score = drawdown_score_hl(prices_so_far, weekly_low)

            # F&G: echte Daten wenn vorhanden, sonst RSI-Proxy auf Weekly-Preisen
            if item["date"] in fg_history:
                fear_greed_raw = fg_history[item["date"]]
            else:
                fear_greed_raw = _rsi_to_fg(prices_so_far)
            fg_score = fg_to_score(fear_greed_raw)

            macro_liq = _get_net_liq_score(item["date"], net_liq_by_date, prices_so_far)
            arc = (
                ma_200w_score * ARC_WEIGHTS["trend"]
                + dd_score * ARC_WEIGHTS["drawdown"]
                + macro_liq * ARC_WEIGHTS["liquidity"]
                + fg_score * ARC_WEIGHTS["sentiment"]
            )
            # Extreme Condition Boost - identical to compute_arc_score() in scoring.py
            if ma_200w_score > 78 and fg_score > 82:
                arc += 7.0
            elif ma_200w_score > 72 and fg_score > 75:
                arc += 3.0
            if dd_score < 18 and fg_score < 15:
                arc -= 7.0
            elif dd_score < 25 and fg_score < 20:
                arc -= 3.0
            arc = max(0.0, min(100.0, arc))

            results.append(
                {
                    "date": item["date"],
                    "price": round(price, 2),
                    "high": round(weekly_high, 2),
                    "low": round(weekly_low, 2),
                    "score": round(arc, 2),
                    "score_display": round(arc_display_score(arc), 2),
                }
            )
    except Exception as e:
        return {"results": results, "error": f"Backtest loop: {e!s}"}

    return {"results": results}


async def run_daily_backtest(days: int = 400) -> Dict[str, Any]:
    """
    DEPRECATED — replaced by run_daily_backtest_full().
    Retained temporarily. Remove after daily migration is validated.

    Compute REAL daily ARC scores for the last `days` days.
    Uses daily Kraken candles (interval=1440), weekly MA200w from backtest,
    daily Fear & Greed, and forward-filled FRED net liquidity. No interpolation.
    """
    try:
        import time as _time

        # 1. Fetch daily candles from Kraken (interval=1440 = daily)
        since_ts = int(_time.time()) - (days + 30) * 86400  # buffer for MA/drawdown
        daily_candles: List[Dict[str, Any]] = []

        async with httpx.AsyncClient(timeout=HTTP_TIMEOUT, follow_redirects=True) as client:
            resp = await client.get(
                "https://api.kraken.com/0/public/OHLC",
                params={"pair": "XBTUSD", "interval": 1440, "since": since_ts},
            )
            data = resp.json()
            if not data.get("error") and "result" in data:
                keys = [k for k in data["result"] if k != "last"]
                if keys:
                    for c in data["result"][keys[0]]:
                        try:
                            ts = int(c[0])
                            close = float(c[4])
                            if close > 0:
                                dt = datetime.utcfromtimestamp(ts).date().isoformat()
                                daily_candles.append({"date": dt, "price": close})
                        except (IndexError, TypeError, ValueError):
                            continue

        if len(daily_candles) < 30:
            return {"results": [], "error": "insufficient daily candles"}

        # Sort and dedupe by date
        seen_dates = set()
        deduped: List[Dict[str, Any]] = []
        for c in daily_candles:
            d = c["date"]
            if d in seen_dates:
                continue
            seen_dates.add(d)
            deduped.append(c)
        daily_candles = sorted(deduped, key=lambda x: x["date"])

        # 2. Get weekly backtest history for MA200w values
        weekly_history = await _load_or_build_cache()
        if not weekly_history or len(weekly_history) < WINDOW_200W:
            return {"results": [], "error": "insufficient weekly history for MA200w"}

        # Build MA200w lookup by weekly date
        weekly_prices = [safe_float(w["price"], 0.0) for w in weekly_history]
        ma200w_by_date: Dict[str, float] = {}
        for idx, item in enumerate(weekly_history):
            if idx + 1 < WINDOW_200W:
                continue
            window = weekly_prices[idx + 1 - WINDOW_200W : idx + 1]
            ma = sum(window) / len(window) if window else 0.0
            if ma > 0:
                ma200w_by_date[item["date"]] = ma

        # Build combined price history (weekly + daily) for drawdown
        all_prices_by_date: Dict[str, float] = {}
        for w in weekly_history:
            all_prices_by_date[w["date"]] = safe_float(w["price"], 0.0)
        for d in daily_candles:
            all_prices_by_date[d["date"]] = d["price"]

        # 3. Fetch FRED data (net liquidity) and Fear & Greed history
        walcl_raw, tga_raw, rrp_raw, fg_history = await asyncio.gather(
            _fetch_fred("WALCL"),
            _fetch_fred("WTREGEN"),
            _fetch_fred("RRPONTSYD"),
            _fetch_fg_history(),
        )

        # Build Net Liquidity per date
        tga_dict = {item["t"]: item["v"] for item in tga_raw}
        rrp_dict = {item["t"]: item["v"] for item in rrp_raw}
        net_liq_by_date: Dict[str, float] = {}
        for item in walcl_raw:
            t = item["t"]
            w = float(item.get("v", 0))
            if w <= 0:
                continue
            tga_val = 0.0
            rrp_val = 0.0
            for delta in [0, 86400000, -86400000, 172800000, -172800000, 604800000, -604800000]:
                if t + delta in tga_dict:
                    tga_val = float(tga_dict[t + delta])
                    break
            for delta in [0, 86400000, -86400000, 172800000, -172800000, 604800000, -604800000]:
                if t + delta in rrp_dict:
                    # RRP is in billions; WALCL/TGA in millions
                    rrp_val = float(rrp_dict[t + delta]) * 1000.0
                    break
            net = w - tga_val - rrp_val
            date_str = datetime.utcfromtimestamp(t // 1000).date().isoformat()
            net_liq_by_date[date_str] = net

        # Helper: last known value <= date_str (forward-fill)
        def _last_known(lookup: Dict[str, float], target_date: str, fallback: float = 50.0) -> float:
            best = None
            for d, v in sorted(lookup.items()):
                if d <= target_date:
                    best = v
                elif best is not None:
                    break
            return best if best is not None else fallback

        def _last_known_ma200w(target_date: str) -> float:
            best = None
            for d in sorted(ma200w_by_date.keys()):
                if d <= target_date:
                    best = ma200w_by_date[d]
                elif best is not None:
                    break
            return best if best is not None else 0.0

        # Build sorted all-price series for drawdown
        all_dates_sorted = sorted(all_prices_by_date.keys())
        all_prices_list = [all_prices_by_date[d] for d in all_dates_sorted]

        results: List[Dict[str, Any]] = []

        for dc in daily_candles:
            date_str = dc["date"]
            price = float(dc["price"])

            # MA200w: last known weekly MA200w value
            ma200w_val = _last_known_ma200w(date_str)
            if ma200w_val <= 0:
                continue

            ma_200w_score = ma_deviation_score(price, ma200w_val)

            # Drawdown score: based on all prices up to this date
            idx_in_all = None
            for i, d in enumerate(all_dates_sorted):
                if d == date_str:
                    idx_in_all = i
                    break
            if idx_in_all is not None and idx_in_all >= 10:
                prices_up_to = all_prices_list[: idx_in_all + 1]
                dd_score = drawdown_score(prices_up_to)
            else:
                dd_score = 50.0

            # Fear & Greed: real daily value, forward-filled
            if date_str in fg_history:
                fg_raw = fg_history[date_str]
            else:
                fg_raw = _last_known(fg_history, date_str, 50.0)
            fg_score = fg_to_score(fg_raw)

            # Net liquidity score via existing helper
            history_slice = prices_up_to if (idx_in_all is not None and idx_in_all >= 0) else []
            macro_liq = _get_net_liq_score(date_str, net_liq_by_date, history_slice)

            # ARC formula (locked weights)
            arc = (
                ma_200w_score * ARC_WEIGHTS["trend"]
                + dd_score * ARC_WEIGHTS["drawdown"]
                + macro_liq * ARC_WEIGHTS["liquidity"]
                + fg_score * ARC_WEIGHTS["sentiment"]
            )
            # Extreme Condition Boost - identical to compute_arc_score() in scoring.py
            if ma_200w_score > 78 and fg_score > 82:
                arc += 7.0
            elif ma_200w_score > 72 and fg_score > 75:
                arc += 3.0
            if dd_score < 18 and fg_score < 15:
                arc -= 7.0
            elif dd_score < 25 and fg_score < 20:
                arc -= 3.0
            arc = max(0.0, min(100.0, arc))

            results.append(
                {
                    "date": date_str,
                    "price": round(price, 2),
                    "score": round(arc, 2),
                    "score_display": round(arc_display_score(arc), 2),
                }
            )

        # Only keep requested window
        results = sorted(results, key=lambda x: x["date"])[-days:]
        last_arc = results[-1]["score"] if results else 0.0
        logger.info("Daily backtest: %s points, last ARC=%.1f", len(results), last_arc)
        return {"results": results}

    except Exception as e:
        logger.error("Daily backtest error: %s", e, exc_info=True)
        return {"results": [], "error": str(e)}


async def run_daily_backtest_full() -> Dict[str, Any]:
    """
    Full-range daily ARC backtest from ~2017 to today.

    METHODOLOGY: MA200w is computed from daily prices via [::7] slicing then
    moving_average(..., 200), replicating the exact pattern in compute_btc_score()
    (scoring.py L325-326). This is a deliberate methodology-alignment choice.
    [::7] daily != true weekly closes, but it ensures backtest and live ARC
    use identical methodology.
    """
    try:
        history = await _load_or_build_daily_cache()
    except Exception as e:
        return {"results": [], "error": f"Daily fetch failed: {e!s}"}

    if not history or len(history) < 1400:
        logger.warning(
            "Daily history too short (%s points). Kraken daily OHLC returns only ~720 "
            "newest candles; full-range daily not available. Fallback to weekly backtest.",
            len(history) if history else 0,
        )
        return await run_backtest()

    walcl_raw, tga_raw, rrp_raw, fg_history = await asyncio.gather(
        _fetch_fred("WALCL"),
        _fetch_fred("WTREGEN"),
        _fetch_fred("RRPONTSYD"),
        _fetch_fg_history(),
    )

    tga_dict = {item["t"]: item["v"] for item in tga_raw}
    rrp_dict = {item["t"]: item["v"] for item in rrp_raw}
    net_liq_by_date: Dict[str, float] = {}
    for item in walcl_raw:
        t = item["t"]
        w = float(item.get("v", 0))
        if w <= 0:
            continue
        tga_val = 0.0
        rrp_val = 0.0
        for delta in [0, 86400000, -86400000, 172800000, -172800000, 604800000, -604800000]:
            if t + delta in tga_dict:
                tga_val = tga_dict[t + delta]
                break
        for delta in [0, 86400000, -86400000, 172800000, -172800000, 604800000, -604800000]:
            if t + delta in rrp_dict:
                rrp_val = float(rrp_dict[t + delta]) * 1000
                break
        net = w - tga_val - rrp_val
        date_str = datetime.utcfromtimestamp(t // 1000).date().isoformat()
        net_liq_by_date[date_str] = net

    prices: List[float] = [safe_float(item["price"], 0.0) for item in history]

    DAILY_PER_WEEK = 7
    MIN_DAYS_FOR_MA200W = WINDOW_200W * DAILY_PER_WEEK

    fg_dates_sorted = sorted(fg_history.keys())

    def _fg_forward_fill(target_date: str) -> float:
        best = None
        for d in fg_dates_sorted:
            if d <= target_date:
                best = fg_history[d]
            else:
                break
        return best if best is not None else 50.0

    results: List[Dict[str, Any]] = []

    try:
        for idx, item in enumerate(history):
            price = prices[idx]
            if price <= 0:
                continue
            if idx + 1 < MIN_DAYS_FOR_MA200W:
                continue

            daily_up_to_now = prices[: idx + 1]
            weekly_sampled = daily_up_to_now[::DAILY_PER_WEEK]
            if len(weekly_sampled) < WINDOW_200W:
                continue
            ma_200w = sum(weekly_sampled[-WINDOW_200W:]) / WINDOW_200W
            if not math.isfinite(ma_200w) or ma_200w <= 0:
                continue

            daily_high = safe_float(item.get("high", price), price)
            daily_low = safe_float(item.get("low", price), price)

            ma_200w_score = ma_deviation_score(daily_high, ma_200w)

            prices_so_far = prices[: idx + 1]
            dd_score = drawdown_score_hl(prices_so_far, daily_low) if len(prices_so_far) >= 10 else 50.0

            if item["date"] in fg_history:
                fear_greed_raw = fg_history[item["date"]]
            else:
                fg_raw_ff = _fg_forward_fill(item["date"])
                fear_greed_raw = fg_raw_ff if fg_raw_ff != 50.0 else _rsi_to_fg(prices_so_far)
            fg_score = fg_to_score(fear_greed_raw)

            macro_liq = _get_net_liq_impulse_score(item["date"], net_liq_by_date)

            arc = (
                ma_200w_score * ARC_WEIGHTS["trend"]
                + dd_score * ARC_WEIGHTS["drawdown"]
                + macro_liq * ARC_WEIGHTS["liquidity"]
                + fg_score * ARC_WEIGHTS["sentiment"]
            )
            # Extreme Condition Boost - identical to compute_arc_score() in scoring.py
            if ma_200w_score > 78 and fg_score > 82:
                arc += 7.0
            elif ma_200w_score > 72 and fg_score > 75:
                arc += 3.0
            if dd_score < 18 and fg_score < 15:
                arc -= 7.0
            elif dd_score < 25 and fg_score < 20:
                arc -= 3.0
            arc = max(0.0, min(100.0, arc))

            results.append({
                "date": item["date"],
                "price": round(price, 2),
                "high": round(daily_high, 2),
                "low": round(daily_low, 2),
                "score": round(arc, 2),
                "score_display": round(arc_display_score(arc), 2),
            })

    except Exception as e:
        return {"results": results, "error": f"Daily backtest loop: {e!s}"}

    try:
        weekly_bt = await run_backtest()
        weekly_results = weekly_bt.get("results", []) if isinstance(weekly_bt, dict) else []
        weekly_backtest_scores = {
            r["date"]: r["score"] for r in weekly_results
            if r.get("date") and r.get("score") is not None
        }
    except Exception:
        weekly_backtest_scores = {}

    for ref_date in ["2022-11-21", "2024-03-14", "2025-01-20"]:
        daily_score = None
        for r in results:
            if r["date"] == ref_date:
                daily_score = r["score"]
                break
        weekly_score = weekly_backtest_scores.get(ref_date)
        delta = round(daily_score - weekly_score, 2) if (daily_score is not None and weekly_score is not None) else None
        logger.info(
            "ARC VALIDATION: %s -> daily=%.1f weekly=%.1f delta=%s",
            ref_date,
            daily_score if daily_score is not None else -1,
            weekly_score if weekly_score is not None else -1,
            f"{delta:+.1f}" if delta is not None else "n/a",
        )

    logger.info(
        "Daily full backtest: %s points, range %s -> %s",
        len(results),
        results[0]["date"] if results else "?",
        results[-1]["date"] if results else "?",
    )
    return {"results": results}


__all__ = ["run_backtest", "run_daily_backtest", "run_daily_backtest_full"]
