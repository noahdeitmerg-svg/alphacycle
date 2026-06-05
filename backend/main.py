"""
main.py — Alpha Cycle Intelligence v3.0
FastAPI Backend. Zero NaN. Auto-refresh every 60s.

Endpoints:
  GET /health
  GET /api/prices
  GET /api/cycle/btc
  GET /api/cycle/eth
  GET /api/cycle/macro
  GET /api/cycle/combined
  GET /api/history
  GET /api/fear-greed
  GET /api/analyzer
  GET /api/decision
"""
import os, time, math, logging, asyncio, json
from contextlib import asynccontextmanager
from datetime import datetime, timedelta
from typing import Optional, Any

import stripe
from fastapi import FastAPI, HTTPException, Security
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pathlib import Path
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from starlette.requests import Request

try:
    from fetcher import fetch_all, _synthetic_walcl
except ImportError:
    from fetcher import fetch_all, _synthetic_walcl

try:
    from database import supabase
except ImportError:
    from database import supabase

try:
    from auth import get_current_user, require_auth, require_paid
except ImportError:
    from auth import get_current_user, require_auth, require_paid

try:
    from scoring import (
        compute_btc_score, compute_eth_score,
        compute_macro_score, compute_combined,
        compute_arc_score, compute_arc_momentum, compute_short_term_score,
        clamp, safe_float, arc_display_score,
    )
except ImportError:
    from scoring import (
        compute_btc_score, compute_eth_score,
        compute_macro_score, compute_combined,
        compute_arc_score, compute_arc_momentum, compute_short_term_score,
        clamp, safe_float, arc_display_score,
    )

try:
    from analyzer import analyzer as cycle_analyzer, get_short_term_context
except ImportError:
    from analyzer import analyzer as cycle_analyzer, get_short_term_context

try:
    from decision_engine import decision_engine, get_position
except ImportError:
    from decision_engine import decision_engine, get_position

try:
    from liquidity_engine import compute_liquidity_regime
except ImportError:
    from liquidity_engine import compute_liquidity_regime

try:
    from cycle_anchor import compute_cycle_anchor, compute_days_since_bottom, TENTATIVE_CYCLE_TOP, compute_days_since_top
except ImportError:
    from cycle_anchor import compute_cycle_anchor, compute_days_since_bottom, TENTATIVE_CYCLE_TOP, compute_days_since_top

try:
    from analyzer import CycleAnalyzer
except ImportError:
    from analyzer import CycleAnalyzer
_analyzer = CycleAnalyzer()

try:
    from services.backtest_engine import run_daily_backtest_full
except ImportError:
    from services.backtest_engine import run_daily_backtest_full

try:
    from snapshot import build_snapshot
except ImportError:
    from snapshot import build_snapshot

try:
    from seasonality import get_seasonal_context
except ImportError:
    def get_seasonal_context():
        return {"month": 1, "month_name": "January", "avg_return": 0, "label": "N/A", "color": "#6b7280", "next_month_return": 0}

# -- LOGGING --------------------------------------------------------------------
logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger(__name__)

# -- CACHE ----------------------------------------------------------------------
CACHE: dict = {}
CACHE_TTL   = int(os.getenv("CACHE_TTL_SECONDS", "60"))
_cache_lock = asyncio.Lock()
SNAPSHOT_FILE = Path("/tmp/arc_snapshots.json")
_last_refresh = 0.0

# -- STRIPE CONFIG --------------------------------------------------------------
STRIPE_SECRET_KEY = os.environ.get("STRIPE_SECRET_KEY", "")
STRIPE_WEBHOOK_SECRET = os.environ.get("STRIPE_WEBHOOK_SECRET", "")
# Price IDs (set these in Railway env — never hardcode keys). Monthly/Yearly preferred; STRIPE_PRICE_ID kept as fallback.
STRIPE_PRICE_MONTHLY = os.environ.get("STRIPE_PRICE_MONTHLY", "")
STRIPE_PRICE_YEARLY = os.environ.get("STRIPE_PRICE_YEARLY", "")
STRIPE_PRICE_ID = os.environ.get("STRIPE_PRICE_ID", "")


def _resolve_price_id(plan: str) -> str:
    """Map a requested plan to a Stripe price id, with safe fallbacks."""
    plan = (plan or "monthly").lower()
    if plan in ("yearly", "annual", "year") and STRIPE_PRICE_YEARLY:
        return STRIPE_PRICE_YEARLY
    if plan in ("monthly", "month") and STRIPE_PRICE_MONTHLY:
        return STRIPE_PRICE_MONTHLY
    # fallbacks: any configured price
    return STRIPE_PRICE_MONTHLY or STRIPE_PRICE_ID or STRIPE_PRICE_YEARLY


stripe.api_key = STRIPE_SECRET_KEY

# -- RATE LIMITING --------------------------------------------------------------
limiter = Limiter(
    key_func=get_remote_address,
    default_limits=["100/minute"],
    storage_uri="memory://",
)


async def refresh_cache(force: bool = False):
    global _last_refresh
    async with _cache_lock:
        now = time.time()
        if not force and (now - _last_refresh) < CACHE_TTL:
            return

        logger.info("Alpha Cycle — refreshing data cache…")
        try:
            raw = await fetch_all()

            try:
                from services.backtest_engine import _load_or_build_daily_cache

                daily_cache = await _load_or_build_daily_cache()
                if daily_cache and len(daily_cache) > 1400:
                    btc_prices_full = [
                        safe_float(d["price"])
                        for d in daily_cache
                        if safe_float(d.get("price")) > 0
                    ]
                    raw["btc_prices"] = btc_prices_full
                    logger.info(
                        "Full BTC price history loaded: %s days (MA200w requires 1400+)",
                        len(btc_prices_full),
                    )
                else:
                    logger.warning(
                        "Daily cache too short (%s points), using Kraken-only prices",
                        len(daily_cache) if daily_cache else 0,
                    )
            except Exception as e:
                logger.warning("Daily cache load failed, using Kraken-only prices: %s", e)

            try:
                from fetcher import fetch_kraken_ohlc_latest

                ohlc_latest = await fetch_kraken_ohlc_latest()
            except Exception:
                ohlc_latest = {}

            btc_p  = raw["btc_prices"]
            eth_p  = raw["eth_prices"]
            walcl  = [item["v"] for item in raw.get("walcl_series", [])]
            stable = [item["v"] for item in raw.get("stable_series", [])]
            tvl    = [item["v"] for item in raw.get("tvl_series",   [])]
            us10y  = [item["v"] for item in raw.get("us10y_series", [])]
            fg     = raw["fear_greed"]["current"]

            # New v3 data
            indicators   = raw.get("indicators",   {})
            funding_data = raw.get("funding_data", {})
            global_data  = raw.get("global_data",  {})
            btc_dom      = global_data.get("btc_dominance", 50.0)
            net_liq_series = raw.get("net_liq_series", [])

            btc_scores = compute_btc_score(
                btc_p, fg, walcl, stable,
                indicators=indicators,
                funding_data=funding_data,
                btc_dominance=btc_dom,
                net_liq_values=net_liq_series,
            )
            short_term_scores = compute_short_term_score(
                prices_daily=btc_p,
                fear_greed=fg,
                funding_data=raw.get("funding_data", raw.get("funding", {})),
                indicators=raw.get("indicators", {}),
                walcl_values=walcl,
                net_liq_values=net_liq_series,
            )
            eth_scores = compute_eth_score(
                eth_p, btc_p, tvl, stable, fg,
                funding_data=funding_data,
            )
            macro_scores = compute_macro_score(
                walcl, stable, btc_p,
                us10y_series=us10y,
                global_data=global_data,
                funding_data=funding_data,
            )
            combined = compute_combined(
                btc_scores["btc_score"],
                eth_scores["eth_score"],
                macro_scores["macro_score"],
            )

            hist = CACHE.get("score_history",
                             {"btc": [], "eth": [], "macro": [], "combined": []})
            ts = int(time.time() * 1000)
            for key, val in [
                ("btc",      btc_scores["btc_score"]),
                ("eth",      eth_scores["eth_score"]),
                ("macro",    macro_scores["macro_score"]),
                ("combined", combined["combined_score"]),
            ]:
                hist[key].append({"t": ts, "v": val})
                hist[key] = hist[key][-2880:]

            CACHE.update({
                "raw":          raw,
                "btc_scores":   btc_scores,
                "short_term_scores": short_term_scores,
                "eth_scores":   eth_scores,
                "macro_scores": macro_scores,
                "combined":     combined,
                "score_history":hist,
                "refreshed_at": ts,
                "ohlc_latest":  ohlc_latest or {},
            })
            _last_refresh = now
            # Invalidate heavy endpoint response cache and derived histories after fresh data
            _response_cache.clear()
            logger.info(
                f"Cache OK — BTC:{btc_scores['btc_score']:.1f} "
                f"ETH:{eth_scores['eth_score']:.1f} "
                f"MACRO:{macro_scores['macro_score']:.1f}"
            )
            # Save daily ARC snapshot after successful refresh
            _save_today_snapshot()

            # Regime-change alert check (Telegram). Fully guarded — never breaks refresh.
            try:
                _ohlc_now = CACHE.get("ohlc_latest", {}) or {}
                arc_live = compute_arc_score(
                    btc_p, fg, walcl, stable, net_liq_series,
                    weekly_high=_ohlc_now.get("high"),
                    weekly_low=_ohlc_now.get("low"),
                )
                _btc_now = safe_float(raw.get("btc_market", {}).get("price")) or (btc_p[-1] if btc_p else None)
                from alerts import check_and_fire_alerts
                res = await asyncio.to_thread(check_and_fire_alerts, arc_live, _btc_now)
                if res.get("status") == "fired":
                    logger.info("Regime alert fired: %s -> %s", res.get("from"), res.get("to"))
            except Exception as e:
                logger.warning("Alert check skipped (non-critical): %s", e)

            try:
                bt_data = await run_daily_backtest_full()
                bt_results = bt_data.get("results", []) if isinstance(bt_data, dict) else []
                if not bt_results:
                    logger.error(
                        "Backtest failed: daily full backtest returned no results (%s)",
                        bt_data.get("error") if isinstance(bt_data, dict) else "non-dict response",
                    )
                if bt_results:
                    for _r in bt_results:
                        if _r.get("score_display") is not None:
                            _r["score"] = _r["score_display"]
                            _r["arc_score"] = _r["score_display"]
                    from historical_returns import (
                        compute_historical_returns,
                        compute_arc_forward_returns,
                        compute_high_risk_drawdown,
                    )
                    arc_history = []
                    for _r in bt_results:
                        d = _r.get("date")
                        arc_val = _r.get("arc_score", _r.get("score"))
                        price = _r.get("btc_price", _r.get("price"))
                        if d and arc_val is not None and price is not None:
                            arc_history.append(
                                {
                                    "date": d,
                                    "arc_score": float(arc_val),
                                    "btc_price": float(price),
                                }
                            )
                    zone_periods = compute_zone_history(arc_history) if arc_history else []
                    hist_returns = compute_historical_returns(bt_results, zone_periods=zone_periods or None)
                    fwd_returns = compute_arc_forward_returns(bt_results)
                    dd_data = compute_high_risk_drawdown(bt_results)
                    CACHE.update({
                        "backtest_results": bt_results,
                        "hist_returns": hist_returns,
                        "fwd_returns": fwd_returns,
                        "high_risk_drawdown": dd_data,
                    })
            except Exception as e:
                logger.warning("Backtest cache update failed (non-critical): %s", e)

        except Exception as e:
            logger.error(f"Cache refresh failed: {e}", exc_info=True)


async def _refresh_loop():
    while True:
        try:
            await refresh_cache()
        except Exception as e:
            logger.error(f"Refresh loop error: {e}")
        await asyncio.sleep(CACHE_TTL)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Alpha Cycle Intelligence API starting…")
    try:
        from pathlib import Path as _Path
        for _cache_path in ("/tmp/zone_history_cache.json", "/tmp/daily_full_cache.json"):
            cache_file = _Path(_cache_path)
            if cache_file.exists():
                try:
                    cache_file.unlink()
                    logger.info("Cache cleared on startup: %s", _cache_path)
                except Exception as e:
                    logger.warning("Could not clear cache %s: %s", _cache_path, e)
    except Exception as e:
        logger.warning("Backtest cache clear init failed: %s", e)
    await refresh_cache(force=True)
    task = asyncio.create_task(_refresh_loop())
    yield
    task.cancel()
    logger.info("Alpha Cycle API shut down.")


app = FastAPI(
    title="Alpha Cycle Intelligence API",
    version="3.0.0",
    description="Institutional crypto cycle intelligence. Zero NaN.",
    lifespan=lifespan,
)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

import pathlib
_static_dir = pathlib.Path(__file__).parent / "static"
if _static_dir.exists():
    app.mount("/static", StaticFiles(directory=str(_static_dir)), name="static")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["GET"],
    allow_headers=["*"],
)


# -- HELPERS --------------------------------------------------------------------

def _require_cache() -> dict:
    if not CACHE:
        raise HTTPException(503, "Data not yet available. Retry in 10s.")
    return CACHE


def _save_today_snapshot() -> dict:
    """Build and persist today's ARC snapshot based on current CACHE."""
    from datetime import date

    if not CACHE or "raw" not in CACHE:
        return {"error": "no data"}

    try:
        c = CACHE
        raw = c.get("raw", {})
        btc_scores = c.get("btc_scores", {})
        macro_scores = c.get("macro_scores", {})
        combined = c.get("combined", {})

        btc_market = raw.get("btc_market", {})
        fg_value = (raw.get("fear_greed") or {}).get("current", 50.0)
        liquidity_trend = macro_scores.get("walcl_trend", 50.0)

        walcl = [item["v"] for item in raw.get("walcl_series", [])]
        stable = [item["v"] for item in raw.get("stable_series", [])]
        _ohlc = c.get("ohlc_latest", {})
        real_arc = compute_arc_score(
            raw.get("btc_prices", []),
            fg_value,
            walcl,
            stable,
            raw.get("net_liq_series"),
            weekly_high=_ohlc.get("high"),
            weekly_low=_ohlc.get("low"),
        )

        snapshot = {
            "date":       date.today().isoformat(),
            "arc":        round(float(real_arc), 1),
            "btc_price":  round(safe_float(btc_market.get("price", 0.0)), 0),
            "regime":     macro_scores.get("regime", "NEUTRAL"),
            "liquidity":  round(liquidity_trend, 1),
            "fear_greed": fg_value,
            "decision":   get_position(real_arc),
            "confidence": round(combined.get("confidence", 0.0), 1),
        }

        snapshots = []
        if SNAPSHOT_FILE.exists():
            try:
                snapshots = json.loads(SNAPSHOT_FILE.read_text())
            except Exception:
                snapshots = []

        # Deduplicate by date and append latest
        snapshots = [s for s in snapshots if s.get("date") != snapshot["date"]]
        snapshots.append(snapshot)
        snapshots = sorted(snapshots, key=lambda x: x.get("date", ""))

        SNAPSHOT_FILE.write_text(json.dumps(snapshots, indent=2))
        return snapshot
    except Exception as e:
        logger.warning("Snapshot save failed: %s", e)
        return {"error": "snapshot_failed"}

# -- RESPONSE CACHE (heavy computation endpoints) ------------------------------
_response_cache: dict = {}
_RESPONSE_TTL = 15.0

def _get_cached_response(key: str) -> Optional[dict]:
    entry = _response_cache.get(key)
    if entry is None:
        return None
    cached_at, data = entry
    if time.time() - cached_at > _RESPONSE_TTL:
        return None
    return data

def _set_cached_response(key: str, data: dict) -> None:
    _response_cache[key] = (time.time(), data)


def _clean(obj: Any) -> Any:
    if isinstance(obj, dict):  return {k: _clean(v) for k, v in obj.items()}
    if isinstance(obj, list):  return [_clean(v) for v in obj]
    if isinstance(obj, float):
        return 0.0 if (math.isnan(obj) or math.isinf(obj)) else round(obj, 6)
    return obj

def api_response(data: dict) -> JSONResponse:
    cleaned = _clean(data)
    cleaned["_ts"] = int(time.time() * 1000)
    return JSONResponse(content=cleaned)

def _prices_to_series(prices: list, days: int) -> list:
    if not prices: return []
    subset = prices[-days:]
    now_ms = int(time.time() * 1000)
    return [{"t": now_ms - (len(subset)-1-i)*86_400_000, "v": safe_float(p)}
            for i, p in enumerate(subset)]

def _build_ratio_series(btc_prices: list, eth_prices: list, days: int) -> list:
    btc = btc_prices[-days:] if btc_prices else []
    eth = eth_prices[-days:] if eth_prices else []
    n   = min(len(btc), len(eth))
    if not n: return []
    now_ms = int(time.time() * 1000)
    return [{"t": now_ms-(n-1-i)*86_400_000,
             "v": safe_float(eth[-(n-i)]) / safe_float(btc[-(n-i)], 1.0)}
            for i in range(n)]


def get_eth_btc_signal(ratio: float) -> dict:
    if ratio < 0.020:
        return {
            "ratio": ratio,
            "label": "ETH Extreme Undervaluation",
            "note": "Historically strongest ETH accumulation zone",
            "color": "#00D4AA",
            "strength": "strong",
        }
    if ratio < 0.030:
        return {
            "ratio": ratio,
            "label": "ETH Undervalued vs BTC",
            "note": "ETH historically outperforms in recovery from this level",
            "color": "#00B4D8",
            "strength": "moderate",
        }
    if ratio < 0.040:
        return {
            "ratio": ratio,
            "label": "ETH Neutral vs BTC",
            "note": "No clear directional edge",
            "color": "#6b7280",
            "strength": "neutral",
        }
    if ratio < 0.060:
        return {
            "ratio": ratio,
            "label": "ETH Elevated vs BTC",
            "note": "BTC dominance likely - reduce ETH exposure",
            "color": "#FF9500",
            "strength": "caution",
        }
    return {
        "ratio": ratio,
        "label": "ETH Overvalued vs BTC",
        "note": "Altseason peak territory historically",
        "color": "#FF3B3B",
        "strength": "avoid",
    }


def _calc_weeks(date_from: str, date_to: str) -> int:
    try:
        from datetime import datetime

        d1 = datetime.fromisoformat(str(date_from))
        d2 = datetime.fromisoformat(str(date_to))
        days = abs((d2 - d1).days)
        return max(1, days // 7)
    except Exception:
        return 1


def compute_zone_history(arc_history: list, min_weeks: int = 4) -> list:
    """
    Build zone periods from backtest history.
    Rules:
    1. A zone is only confirmed after min_weeks consecutive weeks in it
    2. Only entries FROM BELOW count (lower zone -> higher zone = bullish progression)
    3. Return = entry price until confirmed entry into next HIGHER zone
    4. If ARC falls back within min_weeks -> not confirmed, absorbed into previous zone
    """
    if not arc_history:
        return []

    from datetime import datetime

    ZONE_ORDER = {
        "Deep Value": 0,
        "Accumulation": 1,
        "Expansion": 2,
        "Risk Rising": 3,
        "Euphoria": 4,
    }

    def _weeks(d1_str, d2_str):
        try:
            d1 = datetime.fromisoformat(str(d1_str))
            d2 = datetime.fromisoformat(str(d2_str))
            return max(1, abs((d2 - d1).days) // 7)
        except Exception:
            return 1

    def _close_period(zone, start_date, start_price, end_date, end_price, direction, ongoing=False):
        rtn = 0.0
        if start_price and start_price > 0:
            try:
                rtn = round((end_price - start_price) / start_price * 100.0, 1)
            except Exception:
                rtn = 0.0
        return {
            "zone": zone,
            "from": start_date,
            "to": None if ongoing else end_date,
            "weeks": max(1, _weeks(start_date, end_date)),
            "btc_entry": round(start_price),
            "btc_exit": round(end_price),
            "return_pct": rtn,
            "direction": direction,
        }

    history = []

    confirmed_zone = None
    confirmed_order = -1
    zone_start_date = None
    zone_start_price = None
    last_confirmed_date = None
    last_confirmed_price = None
    entry_direction = "initial"

    pending_zone = None
    pending_order = -1
    pending_count = 0
    pending_start_date = None
    pending_start_price = None

    last_date = None
    last_price = None

    for entry in arc_history:
        date = entry.get("date")
        score_val = entry.get("arc_score", entry.get("score"))
        price = entry.get("btc_price", entry.get("price"))
        if date is None or score_val is None or price is None:
            continue

        price = float(price)
        zone = get_zone_name(float(score_val))
        order = ZONE_ORDER.get(zone, 2)

        if confirmed_zone is None:
            confirmed_zone = zone
            confirmed_order = order
            zone_start_date = date
            zone_start_price = price
            last_confirmed_date = date
            last_confirmed_price = price
            last_date = date
            last_price = price
            continue

        if zone == confirmed_zone:
            pending_zone = None
            pending_count = 0
            last_confirmed_date = date
            last_confirmed_price = price

        elif zone == pending_zone:
            pending_count += 1
            try:
                days_pending = (datetime.fromisoformat(str(date)) - datetime.fromisoformat(str(pending_start_date))).days
            except Exception:
                days_pending = pending_count
            if days_pending >= min_weeks * 7:
                new_order = ZONE_ORDER.get(pending_zone, 2)
                direction = "up" if new_order > confirmed_order else "down"

                history.append(
                    _close_period(
                        confirmed_zone,
                        zone_start_date,
                        zone_start_price,
                        last_confirmed_date,
                        last_confirmed_price,
                        entry_direction,
                    )
                )

                confirmed_zone = pending_zone
                confirmed_order = new_order
                zone_start_date = pending_start_date
                zone_start_price = pending_start_price
                last_confirmed_date = date
                last_confirmed_price = price
                entry_direction = direction

                pending_zone = None
                pending_count = 0
        else:
            pending_zone = zone
            pending_order = ZONE_ORDER.get(zone, 2)
            pending_count = 1
            pending_start_date = date
            pending_start_price = price

        last_date = date
        last_price = price

    if confirmed_zone and zone_start_date and last_date and zone_start_price:
        history.append(
            _close_period(
                confirmed_zone,
                zone_start_date,
                zone_start_price,
                last_date,
                last_price or zone_start_price,
                entry_direction,
                ongoing=True,
            )
        )

    history = list(reversed(history))
    return history[:20]


# -- ENDPOINTS -------------------------------------------------------------------

@app.get("/health")
@limiter.exempt
async def health(request: Request):
    return {
        "status":    "ok",
        "service":   "Alpha Cycle Intelligence API",
        "cache_age": max(0, int(time.time() - _last_refresh)),
        "has_data":  bool(CACHE),
        "version":   "3.0.0",
    }


@app.get("/api/prices")
async def get_prices(request: Request):
    c = _require_cache()
    raw = c["raw"]
    btc_market = raw.get("btc_market", {})
    eth_market = raw.get("eth_market", {})
    btc_prices = raw.get("btc_prices", [])
    eth_prices = raw.get("eth_prices", [])
    gdata = raw.get("global_data", {})

    btc_ath = max(btc_prices) if btc_prices else 0.0
    eth_ath = max(eth_prices) if eth_prices else 0.0
    btc_current = btc_prices[-1] if btc_prices else 0.0
    eth_current = eth_prices[-1] if eth_prices else 0.0
    btc_ath_pct = round((btc_current - btc_ath) / btc_ath * 100, 2) if btc_ath > 0 else 0.0
    eth_ath_pct = round((eth_current - eth_ath) / eth_ath * 100, 2) if eth_ath > 0 else 0.0

    fg = raw["fear_greed"]
    fd = raw.get("funding_data", {})
    stable_series = raw.get("stable_series", [])
    stable_b = safe_float(stable_series[-1]["v"]) / 1e9 if stable_series else 0.0

    return api_response({
        "btc": {
            "price":          safe_float(btc_market.get("price", 0)),
            "change_24h":     safe_float(btc_market.get("change_24h", 0)),
            "market_cap":     safe_float(btc_market.get("market_cap", 0)),
            "volume_24h":     safe_float(btc_market.get("volume", 0)),
            "ath":            round(btc_ath, 2),
            "ath_change_pct": btc_ath_pct,
            "history":        _prices_to_series(btc_prices, 90),
        },
        "eth": {
            "price":          safe_float(eth_market.get("price", 0)),
            "change_24h":     safe_float(eth_market.get("change_24h", 0)),
            "market_cap":     safe_float(eth_market.get("market_cap", 0)),
            "volume_24h":     safe_float(eth_market.get("volume", 0)),
            "ath":            round(eth_ath, 2),
            "ath_change_pct": eth_ath_pct,
            "history":        _prices_to_series(eth_prices, 90),
        },
        "eth_btc_ratio": _build_ratio_series(btc_prices, eth_prices, 90),
        "fear_greed":    fg,
        "global": {
            "btc_dominance":    safe_float(gdata.get("btc_dominance", 50)),
            "total_market_cap": safe_float(gdata.get("total_market_cap", 0)),
        },
        "funding": {
            "btc_funding_rate": safe_float(fd.get("btc_funding_rate", 0)),
            "eth_funding_rate": safe_float(fd.get("eth_funding_rate", 0)),
        },
        "stablecoin_cap_B": stable_b,
    })


@app.get("/api/cycle/btc")
async def get_btc_cycle(request: Request):
    c = _require_cache()
    s = c["btc_scores"]
    return api_response({
        "score":         s.get("btc_score", 50.0),
        "current_price": s.get("current_price", 0.0),
        "components": {
            "ma_200w":       {"score": s.get("ma_200w", 50.0), "deviation_pct": s.get("ma_200w_dev_pct", 0.0), "value": s.get("ma_200w_raw", 0.0)},
            "mvrv":          {"score": s.get("mvrv", 50.0)},
            "fear_greed":    {"score": s.get("fear_greed", 50.0), "raw": c["raw"]["fear_greed"]["current"]},
            "drawdown":      {"score": s.get("drawdown", 50.0)},
            "rsi":           {"score": s.get("rsi", 50.0), "raw": s.get("rsi_raw", 50.0)},
            "puell":         {"score": s.get("puell", 50.0)},
            "pi_cycle":      {"score": s.get("pi_cycle", 50.0)},
            "macro_liq":     {"score": s.get("macro_liq", 50.0)},
            "stable_supply": {"score": s.get("stable_supply", 50.0)},
            "funding":       {"score": s.get("funding", 50.0), "raw": s.get("funding_raw", 0.0)},
            "power_law":     {"score": s.get("power_law", 50.0)},
        },
        "short_term": s.get("short_term", {
            "rsi": 50.0,
            "funding": 50.0,
            "mvrv": 50.0,
            "power_law": 50.0,
            "pi_cycle": 50.0,
            "puell": 50.0,
        }),
        "short_term_v2": c.get("short_term_scores", {}),
        "weights": {
            "ma_200w": 0.18, "mvrv": 0.15, "fear_greed": 0.12,
            "drawdown": 0.10, "rsi": 0.10, "puell": 0.10,
            "pi_cycle": 0.08, "macro_liq": 0.08, "stable_supply": 0.05,
            "funding": 0.02, "power_law": 0.02,
        },
    })


@app.get("/api/short-term")
async def get_short_term(request: Request):
    c = _require_cache()
    st = c.get("short_term_scores", {})
    return api_response({
        "score": st.get("short_term_score", 50.0),
        "signal": st.get("signal", "NEUTRAL"),
        "signal_color": st.get("signal_color", "#f59e0b"),
        "components": {
            "rsi":        {"score": st.get("rsi", 50.0), "raw": st.get("rsi_raw", 50.0)},
            "mvrv":       {"score": st.get("mvrv", 50.0)},
            "funding":    {"score": st.get("funding", 50.0), "raw": st.get("funding_raw", 0.0)},
            "fear_greed": {"score": st.get("fear_greed", 50.0)},
            "ma_50d":     {"score": st.get("ma_50d", 50.0), "raw": st.get("ma_50d_raw", 0.0), "dev_pct": st.get("ma_50d_dev_pct", 0.0)},
            "puell":      {"score": st.get("puell", 50.0)},
        },
        "weights": {
            "rsi": 0.20, "mvrv": 0.20, "funding": 0.15,
            "fear_greed": 0.15, "ma_50d": 0.15, "puell": 0.15,
        },
        "horizon": "30-90D",
        "note": "Tactical layer only - does not override ARC Index",
    })


@app.get("/api/cycle/eth")
async def get_eth_cycle(request: Request):
    c = _require_cache()
    s = c["eth_scores"]
    return api_response({
        "score":         s.get("eth_score", 50.0),
        "current_price": s.get("current_price", 0.0),
        "components": {
            "eth_btc_ratio":   {"score": s.get("eth_btc_ratio", 50.0), "raw": s.get("eth_btc_ratio_raw", 0.05)},
            "tvl_trend":       {"score": s.get("tvl_trend", 50.0)},
            "price_trend_30d": {"score": s.get("price_trend_30d", 50.0)},
            "rsi":             {"score": s.get("rsi", 50.0)},
            "ma_200w":         {"score": s.get("ma_200w", 50.0)},
            "price_trend_90d": {"score": s.get("price_trend_90d", 50.0)},
            "drawdown":        {"score": s.get("drawdown", 50.0)},
            "stable_growth":   {"score": s.get("stable_growth", 50.0)},
            "fear_greed":      {"score": s.get("fear_greed", 50.0)},
            "eth_funding":     {"score": s.get("eth_funding", 50.0)},
        },
        "weights": {
            "eth_btc_ratio": 0.20, "tvl_trend": 0.17, "price_trend_30d": 0.12,
            "rsi": 0.12, "ma_200w": 0.10, "price_trend_90d": 0.09,
            "drawdown": 0.07, "stable_growth": 0.06,
            "fear_greed": 0.04, "eth_funding": 0.03,
        },
    })


@app.get("/api/cycle/macro")
async def get_macro_cycle(request: Request):
    c = _require_cache()
    s = c["macro_scores"]
    walcl_hist  = [{"t": i["t"], "v": safe_float(i["v"])}
                   for i in c["raw"].get("walcl_series", [])[-180:]]
    stable_hist = [{"t": i["t"], "v": safe_float(i["v"]) / 1e9}
                   for i in c["raw"].get("stable_series", [])[-180:]]
    return api_response({
        "score": s.get("macro_score", 50.0),
        "components": {
            "walcl_trend":   {"score": s.get("walcl_trend", 50.0)},
            "stable_trend":  {"score": s.get("stable_trend", 50.0)},
            "btc_risk_on":   {"score": s.get("btc_risk_on", 50.0)},
            "dxy_trend":     {"score": s.get("dxy_trend", 50.0)},
            "yield_trend":   {"score": s.get("yield_trend", 50.0)},
            "btc_dom_macro": {"score": s.get("btc_dom_macro", 50.0)},
        },
        "data": {
            "walcl_current_T":    s.get("walcl_current", 8.0),
            "walcl_yoy_pct":      s.get("walcl_yoy_pct", 0.0),
            "stable_current_B":   s.get("stable_current_B", 150.0),
            "btc_dominance_pct":  s.get("btc_dominance_pct", 50.0),
        },
        "history": {"walcl": walcl_hist, "stable": stable_hist},
        "weights": {
            "walcl_trend": 0.30, "stable_trend": 0.22, "btc_risk_on": 0.18,
            "dxy_trend": 0.10, "yield_trend": 0.10, "btc_dom_macro": 0.10,
        },
    })


@app.get("/api/cycle/combined")
async def get_combined(request: Request):
    c = _require_cache()
    raw_combined = c["combined"].get("combined_score", 50.0)
    return api_response({
        **c["combined"],
        "combined_score": raw_combined,
        "arc_display": round(arc_display_score(raw_combined), 1),
        "scores": {
            "btc":   c["btc_scores"].get("btc_score",   50.0),
            "eth":   c["eth_scores"].get("eth_score",   50.0),
            "macro": c["macro_scores"].get("macro_score", 50.0),
        },
        "refreshed_at": c.get("refreshed_at", 0),
    })


@app.get("/api/history")
async def get_history(request: Request):
    c       = _require_cache()
    hist    = c.get("score_history", {"btc": [], "eth": [], "macro": [], "combined": []})
    tvl_raw = c["raw"].get("tvl_series", [])
    fg_hist = c["raw"]["fear_greed"]["history"][-90:]

    tvl_hist = [{"t": i["t"], "v": safe_float(i["v"]) / 1e9} for i in tvl_raw[-365:]]

    return api_response({
        "scores":   hist,
        "tvl":      tvl_hist,
        "fg":       fg_hist,
        "btc_full": _prices_to_series(c["raw"]["btc_prices"], 730),
        "eth_full": _prices_to_series(c["raw"]["eth_prices"], 730),
        "walcl":    [{"t": i["t"], "v": safe_float(i["v"]) / 1e6}
                     for i in c["raw"].get("walcl_series", [])[-260:]],
    })


@app.get("/api/fear-greed")
async def get_fear_greed(request: Request):
    c = _require_cache()
    return api_response(c["raw"]["fear_greed"])


@app.get("/api/cycle-anchor")
async def get_cycle_anchor(request: Request):
    """Cycle Anchor Engine: objective cycle timing from historical Bitcoin structure."""
    try:
        result = compute_cycle_anchor()
        fresh_days = compute_days_since_bottom()
        result["days_since_bottom"] = fresh_days
        result["days_since_cycle_bottom"] = fresh_days
        return api_response(result)
    except Exception as e:
        logger.warning("cycle_anchor error: %s", e)
        return api_response({
            "days_since_bottom": compute_days_since_bottom(),
            "days_since_cycle_bottom": compute_days_since_bottom(),
            "error": str(e),
        })


# Phase groups for phase-coherent decision engine (get_arc_summary, historical-returns)
BEAR_PHASES = ["Early Bear", "Mid Bear", "Late Bear", "Deep Bear"]
BULL_PHASES = ["Early Bull", "Mid Bull"]
ACCUMULATION_PHASES = ["Accumulation", "Deep Accumulation"]
LATE_BULL_PHASES = ["Late Bull"]


def _phase_group(ph):
    if ph in BEAR_PHASES:
        return "bear"
    if ph in LATE_BULL_PHASES:
        return "late_bull"
    if ph in ACCUMULATION_PHASES:
        return "accumulation"
    if ph in BULL_PHASES:
        return "bull"
    return "unknown"


def get_zone_name(arc_score: float) -> str:
    if arc_score < 30:
        return "Deep Value"
    if arc_score < 40:
        return "Accumulation"
    if arc_score < 60:
        return "Expansion"
    if arc_score < 70:
        return "Risk Rising"
    return "Euphoria"


def _get_expected_range(arc: float, hist_returns: dict = None, high_risk_drawdown: dict = None) -> dict:
    """
    Expected range from historical zone stats (backtest). Always shows zone-based stats,
    independent of phase. Uses hist_returns["zones"] (deep_value, accumulation, expansion, risk_rising, euphoria).
    """
    arc = float(arc)
    if arc < 30:
        zone_key = "deep_value"
        zone_name = "Deep Value"
    elif arc < 40:
        zone_key = "accumulation"
        zone_name = "Accumulation"
    elif arc < 60:
        zone_key = "expansion"
        zone_name = "Expansion"
    elif arc < 70:
        zone_key = "risk_rising"
        zone_name = "Risk Rising"
    else:
        zone_key = "euphoria"
        zone_name = "Euphoria"

    zones = (hist_returns or {}).get("zones") or {}
    z = zones.get(zone_key) or {}
    zone_name = z.get("zone_name") or zone_name
    entry_count = z.get("entry_count")
    avg_12m = z.get("avg_12m")
    win_rate_12m = z.get("win_rate_12m")

    if zone_key == "euphoria":
        dd = high_risk_drawdown or {}
        avg_dd = z.get("avg_drawdown") or dd.get("avg_drawdown")
        if avg_dd is not None:
            label = "Avg -%s%% from peak" % (abs(int(round(avg_dd))),)
        else:
            label = "Euphoria — High risk"
        sublabel = "%s entries" % (entry_count if entry_count is not None else 0) if entry_count else "—"
        return {
            "type": "drawdown",
            "label": label,
            "sublabel": sublabel,
            "zone": zone_name,
        }

    if zone_key == "risk_rising":
        if avg_12m is not None:
            label = "+%s%% avg (12M) — REDUCE" % (int(round(avg_12m)),)
        else:
            label = "REDUCE"
        sublabel = ("%s%% win rate · %s entries" % (int(round(win_rate_12m)), entry_count)) if (win_rate_12m is not None and entry_count is not None) else (("%s entries" % entry_count) if entry_count is not None else "—")
        return {
            "type": "reduce",
            "label": label,
            "sublabel": sublabel,
            "zone": zone_name,
        }

    # forward_return: Deep Value, Accumulation, Expansion
    if avg_12m is not None:
        label = "+%s%% avg (12M)" % (int(round(avg_12m)),)
    else:
        label = zone_name
    if win_rate_12m is not None and entry_count is not None:
        sublabel = "%s%% win rate · %s entries" % (int(round(win_rate_12m)), entry_count)
    elif entry_count is not None:
        sublabel = "%s entries" % entry_count
    else:
        sublabel = "—"
    return {
        "type": "forward_return",
        "label": label,
        "sublabel": sublabel,
        "zone": zone_name,
    }


@app.get("/api/arc-summary")
async def get_arc_summary(request: Request):
    """ARC Index consolidated summary. arc_score from unified compute_arc_score(). Phase-coherent position/allocation."""
    c = _require_cache()
    raw = c["raw"]
    btc = c["btc_scores"]
    mac = c["macro_scores"]
    com = c["combined"]
    net_liq_series = raw.get("net_liq_series", [])
    tga_series = raw.get("tga_series", [])
    net_liq_current = float(net_liq_series[-1]["v"]) if net_liq_series else None
    tga_current = float(tga_series[-1]["v"]) if tga_series else None
    walcl = [item["v"] for item in raw.get("walcl_series", [])]
    stable = [item["v"] for item in raw.get("stable_series", [])]
    _ohlc = c.get("ohlc_latest", {})
    current_arc = round(
        compute_arc_score(
            raw.get("btc_prices", []),
            raw.get("fear_greed", {}).get("current", 50.0),
            walcl,
            stable,
            raw.get("net_liq_series"),
            weekly_high=_ohlc.get("high"),
            weekly_low=_ohlc.get("low"),
        ),
        1,
    )
    btc_prices = raw.get("btc_prices", [])
    eth_prices = raw.get("eth_prices", [])
    btc_price = float(btc_prices[-1]) if btc_prices else 0.0
    eth_price = float(eth_prices[-1]) if eth_prices else 0.0
    eth_btc_ratio = eth_price / btc_price if btc_price > 0 else None
    ath_for_summary = max(btc_prices) if btc_prices else btc_price
    ath_for_summary = safe_float(raw.get("btc_market", {}).get("ath", ath_for_summary)) or ath_for_summary
    out = {
        "arc_score":   current_arc,
        "arc_display": round(arc_display_score(current_arc), 1),
        "zone_name":   get_zone_name(arc_display_score(current_arc)),
        "btc_score":   round(btc.get("btc_score", 50.0), 1),
        "eth_score":   round(c["eth_scores"].get("eth_score", 50.0), 1),
        "macro_score": round(mac.get("macro_score", 50.0), 1),
        "regime":      mac.get("regime", "NEUTRAL") or "NEUTRAL",
        "decision":    "HOLD",
        "confidence":  round(com.get("confidence", 50.0), 1),
        "fear_greed":  raw["fear_greed"]["current"],
        "eth_btc_signal": get_eth_btc_signal(eth_btc_ratio) if eth_btc_ratio is not None else None,
        "components": {
            "ma_200w":    round(btc.get("ma_200w", 50.0), 1),
            "drawdown":   round(btc.get("drawdown", 50.0), 1),
            "fear_greed": round(btc.get("fear_greed", 50.0), 1),
            "liquidity":  round(btc.get("macro_liq", 50.0), 1),
            "net_liq":    net_liq_current,
            "tga":        tga_current,
        },
        "short_term": btc.get("short_term", {}),
        "days_since_top": compute_days_since_top(),
        "cycle_top_date": TENTATIVE_CYCLE_TOP.isoformat(),
        "cycle_top_confirmed": False,
        "btc_price": round(btc_price, 0),
        "btc_ath": round(ath_for_summary, 2),
    }
    # Phase for phase-coherent position/allocation (same inputs as /api/analyzer)
    phase = None
    try:
        btc_prices = raw.get("btc_prices", [])
        btc_price = float(btc_prices[-1]) if btc_prices else 0.0
        ath_price = max(btc_prices) if btc_prices else btc_price
        ath_price = safe_float(raw.get("btc_market", {}).get("ath", ath_price))
        ma_200w = safe_float(btc.get("ma_200w_raw", 0.0))
        anchor_data = compute_cycle_anchor()
        days_since_bottom = anchor_data.get("days_since_cycle_bottom", 0)
        st = btc.get("short_term", {})
        st_ctx = get_short_term_context(
            arc_score=current_arc,
            days_since_bottom=days_since_bottom,
            rsi_score=st.get("rsi", 50.0),
            funding_score=st.get("funding", 50.0),
            power_law_score=st.get("power_law", 50.0),
            mvrv_score=st.get("mvrv", 50.0),
            btc_price=btc_price,
            ath_price=ath_price,
            ma_200w=ma_200w,
        )
        phase = st_ctx.get("phase_label")
    except Exception:
        pass
    out["phase_context"] = phase
    out["phase_group"] = _phase_group(phase)
    out["seasonality"] = get_seasonal_context()
    try:
        from analyzer import compute_arc_momentum
        results = CACHE.get("backtest_results")
        if not results:
            # Do not block on backtest: refresh_cache() fills CACHE; next request may have full data.
            results = []
        fwd = CACHE.get("fwd_returns")
        if fwd is None and results:
            from historical_returns import compute_arc_forward_returns
            fwd = compute_arc_forward_returns(results)
        dd_data = CACHE.get("high_risk_drawdown")
        if dd_data is None and results:
            from historical_returns import compute_high_risk_drawdown
            dd_data = compute_high_risk_drawdown(results)
        logger.info("backtest sample: %s", results[:2] if results else "empty")
        arc_history = [
            {"date": r.get("date", ""), "arc_score": r.get("arc_score", r.get("score", 50)), "score": r.get("arc_score", r.get("score", 50))}
            for r in results if r and (r.get("date") and (r.get("arc_score") is not None or r.get("score") is not None))
        ]
        from scoring import compute_arc_momentum as scoring_arc_momentum
        momentum = scoring_arc_momentum(arc_history, days=30)
        out["arc_momentum"] = momentum
        out["arc_momentum_30d"] = momentum["value"]
        out["arc_momentum_label"] = momentum["label"]
        momentum_data = compute_arc_momentum(arc_history, float(current_arc))
        out["arc_percentile"] = momentum_data.get("arc_percentile")
        out["arc_percentile_label"] = momentum_data.get("arc_percentile_label")

        from historical_returns import compute_arc_forward_returns, compute_high_risk_drawdown
        from analyzer import compute_confidence_calibrated
        from decision_engine import get_position

        if fwd is None:
            fwd = []
        if dd_data is None:
            dd_data = {}
        hist_returns = CACHE.get("hist_returns") or {}
        expected = _get_expected_range(arc_display_score(current_arc), hist_returns=hist_returns, high_risk_drawdown=dd_data)
        out["expected_range"] = expected
        out["expected_range_label"] = expected.get("label", "N/A")

        win_rate = None
        for b in fwd or []:
            if b.get("arc_min", 0) <= current_arc < b.get("arc_max", 100):
                win_rate = b.get("win_rate_12m")
                break
        conf_val, conf_label = compute_confidence_calibrated(
            arc=current_arc,
            fear_greed=raw.get("fear_greed", {}).get("current", 50),
            momentum=out.get("arc_momentum_30d") or 0,
            percentile=out.get("arc_percentile") or 50,
            win_rate=win_rate,
        )
        out["confidence"] = conf_val
        out["confidence_label"] = conf_label
        out["position"] = get_position(
            current_arc,
            out.get("arc_momentum_30d") if out.get("arc_momentum_30d") is not None else 0,
            conf_val,
        )
        out["decision"] = out["position"]
        _alloc = {
            "BUY": "60-80%",
            "ACCUMULATE": "50-70%",
            "HOLD": "40-60%",
            "REDUCE": "20-40%",
            "SELL": "0-20%",
        }
        out["allocation"] = _alloc.get(out["position"], "40-60%")

        # Phase-coherent overrides (phase takes priority over ARC-only)
        days_since_top = out.get("days_since_top") or 0
        btc_prices = raw.get("btc_prices", [])
        btc_price = float(btc_prices[-1]) if btc_prices else 0.0
        ath_price = max(btc_prices) if btc_prices else btc_price
        ath_price = safe_float(raw.get("btc_market", {}).get("ath", ath_price)) or ath_price
        drawdown_from_top = 0.0
        if btc_prices and ath_price and ath_price > 0:
            drawdown_from_top = (btc_price - ath_price) / ath_price
        bottom_formation = (
            phase in BEAR_PHASES
            and (days_since_top >= 300 or (days_since_top >= 150 and drawdown_from_top <= -0.40))
        )
        out["bottom_formation"] = bottom_formation
        out["bottom_formation_note"] = (
            "150+ days since top + 40%+ drawdown — bottom formation possible" if bottom_formation else None
        )
        if phase in BEAR_PHASES:
            arc_raw = current_arc
            if bottom_formation:
                if arc_raw > 39:
                    out["position"] = "LOW ACCUMULATION"
                    out["decision"] = out["position"]
                    out["allocation"] = "20-35%"
                    out["confidence_label"] = "Low-Moderate"
                    out["tactical_label"] = "Low Accumulation Zone"
                    out["tactical_color"] = "#10b981"
                elif arc_raw > 29:
                    out["position"] = "ACCUMULATION"
                    out["decision"] = out["position"]
                    out["allocation"] = "35-50%"
                    out["confidence_label"] = "Moderate"
                    out["tactical_label"] = "Accumulation Zone"
                    out["tactical_color"] = "#10b981"
                elif arc_raw > 24:
                    out["position"] = "STRONG ACCUMULATION"
                    out["decision"] = out["position"]
                    out["allocation"] = "50-70%"
                    out["confidence_label"] = "Moderate-High"
                    out["tactical_label"] = "Strong Accumulation Zone"
                    out["tactical_color"] = "#10b981"
                else:
                    out["position"] = "STRONG ACCUMULATION"
                    out["decision"] = out["position"]
                    out["allocation"] = "50-70%"
                    out["confidence_label"] = "Moderate-High"
                    out["tactical_label"] = "Strong Accumulation Zone"
                    out["tactical_color"] = "#10b981"
            else:
                if arc_raw > 39:
                    out["position"] = "WAIT — Bear Market"
                    out["decision"] = out["position"]
                    out["allocation"] = "0-20%"
                    out["confidence_label"] = "Low"
                    out["tactical_label"] = "Bear Market — Wait for lower ARC"
                    out["tactical_color"] = "#6b7280"
                elif arc_raw > 29:
                    out["position"] = "LOW ACCUMULATION"
                    out["decision"] = out["position"]
                    out["allocation"] = "20-35%"
                    out["confidence_label"] = "Low-Moderate"
                    out["tactical_label"] = "Low Accumulation Zone"
                    out["tactical_color"] = "#10b981"
                elif arc_raw > 24:
                    out["position"] = "ACCUMULATION"
                    out["decision"] = out["position"]
                    out["allocation"] = "35-50%"
                    out["confidence_label"] = "Moderate"
                    out["tactical_label"] = "Accumulation Zone"
                    out["tactical_color"] = "#10b981"
                else:
                    out["position"] = "STRONG ACCUMULATION"
                    out["decision"] = out["position"]
                    out["allocation"] = "50-70%"
                    out["confidence_label"] = "Moderate-High"
                    out["tactical_label"] = "Strong Accumulation Zone"
                    out["tactical_color"] = "#10b981"
        elif phase in LATE_BULL_PHASES:
            out["position"] = "REDUCE"
            out["decision"] = out["position"]
            out["allocation"] = "20-40%" if current_arc < 60 else "0-20%"
            out["confidence_label"] = "Low-Moderate"
        elif phase in ACCUMULATION_PHASES:
            if current_arc < 35:
                out["position"] = "ACCUMULATE"
                out["decision"] = out["position"]
                out["allocation"] = "80-100%"
                out["confidence_label"] = "High"
            elif current_arc < 50:
                out["position"] = "BUY"
                out["decision"] = out["position"]
                out["allocation"] = "60-80%"
                out["confidence_label"] = "Moderate-High"
            else:
                out["position"] = "HOLD"
                out["decision"] = out["position"]
                out["allocation"] = "40-60%"
                out["confidence_label"] = "Moderate"
        elif phase in BULL_PHASES:
            if current_arc < 50:
                out["position"] = "BUY"
                out["decision"] = out["position"]
                out["allocation"] = "60-80%"
                out["confidence_label"] = "Moderate-High"
            elif current_arc < 65:
                out["position"] = "HOLD"
                out["decision"] = out["position"]
                out["allocation"] = "40-60%"
                out["confidence_label"] = "Moderate"
            else:
                out["position"] = "REDUCE"
                out["decision"] = out["position"]
                out["allocation"] = "20-40%"
                out["confidence_label"] = "Low-Moderate"
    except Exception as e:
        logger.warning("arc-summary momentum: %s", e)
        out["arc_momentum_30d"] = None
        out["arc_momentum_label"] = None
        out["arc_percentile"] = None
        out["arc_percentile_label"] = None
        out["expected_range"] = {"avg_12m": None, "range_low": None, "range_high": None, "label": "N/A", "type": "forward_return"}
        out["expected_range_label"] = "N/A"
        out["confidence_label"] = "Moderate"
        out["position"] = "HOLD"
    try:
        from liquidity_engine import compute_net_liquidity
        walcl_series = raw.get("walcl_series", [])
        tga_series = raw.get("tga_series", [])
        rrp_series = raw.get("rrp_series", [])
        walcl = float(walcl_series[-1]["v"]) if walcl_series else 0
        tga = float(tga_series[-1]["v"]) if tga_series else 0
        rrp = float(rrp_series[-1]["v"]) if rrp_series else 0
        out["net_liquidity_data"] = compute_net_liquidity(walcl=walcl, tga=tga, rrp=rrp)
    except Exception as e2:
        logger.warning("arc-summary net_liquidity_data: %s", e2)
        out["net_liquidity_data"] = None
    return api_response(out)


class SubscribeRequest(BaseModel):
    email: str
    source: str = "dashboard"


@app.post("/api/subscribe")
@limiter.limit("10/minute")
async def subscribe(request: Request, req: SubscribeRequest):
    try:
        if "@" not in req.email or "." not in req.email:
            raise HTTPException(status_code=400, detail="Invalid email")

        # Best-effort ARC metadata. Never fail the email capture if this errors.
        arc_data: dict = {}
        try:
            arc_resp = await get_arc_summary(request)
            if isinstance(arc_resp, dict):
                arc_data = arc_resp
            elif arc_resp is not None:
                body = getattr(arc_resp, "body", None)
                if body:
                    arc_data = json.loads(body)
        except Exception as meta_e:
            logger.warning("subscribe: ARC metadata unavailable: %s", meta_e)
            arc_data = {}

        email_clean = req.email.lower().strip()
        stored = False
        if supabase:
            full = {
                "email": email_clean,
                "source": req.source,
                "arc_score": arc_data.get("arc_display", 0),
                "zone": arc_data.get("zone_name", ""),
            }
            # Try progressively simpler payloads so a missing column / schema
            # mismatch never breaks the capture. Never raise 500 on storage.
            for attempt in (full, {"email": email_clean, "source": req.source}, {"email": email_clean}):
                try:
                    supabase.table("email_captures").upsert(attempt).execute()
                    stored = True
                    break
                except Exception as store_e:
                    logger.warning("subscribe: store attempt %s failed: %s", list(attempt.keys()), store_e)
            if not stored:
                logger.error("subscribe: ALL store attempts failed; LEAD email=%s source=%s", email_clean, req.source)
        else:
            logger.warning("Supabase not configured; LEAD email=%s source=%s", email_clean, req.source)

        return {"success": True, "message": "Successfully subscribed", "stored": stored}
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Subscribe error: %s", e)
        raise HTTPException(status_code=500, detail="Subscription failed")


class CheckoutRequest(BaseModel):
    user_id: str
    email: str
    plan: str = "monthly"  # "monthly" | "yearly"


class PortalRequest(BaseModel):
    user_id: str


@app.post("/api/checkout")
@limiter.limit("10/minute")
async def create_checkout(request: Request, req: CheckoutRequest):
    """Create Stripe Checkout Session for subscription upgrade."""
    price_id = _resolve_price_id(req.plan)
    if not STRIPE_SECRET_KEY or not price_id:
        raise HTTPException(status_code=503, detail="Stripe not configured")
    try:
        customer_id: Optional[str] = None
        if supabase:
            profile = (
                supabase.table("user_profiles")
                .select("stripe_customer_id")
                .eq("id", req.user_id)
                .single()
                .execute()
            )
            if profile.data and profile.data.get("stripe_customer_id"):
                customer_id = profile.data["stripe_customer_id"]

        if not customer_id:
            customer = stripe.Customer.create(
                email=req.email,
                metadata={"supabase_user_id": req.user_id},
            )
            customer_id = customer.id
            if supabase:
                supabase.table("user_profiles").update(
                    {"stripe_customer_id": customer_id}
                ).eq("id", req.user_id).execute()

        session = stripe.checkout.Session.create(
            customer=customer_id,
            mode="subscription",
            line_items=[{"price": price_id, "quantity": 1}],
            success_url="https://alphacycle.app/app?upgrade=success",
            cancel_url="https://alphacycle.app/app?upgrade=cancelled",
            subscription_data={
                "metadata": {"supabase_user_id": req.user_id},
            },
            metadata={"supabase_user_id": req.user_id, "plan": req.plan},
        )
        return {"checkout_url": session.url}
    except Exception as e:
        logger.error("Checkout error: %s", e)
        raise HTTPException(status_code=500, detail="Checkout failed")


@app.post("/api/create-portal-session")
@limiter.limit("10/minute")
async def create_portal_session(request: Request, req: PortalRequest):
    """Create a Stripe Billing Portal session so a subscriber can manage/cancel their plan.
    Billing-only: resolves the existing stripe_customer_id from the profile. Does not create or modify auth."""
    if not STRIPE_SECRET_KEY:
        raise HTTPException(status_code=503, detail="Stripe not configured")
    try:
        customer_id: Optional[str] = None
        if supabase:
            profile = (
                supabase.table("user_profiles")
                .select("stripe_customer_id")
                .eq("id", req.user_id)
                .single()
                .execute()
            )
            if profile.data and profile.data.get("stripe_customer_id"):
                customer_id = profile.data["stripe_customer_id"]
        if not customer_id:
            raise HTTPException(status_code=404, detail="No billing account found")
        session = stripe.billing_portal.Session.create(
            customer=customer_id,
            return_url="https://alphacycle.app/app",
        )
        return {"portal_url": session.url}
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Portal error: %s", e)
        raise HTTPException(status_code=500, detail="Portal session failed")


def _get_profile_by_user_id(user_id: str) -> dict:
    """Fetch current user_profiles row for webhook skip logic. Returns {} on error."""
    if not supabase:
        return {}
    try:
        r = supabase.table("user_profiles").select("plan, subscription_status").eq("id", user_id).single().execute()
        return r.data if r.data else {}
    except Exception:
        return {}


# AlphaCycle entitlement policy: Stripe status -> plan
# active,trialing,past_due -> paid; canceled,incomplete,incomplete_expired,paused,unpaid -> free
STRIPE_STATUS_TO_PLAN = {"active": "paid", "trialing": "paid", "past_due": "paid", "canceled": "free", "incomplete": "free", "incomplete_expired": "free", "paused": "free", "unpaid": "free"}


@app.post("/api/stripe-webhook")
async def stripe_webhook(request: Request):
    """Handle Stripe webhook events to update user plan. Always return 200 to Stripe."""
    if not STRIPE_WEBHOOK_SECRET:
        logger.warning("Webhook not configured")
        return {"received": True}
    payload = await request.body()
    sig_header = request.headers.get("stripe-signature", "")
    try:
        event = stripe.Webhook.construct_event(
            payload, sig_header, STRIPE_WEBHOOK_SECRET
        )
    except (ValueError, stripe.error.SignatureVerificationError) as e:
        logger.warning("Webhook signature failed: %s", e)
        return {"received": True}

    event_type = event.get("type", "")
    data = event.get("data", {}).get("object", {})
    logger.info("Stripe webhook: %s", event_type)

    meta_uid = (data.get("metadata") or {}).get("supabase_user_id")
    sub_uid: Optional[str] = None
    if data.get("subscription"):
        try:
            sub = stripe.Subscription.retrieve(data["subscription"])
            sub_uid = (sub.metadata or {}).get("supabase_user_id")
        except Exception:
            pass
    cust_uid: Optional[str] = None
    if data.get("customer") and supabase:
        try:
            profile = (
                supabase.table("user_profiles")
                .select("id")
                .eq("stripe_customer_id", data["customer"])
                .single()
                .execute()
            )
            if profile.data:
                cust_uid = profile.data["id"]
        except Exception:
            pass

    user_id = meta_uid or sub_uid or cust_uid
    logger.info("Webhook resolve: event=%s resolved_uid=%s (meta=%s, sub=%s, cust=%s)", event_type, user_id, meta_uid, sub_uid, cust_uid)

    if not user_id or not supabase:
        logger.warning("Webhook: no user_id found for event %s", event_type)
        return {"received": True}

    try:
        current = _get_profile_by_user_id(user_id)
    except Exception:
        current = {}

    if event_type == "checkout.session.completed":
        if current.get("plan") == "paid":
            logger.info("Webhook skip: user %s already %s for %s", user_id, "paid", event_type)
            return {"received": True}
        sub_id = data.get("subscription")
        supabase.table("user_profiles").update(
            {
                "plan": "paid",
                "stripe_subscription_id": sub_id,
                "subscription_status": "active",
                "stripe_customer_id": data.get("customer"),
            }
        ).eq("id", user_id).execute()
        logger.info("User %s upgraded to paid", user_id)

    elif event_type in ("customer.subscription.updated", "customer.subscription.renewed"):
        status = data.get("status", "")
        plan = STRIPE_STATUS_TO_PLAN.get(status, "free" if status else "free")
        if current.get("subscription_status") == status:
            logger.info("Webhook skip: user %s already %s for %s", user_id, status, event_type)
            return {"received": True}
        update: dict[str, Any] = {
            "plan": plan,
            "subscription_status": status,
        }
        if data.get("current_period_end"):
            update["current_period_end"] = datetime.utcfromtimestamp(
                data["current_period_end"]
            ).isoformat()
        supabase.table("user_profiles").update(update).eq("id", user_id).execute()
        logger.info("User %s subscription updated: %s -> %s", user_id, status, plan)

    elif event_type in ("customer.subscription.deleted", "customer.subscription.paused"):
        if current.get("plan") == "free":
            logger.info("Webhook skip: user %s already %s for %s", user_id, "free", event_type)
            return {"received": True}
        supabase.table("user_profiles").update(
            {
                "plan": "free",
                "subscription_status": "cancelled",
            }
        ).eq("id", user_id).execute()
        logger.info("User %s subscription cancelled", user_id)

    elif event_type == "invoice.payment_failed":
        if current.get("subscription_status") == "past_due":
            logger.info("Webhook skip: user %s already %s for %s", user_id, "past_due", event_type)
            return {"received": True}
        supabase.table("user_profiles").update(
            {
                "subscription_status": "past_due",
            }
        ).eq("id", user_id).execute()
        logger.warning("User %s payment failed", user_id)

    return {"received": True}


LEMONSQUEEZY_WEBHOOK_SECRET = os.getenv("LEMONSQUEEZY_WEBHOOK_SECRET", "").strip()
LS_STATUS_TO_PLAN = {
    "active": "paid", "on_trial": "paid", "past_due": "paid", "cancelled": "paid",
    "paused": "free", "unpaid": "free", "expired": "free",
}


def _get_profile_id_by_email(email: str) -> Optional[str]:
    """Resolve a user_profiles id by email (lowercased). None on miss/error."""
    if not email or not supabase:
        return None
    try:
        r = (
            supabase.table("user_profiles")
            .select("id")
            .eq("email", email.strip().lower())
            .single()
            .execute()
        )
        if r.data:
            return r.data.get("id")
    except Exception:
        pass
    return None


@app.post("/api/lemonsqueezy-webhook")
async def lemonsqueezy_webhook(request: Request):
    """Lemon Squeezy (Merchant of Record) subscription webhooks -> user plan.
    Always returns 200. Resolves user via meta.custom_data.user_id, fallback email.
    Set LEMONSQUEEZY_WEBHOOK_SECRET env to enable signature verification."""
    payload = await request.body()
    if not LEMONSQUEEZY_WEBHOOK_SECRET:
        logger.warning("LS webhook not configured (no secret)")
        return {"received": True}
    import hmac as _hmac, hashlib as _hashlib
    digest = _hmac.new(
        LEMONSQUEEZY_WEBHOOK_SECRET.encode("utf-8"), payload, _hashlib.sha256
    ).hexdigest()
    sig = (request.headers.get("X-Signature", "") or "").strip()
    if not _hmac.compare_digest(digest, sig):
        logger.warning("LS webhook signature failed")
        return {"received": True}

    try:
        body = await request.json()
    except Exception:
        return {"received": True}

    meta = body.get("meta", {}) or {}
    event_name = meta.get("event_name", "")
    custom = meta.get("custom_data", {}) or {}
    attrs = (body.get("data", {}) or {}).get("attributes", {}) or {}
    status = (attrs.get("status") or "").lower()
    email = attrs.get("user_email") or attrs.get("email") or ""
    logger.info("LS webhook: %s status=%s", event_name, status)

    if not supabase:
        return {"received": True}

    user_id = custom.get("user_id") or _get_profile_id_by_email(email)
    if not user_id:
        logger.warning("LS webhook: no user resolved (event=%s email=%s)", event_name, email)
        return {"received": True}

    if event_name == "subscription_expired" or status in ("expired", "unpaid"):
        plan = "free"
    else:
        plan = LS_STATUS_TO_PLAN.get(
            status,
            "paid" if event_name in ("subscription_created", "subscription_payment_success") else "free",
        )

    try:
        supabase.table("user_profiles").update(
            {"plan": plan, "subscription_status": status or event_name}
        ).eq("id", user_id).execute()
        logger.info("LS webhook: user %s -> plan=%s (%s)", user_id, plan, event_name)
    except Exception as e:
        logger.error("LS webhook update failed: %s", e)

    return {"received": True}


@app.get("/api/auth/profile")
@limiter.limit("20/minute")
async def get_profile(request: Request, user=Security(get_current_user)):
    if not user:
        return {"authenticated": False, "plan": "anonymous", "subscription_status": "inactive"}

    if not supabase:
        logger.warning("Supabase not configured; returning fallback")
        return {"authenticated": True, "plan": "free", "email": user.email, "subscription_status": "inactive"}

    try:
        profile = (
            supabase.table("user_profiles")
            .select("*")
            .eq("id", str(user.id))
            .single()
            .execute()
        )
    except Exception as e:
        logger.error("Profile fetch failed for user %s: %s", user.id, e)
        return {
            "authenticated": True,
            "plan": "free",
            "email": user.email,
            "subscription_status": "unknown",
            "error": "profile_fetch_failed",
        }

    if not profile.data:
        try:
            supabase.table("user_profiles").insert({
                "id": str(user.id),
                "email": user.email,
                "plan": "free",
            }).execute()
        except Exception as e:
            logger.error("Profile create failed for user %s: %s", user.id, e)
            return {
                "authenticated": True,
                "plan": "free",
                "email": user.email,
                "subscription_status": "inactive",
                "error": "profile_fetch_failed",
            }
        return {
            "authenticated": True,
            "plan": "trial",
            "email": user.email,
            "trial_active": True,
            "trial_ends_at": (datetime.utcnow() + timedelta(days=7)).isoformat(),
            "subscription_status": "inactive",
        }

    plan = profile.data.get("plan", "free")
    sub_status = profile.data.get("subscription_status", "inactive")
    created_at = profile.data.get("created_at", "")

    trial_active = False
    trial_ends_at = None
    if plan == "free" and created_at:
        try:
            created = datetime.fromisoformat(str(created_at).replace("Z", "+00:00").replace("+00:00", ""))
            trial_end = created + timedelta(days=7)
            trial_active = datetime.utcnow() < trial_end
            trial_ends_at = trial_end.isoformat()
        except Exception:
            trial_active = False

    effective_plan = plan
    if plan == "free" and trial_active:
        effective_plan = "trial"

    return {
        "authenticated": True,
        "plan": effective_plan,
        "email": user.email,
        "trial_active": trial_active,
        "trial_ends_at": trial_ends_at,
        "subscription_status": sub_status,
    }


@app.get("/api/snapshot/today")
async def get_today_snapshot(request: Request):
    """Save and return today's ARC snapshot."""
    snap = _save_today_snapshot()
    return api_response(snap)


@app.get("/api/snapshots")
async def get_snapshots(request: Request):
    """Return all saved daily snapshots."""
    if not SNAPSHOT_FILE.exists():
        return api_response({"snapshots": []})
    try:
        data = json.loads(SNAPSHOT_FILE.read_text())
    except Exception:
        data = []
    return api_response({"snapshots": data})


@app.get("/api/backtest")
async def get_backtest(request: Request):
    """
    Historical AlphaCycle backtest endpoint.
    Returns BTC price+score history from cache when available (fast); else runs daily full backtest once.
    """
    try:
        if CACHE.get("backtest_results"):
            results = list(CACHE["backtest_results"])
        else:
            data = await run_daily_backtest_full()
            results = list((data.get("results") or []) if isinstance(data, dict) else [])
        c = CACHE
        if c and c.get("raw"):
            raw = c["raw"]
            walcl = [item["v"] for item in raw.get("walcl_series", [])]
            stable = [item["v"] for item in raw.get("stable_series", [])]
            _ohlc = c.get("ohlc_latest", {})
            try:
                live_arc = compute_arc_score(
                    raw.get("btc_prices", []),
                    raw.get("fear_greed", {}).get("current", 50.0),
                    walcl,
                    stable,
                    raw.get("net_liq_series"),
                    weekly_high=_ohlc.get("high"),
                    weekly_low=_ohlc.get("low"),
                )
                btc_prices = raw.get("btc_prices", [])
                live_price = float(btc_prices[-1]) if btc_prices else 0.0
                if results:
                    results[-1] = dict(results[-1])
                    disp = round(arc_display_score(live_arc), 2)
                    results[-1]["score"] = disp
                    results[-1]["score_display"] = disp
                    results[-1]["price"] = round(live_price, 2)
            except Exception:
                pass
        return api_response({"results": results})
    except Exception as e:
        logger.exception("Backtest endpoint failed")
        return api_response({"results": [], "error": str(e)})


@app.get("/api/zone-history")
async def get_zone_history(request: Request):
    c = _require_cache()
    results = CACHE.get("backtest_results") or []
    arc_history = []
    for r in results:
        if not r:
            continue
        date = r.get("date")
        arc_val = r.get("score_display", r.get("arc_score", r.get("score")))
        price = r.get("btc_price", r.get("price"))
        if not (date and arc_val is not None and price is not None):
            continue
        arc_history.append(
            {
                "date": date,
                "arc_score": float(arc_val),
                "btc_price": float(price),
            }
        )
    zone_periods = compute_zone_history(arc_history)
    current_zone = None
    current_since = None
    current_weeks = 0
    if zone_periods:
        current = zone_periods[0]
        current_zone = current.get("zone")
        current_since = current.get("from")
        current_weeks = int(current.get("weeks") or 0)

    # Override context with live ARC if available (cached backtest can lag)
    live_arc = None
    try:
        combined = CACHE.get("combined", {})
        live_arc = combined.get("combined_score")
    except Exception:
        live_arc = None

    if live_arc is not None:
        live_zone = get_zone_name(float(live_arc))
        if live_zone != current_zone:
            # Live ARC is in a different zone than the confirmed backtest zone.
            # Do not override the confirmed zone yet; mark live as transitioning.
            return api_response(
                {
                    "zone_history": zone_periods,
                    "current_zone": current_zone,
                    "current_zone_since": current_since,
                    "current_zone_weeks": current_weeks,
                    "live_zone": live_zone,
                    "live_zone_confirmed": False,
                }
            )

    return api_response(
        {
            "zone_history": zone_periods,
            "current_zone": current_zone,
            "current_zone_since": current_since,
            "current_zone_weeks": current_weeks,
            "live_zone": current_zone,
            "live_zone_confirmed": True,
        }
    )


@app.get("/api/historical-returns")
async def get_historical_returns(request: Request):
    """
    Average forward returns by ARC zone from backtest data.
    Served from cache when available (fast).
    """
    try:
        if CACHE.get("hist_returns"):
            result = CACHE["hist_returns"]
        else:
            from historical_returns import compute_historical_returns, _empty_returns
            bt = await run_daily_backtest_full()
            bt_list = bt.get("results", []) if isinstance(bt, dict) else []
            arc_history_for_zones = []
            for r in bt_list:
                if not r:
                    continue
                d = r.get("date")
                arc_val = r.get("score_display", r.get("arc_score", r.get("score")))
                price = r.get("btc_price", r.get("price"))
                if d and arc_val is not None and price is not None:
                    arc_history_for_zones.append(
                        {
                            "date": d,
                            "arc_score": float(arc_val),
                            "btc_price": float(price),
                        }
                    )
            zone_periods = compute_zone_history(arc_history_for_zones) if arc_history_for_zones else []
            result = compute_historical_returns(bt_list, zone_periods=zone_periods or None)
        if result.get("zones", {}).get("risk_rising"):
            result["zones"]["risk_rising"]["display_mode"] = "reduce"
            result["zones"]["risk_rising"]["display_label"] = "REDUCE — DO NOT BUY"
        if result.get("zones", {}).get("euphoria"):
            dd = CACHE.get("high_risk_drawdown") or {}
            result["zones"]["euphoria"]["display_mode"] = "drawdown"
            result["zones"]["euphoria"]["avg_drawdown"] = dd.get("avg_drawdown")
            result["zones"]["euphoria"]["max_drawdown"] = dd.get("max_drawdown")
            result["zones"]["euphoria"]["min_drawdown"] = dd.get("min_drawdown")
        phase = None
        try:
            c = _require_cache()
            raw = c["raw"]
            btc = c["btc_scores"]
            walcl = [x["v"] for x in raw.get("walcl_series", [])]
            stable = [x["v"] for x in raw.get("stable_series", [])]
            _ohlc = c.get("ohlc_latest", {})
            current_arc = compute_arc_score(
                raw.get("btc_prices", []),
                raw.get("fear_greed", {}).get("current", 50.0),
                walcl,
                stable,
                raw.get("net_liq_series"),
                weekly_high=_ohlc.get("high"),
                weekly_low=_ohlc.get("low"),
            )
            btc_prices = raw.get("btc_prices", [])
            btc_price = float(btc_prices[-1]) if btc_prices else 0.0
            ath_price = max(btc_prices) if btc_prices else btc_price
            ath_price = safe_float(raw.get("btc_market", {}).get("ath", ath_price))
            ma_200w = safe_float(btc.get("ma_200w_raw", 0.0))
            anchor_data = compute_cycle_anchor()
            days_since_bottom = anchor_data.get("days_since_cycle_bottom", 0)
            st = btc.get("short_term", {})
            st_ctx = get_short_term_context(
                arc_score=current_arc,
                days_since_bottom=days_since_bottom,
                rsi_score=st.get("rsi", 50.0),
                funding_score=st.get("funding", 50.0),
                power_law_score=st.get("power_law", 50.0),
                mvrv_score=st.get("mvrv", 50.0),
                btc_price=btc_price,
                ath_price=ath_price,
                ma_200w=ma_200w,
            )
            phase = st_ctx.get("phase_label")
        except Exception:
            pass
        result["phase_group"] = _phase_group(phase)
        return api_response(result)
    except Exception as e:
        logger.error("historical_returns error: %s", e)
        try:
            from historical_returns import _empty_returns
            return api_response({**_empty_returns(), "error": str(e)})
        except Exception:
            return api_response({"zones": {}, "best_entry_zone": None, "sample_events": [], "data_points_used": 0, "error": str(e)})


@app.get("/api/arc-forward-returns")
async def get_arc_forward_returns(request: Request):
    """Forward returns by finer ARC buckets (0-25, 25-35, ...). From cache when available."""
    try:
        if CACHE.get("fwd_returns"):
            return api_response({"buckets": CACHE["fwd_returns"]})
        from historical_returns import compute_arc_forward_returns
        bt = await run_daily_backtest_full()
        bt_list = bt.get("results", []) if isinstance(bt, dict) else []
        results = compute_arc_forward_returns(bt_list)
        return api_response({"buckets": results})
    except Exception as e:
        logger.error("arc_forward_returns error: %s", e)
        return api_response({"buckets": [], "error": str(e)})


@app.get("/api/history-daily")
async def get_history_daily(request: Request):
    """Daily ARC scores for last 365 days — sliced from full daily backtest."""
    try:
        all_results = CACHE.get("backtest_results", [])
        if not all_results:
            bt = await run_daily_backtest_full()
            all_results = bt.get("results", [])

        results = list(all_results[-365:]) if len(all_results) > 365 else list(all_results)

        if not results:
            return api_response({"results": [], "count": 0, "interval": "daily", "error": "no data"})

        c = CACHE
        if c and c.get("raw"):
            raw = c["raw"]
            walcl = [item["v"] for item in raw.get("walcl_series", [])]
            stable = [item["v"] for item in raw.get("stable_series", [])]
            try:
                _ohlc = c.get("ohlc_latest", {})
                live_arc = compute_arc_score(
                    raw.get("btc_prices", []),
                    raw.get("fear_greed", {}).get("current", 50.0),
                    walcl,
                    stable,
                    raw.get("net_liq_series"),
                    weekly_high=_ohlc.get("high"),
                    weekly_low=_ohlc.get("low"),
                )
                btc_prices = raw.get("btc_prices", [])
                live_price = float(btc_prices[-1]) if btc_prices else results[-1]["price"]
                results[-1] = dict(results[-1])
                results[-1]["score"] = round(live_arc, 2)
                results[-1]["score_display"] = round(arc_display_score(live_arc), 2)
                results[-1]["price"] = round(live_price, 2)
            except Exception as e:
                logger.warning("history-daily live override failed: %s", e)

        return api_response({
            "results": results,
            "count": len(results),
            "interval": "daily",
        })
    except Exception as e:
        logger.error("history-daily error: %s", e)
        return api_response({"results": [], "count": 0, "interval": "daily", "error": str(e)})


@app.get("/api/liquidity-regime")
async def get_liquidity_regime(request: Request):
    """
    Global Liquidity Regime Engine™ endpoint.
    Uses WALCL, stablecoins, BTC and macro proxies from cache.
    """
    c = _require_cache()
    raw = c["raw"]

    walcl_series = raw.get("walcl_series", [])
    stable_series = raw.get("stable_series", [])
    btc_prices = raw.get("btc_prices", [])
    eth_prices = raw.get("eth_prices", [])
    us10y_series = raw.get("us10y_series", [])
    dxy_series = raw.get("dxy_series", [])

    data = compute_liquidity_regime(
        walcl_series=walcl_series,
        stablecoin_series=stable_series,
        btc_prices=btc_prices,
        eth_prices=eth_prices,
        us10y_series=us10y_series,
        dxy_series=dxy_series,
    )
    return api_response(data)


@app.get("/api/analyzer")
@limiter.limit("30/minute")
async def get_analyzer(request: Request):
    cached = _get_cached_response("analyzer")
    if cached is not None:
        return api_response(cached)
    c = _require_cache()
    raw = c["raw"]
    try:
        btc_prices = raw.get("btc_prices", [])
        btc_price = float(btc_prices[-1]) if btc_prices else 0.0
        ath_price = max(btc_prices) if btc_prices else btc_price
        btc_drawdown = ((btc_price - ath_price) / ath_price * 100) if ath_price > 0 else -30.0
        score_history = c.get("score_history", {}).get("combined", [])
        walcl = [x["v"] for x in raw.get("walcl_series", [])]
        stable = [x["v"] for x in raw.get("stable_series", [])]
        liquidity_trend = c["macro_scores"].get("walcl_trend", 50.0)
        ma_200w = safe_float(c["btc_scores"].get("ma_200w_raw", 0.0))
        result = _analyzer.analyze(
            combined_score    = c["combined"].get("combined_score", 50.0),
            btc_score         = c["btc_scores"].get("btc_score", 50.0),
            eth_score         = c["eth_scores"].get("eth_score", 50.0),
            macro_score       = c["macro_scores"].get("macro_score", 50.0),
            fear_greed        = raw["fear_greed"]["current"],
            btc_price         = btc_price,
            btc_drawdown_pct  = btc_drawdown,
            liquidity_trend   = liquidity_trend,
            score_history     = score_history,
            btc_price_history = btc_prices,
            ma_200w           = ma_200w,
            ath_price         = safe_float(raw.get("btc_market", {}).get("ath", ath_price)),
        )
        try:
            anchor_data = compute_cycle_anchor()
            days_since = anchor_data.get("days_since_cycle_bottom", 0)
            st = c["btc_scores"].get("short_term", {})
            st_ctx = get_short_term_context(
                arc_score=result.get("alpha_cycle_position", 50.0),
                days_since_bottom=days_since or 0,
                rsi_score=st.get("rsi", 50.0),
                funding_score=st.get("funding", 50.0),
                power_law_score=st.get("power_law", 50.0),
                mvrv_score=st.get("mvrv", 50.0),
                btc_price=btc_price,
                ath_price=ath_price,
                ma_200w=ma_200w,
            )
            result["short_term_context"] = st_ctx
            result["days_since_top"] = st_ctx.get("days_since_top")
            result["cycle_top_date"] = st_ctx.get("cycle_top_date", TENTATIVE_CYCLE_TOP.isoformat())
            result["cycle_top_confirmed"] = False
        except Exception as e:
            logger.warning("short_term_context failed: %s", e)
            result["short_term_context"] = {
                "st_score": 50,
                "phase_label": "Transition",
                "phase_desc": "Data loading...",
                "upside_pct": 10,
                "downside_pct": 15,
                "upside_target": None,
                "downside_target": None,
                "tactical_signal": "NEUTRAL",
                "tactical_color": "blue",
                "days_since_bottom": 0,
            }
        _set_cached_response("analyzer", result)
        return api_response(result)
    except Exception as e:
        logger.exception("Analyzer endpoint failed")
        return api_response({"error": str(e), "alpha_cycle_position": 50.0})


def _phase_label(arc: float) -> str:
    if arc < 30: return "Deep Value"
    if arc < 40: return "Accumulation"
    if arc < 60: return "Expansion"
    if arc < 70: return "Risk Rising"
    return "Euphoria"


@app.get("/api/snapshot")
@limiter.limit("30/minute")
async def get_snapshot(request: Request):
    """
    Aggregates all relevant data and returns ready-to-use post templates.
    """
    try:
        c = _require_cache()
        raw = c["raw"]
        btc_prices = raw.get("btc_prices", [])
        btc_price = float(btc_prices[-1]) if btc_prices else 0.0
        ath_price = max(btc_prices) if btc_prices else btc_price
        btc_drawdown = ((btc_price - ath_price) / ath_price * 100) if ath_price > 0 else -30.0
        score_history = c.get("score_history", {}).get("combined", [])
        walcl = [x["v"] for x in raw.get("walcl_series", [])]
        liquidity_trend = c["macro_scores"].get("walcl_trend", 50.0)
        ma_200w = safe_float(c["btc_scores"].get("ma_200w_raw", 0.0))

        result = _analyzer.analyze(
            combined_score=c["combined"].get("combined_score", 50.0),
            btc_score=c["btc_scores"].get("btc_score", 50.0),
            eth_score=c["eth_scores"].get("eth_score", 50.0),
            macro_score=c["macro_scores"].get("macro_score", 50.0),
            fear_greed=raw["fear_greed"]["current"],
            btc_price=btc_price,
            btc_drawdown_pct=btc_drawdown,
            liquidity_trend=liquidity_trend,
            score_history=score_history,
            btc_price_history=btc_prices,
            ma_200w=ma_200w,
            ath_price=safe_float(raw.get("btc_market", {}).get("ath", ath_price)),
        )
        try:
            anchor_data = compute_cycle_anchor()
            days_since = anchor_data.get("days_since_cycle_bottom", 0)
            st = c["btc_scores"].get("short_term", {})
            st_ctx = get_short_term_context(
                arc_score=result.get("alpha_cycle_position", 50.0),
                days_since_bottom=days_since or 0,
                rsi_score=st.get("rsi", 50.0),
                funding_score=st.get("funding", 50.0),
                power_law_score=st.get("power_law", 50.0),
                mvrv_score=st.get("mvrv", 50.0),
                btc_price=btc_price,
                ath_price=ath_price,
                ma_200w=ma_200w,
            )
            result["short_term_context"] = st_ctx
            result["days_since_top"] = st_ctx.get("days_since_top")
            result["cycle_top_date"] = st_ctx.get("cycle_top_date", TENTATIVE_CYCLE_TOP.isoformat())
            result["cycle_top_confirmed"] = False
        except Exception as e:
            logger.warning("short_term_context failed: %s", e)
            st_ctx = {
                "st_score": 50,
                "phase_label": "Transition",
                "upside_pct": 10,
                "downside_pct": 15,
            }

        from datetime import datetime as _dt
        analysis = cycle_analyzer.analyze(
            combined_score=c["combined"].get("combined_score", 50.0),
            btc_score=c["btc_scores"].get("btc_score", 50.0),
            eth_score=c["eth_scores"].get("eth_score", 50.0),
            macro_score=c["macro_scores"].get("macro_score", 50.0),
            fear_greed=raw.get("fear_greed", {}).get("current", 50.0),
            btc_price=btc_price,
            btc_drawdown_pct=btc_drawdown,
            liquidity_trend=c["macro_scores"].get("walcl_trend", 50.0),
            score_history=score_history,
            btc_price_history=raw.get("btc_prices", []),
            ma_200w=ma_200w,
            ath_price=safe_float(raw.get("btc_market", {}).get("ath", 0.0)),
            now=_dt.utcnow(),
        )
        dec = decision_engine.decide(
            phase=analysis.get("phase", "Accumulation"),
            cycle_position=analysis.get("alpha_cycle_position", analysis.get("cycle_position_percent", 50.0)),
            combined_score=c["combined"].get("combined_score", 50.0),
            btc_score=c["btc_scores"].get("btc_score", 50.0),
            eth_score=c["eth_scores"].get("eth_score", 50.0),
            macro_score=c["macro_scores"].get("macro_score", 50.0),
            seasonality_score=analysis.get("seasonality_score", 50.0),
            seasonality_bias=analysis.get("seasonality_bias", "NEUTRAL"),
            bottom_probability=analysis.get("bottom_probability", 50.0),
            top_probability=analysis.get("top_probability", 10.0),
            confidence=analysis.get("confidence", 50.0),
            years_since_halving=analysis.get("seasonality_detail", {}).get("years_since_halving", 1.0),
            btc_price=btc_price,
            eth_price=safe_float(raw.get("eth_market", {}).get("price", 0)),
            btc_drawdown_pct=btc_drawdown,
            fear_greed=raw.get("fear_greed", {}).get("current", 50.0),
            walcl_series=raw.get("walcl_series", []),
            stable_series=raw.get("stable_series", []),
            score_history=score_history,
        )
        position = result.get("position") or dec.get("position", "HOLD")
        override = result.get("decision_override")
        if override:
            position = override
        spot = dec.get("spot_allocation", {})
        allocation = "BTC %s%% / ETH %s%% / Cash %s%%" % (
            spot.get("btc", 40), spot.get("eth", 20), spot.get("cash", 40),
        )

        analysis = {
            "arc_summary": c.get("arc_summary") or {},
            "combined": c.get("combined", {}).get("combined_score"),
            "alpha_cycle_position": result.get("alpha_cycle_position"),
            "arc_score": result.get("arc_score"),
        }
        arc_score = (
            analysis.get("arc_summary", {}).get("arc_score")
            or analysis.get("arc_score")
            or 50
        )
        arc_score = float(arc_score) if arc_score is not None else 50.0
        arc_display_val = arc_display_score(arc_score)
        st_ctx = result.get("short_term_context") or st_ctx
        cy_sig = result.get("cycle_signal") or {}
        eth_price = safe_float(raw.get("eth_market", {}).get("price", 0))

        expected_range_label = "N/A"
        try:
            bt_results = CACHE.get("backtest_results")
            fwd = CACHE.get("fwd_returns")
            dd_data = CACHE.get("high_risk_drawdown")
            if not bt_results:
                bt = await run_daily_backtest_full()
                bt_results = bt.get("results", []) if isinstance(bt, dict) else []
            if fwd is None and bt_results:
                from historical_returns import compute_arc_forward_returns
                fwd = compute_arc_forward_returns(bt_results)
            if dd_data is None and bt_results:
                from historical_returns import compute_high_risk_drawdown
                dd_data = compute_high_risk_drawdown(bt_results)
            if fwd is None:
                fwd = []
            if dd_data is None:
                dd_data = {}
            hist_returns = CACHE.get("hist_returns")
            if hist_returns is None and bt_results:
                from historical_returns import compute_historical_returns
                arc_history = []
                for _r in bt_results:
                    d = _r.get("date")
                    arc_val = _r.get("arc_score", _r.get("score"))
                    price = _r.get("btc_price", _r.get("price"))
                    if d and arc_val is not None and price is not None:
                        arc_history.append(
                            {
                                "date": d,
                                "arc_score": float(arc_val),
                                "btc_price": float(price),
                            }
                        )
                zone_periods_for_expected = compute_zone_history(arc_history) if arc_history else []
                hist_returns = compute_historical_returns(
                    bt_results, zone_periods=zone_periods_for_expected or None
                )
            expected = _get_expected_range(arc_display_val, hist_returns=hist_returns or {}, high_risk_drawdown=dd_data)
            expected_range_label = expected.get("label", "N/A")
        except Exception:
            pass

        snapshot = build_snapshot(
            arc_score=arc_display_val,
            btc_price=btc_price,
            eth_price=eth_price,
            fear_greed=raw["fear_greed"]["current"],
            phase_label=_phase_label(arc_display_val),
            position=position,
            allocation=allocation,
            upside_pct=st_ctx.get("upside_pct", 0),
            downside_pct=st_ctx.get("downside_pct", 0),
            st_score=st_ctx.get("st_score", 50),
            cycle_phase_label=st_ctx.get("phase_label", "Transition"),
            signal_type=cy_sig.get("signal_type", "NONE"),
            days_since_bottom=compute_days_since_bottom(),
            days_since_top=st_ctx.get("days_since_top") if st_ctx else compute_days_since_top(),
            btc_score=c["btc_scores"].get("btc_score", 50.0),
            eth_score=c["eth_scores"].get("eth_score", 50.0),
            mac_score=c["macro_scores"].get("macro_score", 50.0),
            ma_200w_dev=c["btc_scores"].get("ma_200w_dev_pct"),
            drawdown_pct=abs(btc_drawdown) / 100.0 if btc_drawdown else None,
            expected_range=expected_range_label,
            confidence=dec.get("confidence"),
            arc_momentum_30d=result.get("arc_momentum_30d"),
            arc_momentum_label=result.get("arc_momentum_label"),
            arc_percentile=result.get("arc_percentile"),
            arc_percentile_label=result.get("arc_percentile_label"),
        )
        _set_cached_response("snapshot", snapshot)
        return api_response(snapshot)
    except Exception as e:
        logger.error("snapshot error: %s", e)
        return api_response({
            "error": str(e),
            "post_templates": {
                "daily_update": "Data loading...",
                "compact": "Data loading...",
            },
        })


@app.get("/api/decision")
@limiter.limit("30/minute")
async def get_decision(request: Request):
    from datetime import datetime
    cached = _get_cached_response("decision")
    if cached is not None:
        return api_response(cached)
    c   = _require_cache()
    raw = c["raw"]

    bm           = raw.get("btc_market", {})
    em           = raw.get("eth_market", {})
    btc_price    = safe_float(bm.get("price", 0))
    eth_price    = safe_float(em.get("price", 0))
    btc_drawdown = safe_float(bm.get("ath_change_pct", -30.0))
    if btc_drawdown == 0.0 and raw.get("btc_prices"):
        prices       = raw["btc_prices"]
        peak         = max(prices) if prices else btc_price
        btc_drawdown = ((btc_price - peak) / peak * 100) if peak > 0 else -30.0

    score_history = c.get("score_history", {}).get("combined", [])

    # Run analyzer for cycle intelligence inputs
    analysis = cycle_analyzer.analyze(
        combined_score    = c["combined"].get("combined_score",       50.0),
        btc_score         = c["btc_scores"].get("btc_score",          50.0),
        eth_score         = c["eth_scores"].get("eth_score",          50.0),
        macro_score       = c["macro_scores"].get("macro_score",      50.0),
        fear_greed        = raw.get("fear_greed", {}).get("current",  50.0),
        btc_price         = btc_price,
        btc_drawdown_pct  = btc_drawdown,
        liquidity_trend   = c["macro_scores"].get("walcl_trend",      50.0),
        score_history     = score_history,
        btc_price_history = raw.get("btc_prices", []),
        ma_200w           = safe_float(c["btc_scores"].get("ma_200w_raw", 0.0)),
        ath_price         = safe_float(raw.get("btc_market", {}).get("ath", 0.0)),
        now               = datetime.utcnow(),
    )

    result = decision_engine.decide(
        phase               = analysis.get("phase",                 "Accumulation"),
        cycle_position      = analysis.get("alpha_cycle_position",
                              analysis.get("cycle_position_percent", 50.0)),
        combined_score      = c["combined"].get("combined_score",    50.0),
        btc_score           = c["btc_scores"].get("btc_score",       50.0),
        eth_score           = c["eth_scores"].get("eth_score",       50.0),
        macro_score         = c["macro_scores"].get("macro_score",   50.0),
        seasonality_score   = analysis.get("seasonality_score",      50.0),
        seasonality_bias    = analysis.get("seasonality_bias",       "NEUTRAL"),
        bottom_probability  = analysis.get("bottom_probability",     50.0),
        top_probability     = analysis.get("top_probability",        10.0),
        confidence          = analysis.get("confidence",             50.0),
        years_since_halving = analysis.get("seasonality_detail", {}).get("years_since_halving", 1.0),
        btc_price           = btc_price,
        eth_price           = eth_price,
        btc_drawdown_pct    = btc_drawdown,
        fear_greed          = raw.get("fear_greed", {}).get("current", 50.0),
        walcl_series        = raw.get("walcl_series", []),
        stable_series       = raw.get("stable_series", []),
        score_history       = score_history,
    )
    decision_override = analysis.get("decision_override")
    if decision_override:
        result["position"] = decision_override
        if "suggested_position" in result:
            result["suggested_position"] = decision_override
    _set_cached_response("decision", result)
    return api_response(result)
