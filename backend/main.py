"""
main.py — Alpha Cycle Intelligence — FastAPI Backend
Production-grade. Zero NaN. Auto-refresh every 60s.

Endpoints:
  GET /health
  GET /api/prices
  GET /api/cycle/btc
  GET /api/cycle/eth
  GET /api/cycle/macro
  GET /api/cycle/combined
  GET /api/history
  GET /api/fear-greed
  GET /api/cycle-anchor
"""
import os
import time
import math
import logging
import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

try:
    from fetcher import fetch_all, _synthetic_walcl
except ImportError:
    from backend.fetcher import fetch_all, _synthetic_walcl
try:
    from scoring import (
        compute_btc_score, compute_eth_score,
        compute_macro_score, compute_combined,
        clamp, safe_float,
    )
except ImportError:
    from backend.scoring import (
        compute_btc_score, compute_eth_score,
        compute_macro_score, compute_combined,
        clamp, safe_float,
    )
try:
    from cycle_anchor import compute_cycle_anchor
except ImportError:
    from backend.cycle_anchor import compute_cycle_anchor

# -----------------------------------------------------------------------------
# LOGGING
# -----------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

# -----------------------------------------------------------------------------
# CACHE - in-memory, refreshed every 60 seconds
# -----------------------------------------------------------------------------
CACHE: dict = {}
CACHE_TTL = int(os.getenv("CACHE_TTL_SECONDS", "60"))
_cache_lock = asyncio.Lock()
_last_refresh = 0.0


async def refresh_cache(force: bool = False):
    global _last_refresh
    async with _cache_lock:
        now = time.time()
        if not force and (now - _last_refresh) < CACHE_TTL:
            return  # still fresh

        logger.info("Alpha Cycle — refreshing data cache…")
        try:
            raw = await fetch_all()

            btc_p  = raw["btc_prices"]
            eth_p  = raw["eth_prices"]
            walcl  = [item["v"] for item in raw["walcl_series"]]
            stable = [item["v"] for item in raw["stable_series"]]
            tvl    = [item["v"] for item in raw["tvl_series"]]
            us10y  = [item["v"] for item in raw.get("us10y_series", [])]
            fg     = raw["fear_greed"]["current"]

            btc_scores   = compute_btc_score(btc_p, fg, walcl, stable)
            eth_scores   = compute_eth_score(eth_p, btc_p, tvl, stable, fg)
            macro_scores = compute_macro_score(walcl, stable, btc_p,
                                               us10y_series=us10y)
            combined     = compute_combined(
                btc_scores["btc_score"],
                eth_scores["eth_score"],
                macro_scores["macro_score"],
            )

            hist = CACHE.get("score_history", {"btc": [], "eth": [], "macro": [], "combined": []})
            ts = int(time.time() * 1000)
            for key, val in [
                ("btc",      btc_scores["btc_score"]),
                ("eth",      eth_scores["eth_score"]),
                ("macro",    macro_scores["macro_score"]),
                ("combined", combined["combined_score"]),
            ]:
                hist[key].append({"t": ts, "v": val})
                hist[key] = hist[key][-2880:]  # keep 48h at 60s intervals

            CACHE.update({
                "raw":           raw,
                "btc_scores":    btc_scores,
                "eth_scores":    eth_scores,
                "macro_scores":  macro_scores,
                "combined":      combined,
                "score_history": hist,
                "refreshed_at":  ts,
            })
            _last_refresh = now
            logger.info(
                f"Cache OK — BTC:{btc_scores['btc_score']:.1f} "
                f"ETH:{eth_scores['eth_score']:.1f} "
                f"MACRO:{macro_scores['macro_score']:.1f}"
            )
        except Exception as e:
            logger.error(f"Cache refresh failed: {e}", exc_info=True)


# -----------------------------------------------------------------------------
# BACKGROUND REFRESH LOOP
# -----------------------------------------------------------------------------

async def _refresh_loop():
    while True:
        try:
            await refresh_cache()
        except Exception as e:
            logger.error(f"Refresh loop error: {e}")
        await asyncio.sleep(CACHE_TTL)


# -----------------------------------------------------------------------------
# APP LIFECYCLE
# -----------------------------------------------------------------------------

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Alpha Cycle Intelligence API starting…")
    await refresh_cache(force=True)
    task = asyncio.create_task(_refresh_loop())
    yield
    task.cancel()
    logger.info("Alpha Cycle API shut down.")


app = FastAPI(
    title="Alpha Cycle Intelligence API",
    version="2.0.0",
    description="Proprietary crypto market cycle scoring. Zero NaN.",
    lifespan=lifespan,
)

# -----------------------------------------------------------------------------
# CORS - allow all origins (public read-only API)
# -----------------------------------------------------------------------------

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["GET"],
    allow_headers=["*"],
)


# -----------------------------------------------------------------------------
# HELPERS
# -----------------------------------------------------------------------------

def _require_cache():
    if not CACHE:
        raise HTTPException(503, "Data not yet available. Retry in 10s.")
    return CACHE


def _clean(obj):
    """Recursively replace NaN/Inf with 0.0 for JSON safety."""
    if isinstance(obj, dict):
        return {k: _clean(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_clean(v) for v in obj]
    if isinstance(obj, float):
        if math.isnan(obj) or math.isinf(obj):
            return 0.0
        return round(obj, 6)
    return obj


def api_response(data: dict) -> JSONResponse:
    cleaned = _clean(data)
    cleaned["_ts"] = int(time.time() * 1000)
    return JSONResponse(content=cleaned)


# -----------------------------------------------------------------------------
# ENDPOINTS
# -----------------------------------------------------------------------------

@app.get("/health")
async def health():
    cache_age = max(0, int(time.time() - _last_refresh))
    return {
        "status":    "ok",
        "service":   "Alpha Cycle Intelligence API",
        "cache_age": cache_age,
        "has_data":  bool(CACHE),
        "version":   "2.0.0",
    }


@app.get("/api/prices")
async def get_prices():
    c = _require_cache()
    bm = c["raw"]["btc_market"]
    em = c["raw"]["eth_market"]
    fg = c["raw"]["fear_greed"]

    btc_hist   = _prices_to_series(c["raw"]["btc_prices"], 90)
    eth_hist   = _prices_to_series(c["raw"]["eth_prices"], 90)
    ratio_hist = _build_ratio_series(c["raw"]["btc_prices"], c["raw"]["eth_prices"], 90)

    return api_response({
        "btc": {
            "price":         safe_float(bm.get("price", 0)),
            "change_24h":    safe_float(bm.get("change_24h", 0)),
            "market_cap":    safe_float(bm.get("market_cap", 0)),
            "volume_24h":    safe_float(bm.get("volume", 0)),
            "ath":           safe_float(bm.get("ath", 0)),
            "ath_change_pct":safe_float(bm.get("ath_change_pct", 0)),
            "history":       btc_hist,
        },
        "eth": {
            "price":         safe_float(em.get("price", 0)),
            "change_24h":    safe_float(em.get("change_24h", 0)),
            "market_cap":    safe_float(em.get("market_cap", 0)),
            "volume_24h":    safe_float(em.get("volume", 0)),
            "ath":           safe_float(em.get("ath", 0)),
            "ath_change_pct":safe_float(em.get("ath_change_pct", 0)),
            "history":       eth_hist,
        },
        "eth_btc_ratio": ratio_hist,
        "fear_greed":    fg,
    })


@app.get("/api/cycle/btc")
async def get_btc_cycle():
    c = _require_cache()
    s = c["btc_scores"]
    return api_response({
        "score":         s.get("btc_score", 50.0),
        "current_price": s.get("current_price", 0.0),
        "components": {
            "rsi":           {"score": s.get("rsi", 50.0),       "raw": s.get("rsi_raw", 50.0)},
            "ma_200w":       {"score": s.get("ma_200w", 50.0),   "deviation_pct": s.get("ma_200w_dev_pct", 0.0), "value": s.get("ma_200w_raw", 0.0)},
            "drawdown":      {"score": s.get("drawdown", 50.0)},
            "fear_greed":    {"score": s.get("fear_greed", 50.0),"raw": c["raw"]["fear_greed"]["current"]},
            "macro_liq":     {"score": s.get("macro_liq", 50.0)},
            "stable_supply": {"score": s.get("stable_supply", 50.0)},
            "power_law":     {"score": s.get("power_law", 50.0)},
        },
        "weights": {
            "rsi": 0.18, "ma_200w": 0.22, "drawdown": 0.15,
            "fear_greed": 0.20, "macro_liq": 0.12,
            "stable_supply": 0.08, "power_law": 0.05,
        },
    })


@app.get("/api/cycle/eth")
async def get_eth_cycle():
    c = _require_cache()
    s = c["eth_scores"]
    return api_response({
        "score":         s.get("eth_score", 50.0),
        "current_price": s.get("current_price", 0.0),
        "components": {
            "eth_btc_ratio":  {"score": s.get("eth_btc_ratio", 50.0),    "raw": s.get("eth_btc_ratio_raw", 0.05)},
            "price_trend_30d":{"score": s.get("price_trend_30d", 50.0)},
            "price_trend_90d":{"score": s.get("price_trend_90d", 50.0)},
            "tvl_trend":      {"score": s.get("tvl_trend", 50.0)},
            "stable_growth":  {"score": s.get("stable_growth", 50.0)},
            "rsi":            {"score": s.get("rsi", 50.0)},
            "ma_200w":        {"score": s.get("ma_200w", 50.0)},
            "drawdown":       {"score": s.get("drawdown", 50.0)},
            "fear_greed":     {"score": s.get("fear_greed", 50.0)},
        },
        "weights": {
            "eth_btc_ratio": 0.22, "price_trend_30d": 0.12,
            "price_trend_90d": 0.10, "tvl_trend": 0.18,
            "stable_growth": 0.08, "rsi": 0.12,
            "ma_200w": 0.10, "drawdown": 0.05, "fear_greed": 0.03,
        },
    })


@app.get("/api/cycle/macro")
async def get_macro_cycle():
    c = _require_cache()
    s = c["macro_scores"]
    walcl_hist  = [{"t": item["t"], "v": safe_float(item["v"])}
                   for item in c["raw"]["walcl_series"][-180:]]
    stable_hist = [{"t": item["t"], "v": safe_float(item["v"]) / 1e9}
                   for item in c["raw"]["stable_series"][-180:]]
    return api_response({
        "score": s.get("macro_score", 50.0),
        "components": {
            "walcl_trend":  {"score": s.get("walcl_trend", 50.0)},
            "stable_trend": {"score": s.get("stable_trend", 50.0)},
            "btc_risk_on":  {"score": s.get("btc_risk_on", 50.0)},
            "dxy_trend":    {"score": s.get("dxy_trend", 50.0)},
            "yield_trend":  {"score": s.get("yield_trend", 50.0)},
        },
        "data": {
            "walcl_current_T":  s.get("walcl_current", 8.0),
            "walcl_yoy_pct":    s.get("walcl_yoy_pct", 0.0),
            "stable_current_B": s.get("stable_current_B", 150.0),
        },
        "history":  {"walcl": walcl_hist, "stable": stable_hist},
        "weights": {
            "walcl_trend": 0.35, "stable_trend": 0.25,
            "btc_risk_on": 0.20, "dxy_trend": 0.10, "yield_trend": 0.10,
        },
    })


@app.get("/api/arc-summary")
async def get_arc_summary():
    """ARC Index summary — single endpoint for dashboard."""
    c = _require_cache()
    raw = c["raw"]
    btc = compute_btc_score(
        raw["btc_prices"], raw["fear_greed"]["current"],
        [x["v"] for x in raw.get("walcl_series", [])],
        [x["v"] for x in raw.get("stable_series", [])],
        indicators=raw.get("indicators"),
        funding_data=raw.get("funding_data"),
        btc_dominance=raw.get("global_data", {}).get("btc_dominance", 50.0),
    )
    eth = compute_eth_score(
        raw["eth_prices"], raw["btc_prices"],
        [x["v"] for x in raw.get("tvl_series", [])],
        [x["v"] for x in raw.get("stable_series", [])],
        raw["fear_greed"]["current"],
        funding_data=raw.get("funding_data"),
    )
    arc = btc["btc_score"]
    fg  = raw["fear_greed"]["current"]

    if arc < 30:
        regime = "Low Risk"
        decision = "Accumulate"
        confidence = "High"
    elif arc < 61:
        regime = "Moderate Risk"
        decision = "Hold"
        confidence = "Moderate"
    elif arc < 81:
        regime = "Elevated Risk"
        decision = "Reduce"
        confidence = "Low-Moderate"
    else:
        regime = "Extreme Risk"
        decision = "Defensive"
        confidence = "Low"

    return api_response({
        "arc_index":     round(arc, 1),
        "regime":        regime,
        "decision":      decision,
        "confidence":    confidence,
        "btc_score":     round(arc, 1),
        "eth_score":     round(eth["eth_score"], 1),
        "fear_greed":    fg,
        "liquidity":     round(btc.get("liquidity", 50.0), 1),
        "components": {
            "ma_200w":    round(btc.get("ma_200w", 50.0), 1),
            "drawdown":   round(btc.get("drawdown", 50.0), 1),
            "fear_greed": round(btc.get("fear_greed", 50.0), 1),
            "liquidity":  round(btc.get("liquidity", 50.0), 1),
        },
        "short_term":    btc.get("short_term", {}),
        "cycle_anchor":  compute_cycle_anchor(),
        "_ts":           c.get("refreshed_at", 0),
    })


@app.get("/api/cycle/combined")
async def get_combined():
    c = _require_cache()
    return api_response({
        **c["combined"],
        "scores": {
            "btc":   c["btc_scores"].get("btc_score", 50.0),
            "eth":   c["eth_scores"].get("eth_score", 50.0),
            "macro": c["macro_scores"].get("macro_score", 50.0),
        },
        "refreshed_at": c.get("refreshed_at", 0),
    })


@app.get("/api/history")
async def get_history():
    c = _require_cache()
    hist     = c.get("score_history", {"btc": [], "eth": [], "macro": [], "combined": []})
    tvl_hist = [{"t": item["t"], "v": safe_float(item["v"]) / 1e9}
                for item in c["raw"]["tvl_series"][-365:]]
    fg_hist  = c["raw"]["fear_greed"]["history"][-90:]

    return api_response({
        "scores":   hist,
        "tvl":      tvl_hist,
        "fg":       fg_hist,
        "btc_full": _prices_to_series(c["raw"]["btc_prices"], 730),
        "eth_full": _prices_to_series(c["raw"]["eth_prices"], 730),
        "walcl":    [{"t": item["t"], "v": safe_float(item["v"]) / 1e6}
                     for item in c["raw"]["walcl_series"][-260:]],
    })


@app.get("/api/fear-greed")
async def get_fear_greed():
    c = _require_cache()
    return api_response(c["raw"]["fear_greed"])


@app.get("/api/cycle-anchor")
async def get_cycle_anchor():
    """Cycle Anchor Engine: objective cycle timing from historical Bitcoin structure."""
    data = compute_cycle_anchor()
    return api_response(data)


# -----------------------------------------------------------------------------
# INTERNAL HELPERS
# -----------------------------------------------------------------------------

def _prices_to_series(prices: list, days: int) -> list:
    if not prices:
        return []
    subset = prices[-days:]
    now_ms = int(time.time() * 1000)
    return [
        {"t": now_ms - (len(subset) - 1 - i) * 86_400_000, "v": safe_float(p)}
        for i, p in enumerate(subset)
    ]


def _build_ratio_series(btc_prices: list, eth_prices: list, days: int) -> list:
    btc = btc_prices[-days:] if btc_prices else []
    eth = eth_prices[-days:] if eth_prices else []
    n   = min(len(btc), len(eth))
    if not n:
        return []
    now_ms = int(time.time() * 1000)
    result = []
    for i in range(n):
        b = safe_float(btc[-(n - i)], 1.0)
        e = safe_float(eth[-(n - i)], 0.0)
        result.append({"t": now_ms - (n - 1 - i) * 86_400_000, "v": e / b if b > 0 else 0.0})
    return result
