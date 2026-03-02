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
  GET /api/cycle-anchor
"""
import os, time, math, logging, asyncio
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
    from analyzer import analyzer as cycle_analyzer
except ImportError:
    from backend.analyzer import analyzer as cycle_analyzer

try:
    from decision_engine import decision_engine
except ImportError:
    from backend.decision_engine import decision_engine

try:
    from cycle_anchor import compute_cycle_anchor
except ImportError:
    from backend.cycle_anchor import compute_cycle_anchor

# ── LOGGING ──────────────────────────────────────────────────────────────────
logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger(__name__)

# ── CACHE ────────────────────────────────────────────────────────────────────
CACHE: dict = {}
CACHE_TTL   = int(os.getenv("CACHE_TTL_SECONDS", "60"))
_cache_lock = asyncio.Lock()
_last_refresh = 0.0


async def refresh_cache(force: bool = False):
    global _last_refresh
    async with _cache_lock:
        now = time.time()
        if not force and (now - _last_refresh) < CACHE_TTL:
            return

        logger.info("Alpha Cycle — refreshing data cache…")
        try:
            raw = await fetch_all()

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

            btc_scores = compute_btc_score(
                btc_p, fg, walcl, stable,
                indicators=indicators,
                funding_data=funding_data,
                btc_dominance=btc_dom,
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
                "eth_scores":   eth_scores,
                "macro_scores": macro_scores,
                "combined":     combined,
                "score_history":hist,
                "refreshed_at": ts,
            })
            _last_refresh = now
            logger.info(
                f"Cache OK — BTC:{btc_scores['btc_score']:.1f} "
                f"ETH:{eth_scores['eth_score']:.1f} "
                f"MACRO:{macro_scores['macro_score']:.1f}"
            )
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

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["GET"],
    allow_headers=["*"],
)


# ── HELPERS ──────────────────────────────────────────────────────────────────

def _require_cache():
    if not CACHE:
        raise HTTPException(503, "Data not yet available. Retry in 10s.")
    return CACHE

def _clean(obj):
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

def _build_ratio_series(btc_prices, eth_prices, days) -> list:
    btc = btc_prices[-days:] if btc_prices else []
    eth = eth_prices[-days:] if eth_prices else []
    n   = min(len(btc), len(eth))
    if not n: return []
    now_ms = int(time.time() * 1000)
    return [{"t": now_ms-(n-1-i)*86_400_000,
             "v": safe_float(eth[-(n-i)]) / safe_float(btc[-(n-i)], 1.0)}
            for i in range(n)]


# ── ENDPOINTS ────────────────────────────────────────────────────────────────

@app.get("/health")
async def health():
    return {
        "status":    "ok",
        "service":   "Alpha Cycle Intelligence API",
        "cache_age": max(0, int(time.time() - _last_refresh)),
        "has_data":  bool(CACHE),
        "version":   "3.0.0",
    }


@app.get("/api/prices")
async def get_prices():
    c  = _require_cache()
    bm = c["raw"]["btc_market"]
    em = c["raw"]["eth_market"]
    fg = c["raw"]["fear_greed"]
    gd = c["raw"].get("global_data", {})
    fd = c["raw"].get("funding_data", {})

    # Stablecoin current
    stable_series = c["raw"].get("stable_series", [])
    stable_b = safe_float(stable_series[-1]["v"]) / 1e9 if stable_series else 0.0

    return api_response({
        "btc": {
            "price":          safe_float(bm.get("price", 0)),
            "change_24h":     safe_float(bm.get("change_24h", 0)),
            "market_cap":     safe_float(bm.get("market_cap", 0)),
            "volume_24h":     safe_float(bm.get("volume", 0)),
            "ath":            safe_float(bm.get("ath", 0)),
            "ath_change_pct": safe_float(bm.get("ath_change_pct", 0)),
            "history":        _prices_to_series(c["raw"]["btc_prices"], 90),
        },
        "eth": {
            "price":          safe_float(em.get("price", 0)),
            "change_24h":     safe_float(em.get("change_24h", 0)),
            "market_cap":     safe_float(em.get("market_cap", 0)),
            "volume_24h":     safe_float(em.get("volume", 0)),
            "ath":            safe_float(em.get("ath", 0)),
            "ath_change_pct": safe_float(em.get("ath_change_pct", 0)),
            "history":        _prices_to_series(c["raw"]["eth_prices"], 90),
        },
        "eth_btc_ratio": _build_ratio_series(
            c["raw"]["btc_prices"], c["raw"]["eth_prices"], 90),
        "fear_greed":    fg,
        "global": {
            "btc_dominance":    safe_float(gd.get("btc_dominance", 50)),
            "total_market_cap": safe_float(gd.get("total_market_cap", 0)),
        },
        "funding": {
            "btc_funding_rate": safe_float(fd.get("btc_funding_rate", 0)),
            "eth_funding_rate": safe_float(fd.get("eth_funding_rate", 0)),
        },
        "stablecoin_cap_B": stable_b,
    })


@app.get("/api/cycle/btc")
async def get_btc_cycle():
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
        "weights": {
            "ma_200w": 0.18, "mvrv": 0.15, "fear_greed": 0.12,
            "drawdown": 0.10, "rsi": 0.10, "puell": 0.10,
            "pi_cycle": 0.08, "macro_liq": 0.08, "stable_supply": 0.05,
            "funding": 0.02, "power_law": 0.02,
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
async def get_macro_cycle():
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
async def get_combined():
    c = _require_cache()
    return api_response({
        **c["combined"],
        "scores": {
            "btc":   c["btc_scores"].get("btc_score",   50.0),
            "eth":   c["eth_scores"].get("eth_score",   50.0),
            "macro": c["macro_scores"].get("macro_score", 50.0),
        },
        "refreshed_at": c.get("refreshed_at", 0),
    })


@app.get("/api/history")
async def get_history():
    c       = _require_cache()
    hist    = c.get("score_history", {"btc": [], "eth": [], "macro": [], "combined": []})
    tvl_raw = c["raw"].get("tvl_series", [])
    fg_hist = c["raw"]["fear_greed"]["history"][-90:]
    stable_raw = c["raw"].get("stable_series", [])

    tvl_hist = [{"t": i["t"], "v": safe_float(i["v"]) / 1e9} for i in tvl_raw[-365:]]
    stable_hist = [{"t": i["t"], "v": safe_float(i["v"])} for i in stable_raw[-365:]]

    return api_response({
        "scores":   hist,
        "tvl":      tvl_hist,
        "fg":       fg_hist,
        "btc_full": _prices_to_series(c["raw"]["btc_prices"], 730),
        "eth_full": _prices_to_series(c["raw"]["eth_prices"], 730),
        "walcl":    [{"t": i["t"], "v": safe_float(i["v"]) / 1e6}
                     for i in c["raw"].get("walcl_series", [])[-260:]],
        "stable":   stable_hist,
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


@app.get("/api/analyzer")
async def get_analyzer():
    from datetime import datetime
    c   = _require_cache()
    raw = c["raw"]

    bm           = raw.get("btc_market", {})
    btc_price    = safe_float(bm.get("price", 0))
    btc_drawdown = safe_float(bm.get("ath_change_pct", -30.0))
    if btc_drawdown == 0.0 and raw.get("btc_prices"):
        prices       = raw["btc_prices"]
        peak         = max(prices) if prices else btc_price
        btc_drawdown = ((btc_price - peak) / peak * 100) if peak > 0 else -30.0

    score_history = c.get("score_history", {}).get("combined", [])

    result = cycle_analyzer.analyze(
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
        now               = datetime.utcnow(),
    )
    return api_response(result)


@app.get("/api/decision")
async def get_decision():
    from datetime import datetime
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
        now               = datetime.utcnow(),
    )

    result = decision_engine.decide(
        phase               = analysis.get("phase",                 "Accumulation"),
        cycle_position      = analysis.get("cycle_position_percent", 50.0),
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
    return api_response(result)
