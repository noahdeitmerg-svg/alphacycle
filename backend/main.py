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


_DAILY_TG_STATE = {"sent_date": None}


async def _compose_daily_telegram() -> str:
    """Build the daily summary text from the live endpoints. English, concise."""
    import httpx
    base = "https://alphacycle-production.up.railway.app"
    arc = {}
    lad = {}
    async with httpx.AsyncClient(timeout=25) as c:
        try:
            arc = (await c.get(base + "/api/arc-summary")).json()
        except Exception as e:
            logger.warning("daily tg arc fetch: %s", e)
        try:
            lad = (await c.get(base + "/api/ladder")).json()
        except Exception as e:
            logger.warning("daily tg ladder fetch: %s", e)
    score = arc.get("arc_score")
    score_txt = f"{float(score):.0f}" if score is not None else "?"
    zone = lad.get("zone") or arc.get("zone") or "-"
    price = arc.get("btc_price")
    price_txt = f"${float(price):,.0f}" if price else "-"
    mom = arc.get("arc_momentum_30d")
    mom_txt = (f"{mom:+.1f}" if isinstance(mom, (int, float)) else "-")
    invested = lad.get("invested_pct")
    nxt = (lad.get("next_step") or {}).get("text") or ""
    from datetime import date as _date
    msg = (
        f"\U0001F4C5 AlphaCycle Daily - {_date.today().isoformat()}\n\n"
        f"ARC Index: {score_txt} - {zone}\n"
        f"BTC: {price_txt}\n"
        f"30d momentum: {mom_txt}\n\n"
        f"Adaptive ladder: {invested}% invested\n"
        f"Next move: {nxt}\n\n"
        f"- alphacycle.app/app"
    )
    return msg


async def _send_daily_telegram():
    try:
        from alerts import send_telegram
        text = await _compose_daily_telegram()
        return await asyncio.to_thread(send_telegram, text)
    except Exception as e:
        logger.warning("send daily telegram failed: %s", e)
        return False


async def _daily_telegram_loop():
    """Fire one Telegram summary per day around 12:00 Europe/Berlin (DST-safe)."""
    from datetime import datetime, timedelta
    while True:
        try:
            try:
                from zoneinfo import ZoneInfo
                now = datetime.now(ZoneInfo("Europe/Berlin"))
            except Exception:
                now = datetime.utcnow() + timedelta(hours=2)
            today = now.date().isoformat()
            if now.hour == 12 and _DAILY_TG_STATE["sent_date"] != today:
                ok = await _send_daily_telegram()
                _DAILY_TG_STATE["sent_date"] = today
                logger.info("daily telegram fired for %s (ok=%s)", today, ok)
        except Exception as e:
            logger.warning("daily telegram loop error: %s", e)
        await asyncio.sleep(55)


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
    daily_tg_task = asyncio.create_task(_daily_telegram_loop())
    yield
    task.cancel()
    daily_tg_task.cancel()
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
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- lightweight funnel analytics (GET-based so it works under any CORS) ---
import json as _ajson, os as _aos
_METRICS_FILE = "/tmp/ac_metrics.json"
_METRICS = {}
try:
    if _aos.path.exists(_METRICS_FILE):
        _METRICS = _ajson.load(open(_METRICS_FILE))
except Exception:
    _METRICS = {}

@app.get("/api/track")
async def track_event(e: str = ""):
    e = (e or "").strip()[:40]
    if e:
        _METRICS[e] = _METRICS.get(e, 0) + 1
        try: _ajson.dump(_METRICS, open(_METRICS_FILE, "w"))
        except Exception: pass
    return {"ok": True}

@app.get("/api/stats")
async def get_stats():
    m = dict(_METRICS)
    def g(k): return m.get(k, 0)
    def pct(a, b): return round(a / b * 100, 1) if b else 0.0
    vl, va, cs, cp = g("view_landing"), g("view_app"), g("cta_start"), g("cta_pro")
    return {"raw": m, "landing_views": vl, "app_views": va, "start_free_clicks": cs, "go_pro_clicks": cp,
            "landing_to_app_pct": pct(va, vl), "landing_to_anyCTA_pct": pct(cs + cp, vl), "pro_intent_pct": pct(cp, vl)}


# --- email / waitlist capture (start collecting leads now; swap to Beehiiv for durability) ---
_SUBS_FILE = "/tmp/ac_subscribers.json"
_SUBS = []
try:
    if _aos.path.exists(_SUBS_FILE):
        _SUBS = _ajson.load(open(_SUBS_FILE))
except Exception:
    _SUBS = []

@app.get("/api/subscribe")
async def subscribe(email: str = "", src: str = ""):
    from datetime import datetime as _dtm
    e = (email or "").strip().lower()[:120]
    if "@" in e and "." in e.split("@")[-1]:
        if e not in [s.get("email") for s in _SUBS]:
            _SUBS.append({"email": e, "src": (src or "")[:30], "ts": _dtm.utcnow().isoformat()})
            try: _ajson.dump(_SUBS, open(_SUBS_FILE, "w"))
            except Exception: pass
        _METRICS["subscribe"] = _METRICS.get("subscribe", 0) + 1
        try: _ajson.dump(_METRICS, open(_METRICS_FILE, "w"))
        except Exception: pass
        return {"ok": True, "count": len(_SUBS)}
    return {"ok": False, "error": "invalid email"}

@app.get("/api/subscribers")
async def get_subscribers(token: str = ""):
    if token and token == _aos.getenv("ADMIN_TOKEN", "alphacycle-admin"):
        return {"count": len(_SUBS), "list": _SUBS}
    return {"count": len(_SUBS)}  # public: count only, no PII


# --- auto macro + week-ahead brief (real data + Claude) for the newsletter ---
_MACRO_CACHE = {"day": None, "data": None}

async def _fred_series(sid, n=16):
    key = _aos.getenv("FRED_API_KEY", "")
    if not key or key in ("", "your_key_here"):
        return []
    import httpx
    try:
        async with httpx.AsyncClient(timeout=20) as c:
            r = await c.get("https://api.stlouisfed.org/fred/series/observations",
                            params={"series_id": sid, "api_key": key, "file_type": "json",
                                    "sort_order": "desc", "limit": n})
            obs = [o for o in r.json().get("observations", []) if o.get("value") not in (".", "", None)]
            return [(o["date"], float(o["value"])) for o in obs]
    except Exception:
        return []

async def _fred_macro():
    out = {}
    m2 = await _fred_series("M2SL", 14)
    if m2:
        out["m2_latest_bn"] = round(m2[0][1])
        if len(m2) >= 13:
            out["m2_yoy_pct"] = round((m2[0][1] / m2[12][1] - 1) * 100, 1)
    dxy = await _fred_series("DTWEXBGS", 30)
    if dxy:
        out["dollar_index"] = round(dxy[0][1], 2)
        if len(dxy) >= 5:
            out["dollar_1m_chg_pct"] = round((dxy[0][1] / dxy[4][1] - 1) * 100, 2)
    ff = await _fred_series("DFEDTARU", 3)
    if ff:
        out["fed_funds_upper_pct"] = ff[0][1]
    t10 = await _fred_series("DGS10", 3)
    if t10:
        out["us_10y_pct"] = t10[0][1]
    return out

async def _claude_text(prompt, max_tokens=700):
    key = _aos.getenv("ANTHROPIC_API_KEY") or _aos.getenv("CLAUDE_API_KEY") or ""
    if not key:
        return None
    import httpx
    try:
        async with httpx.AsyncClient(timeout=45) as c:
            r = await c.post("https://api.anthropic.com/v1/messages",
                             headers={"x-api-key": key, "anthropic-version": "2023-06-01",
                                      "content-type": "application/json"},
                             json={"model": _aos.getenv("CLAUDE_MODEL", "claude-haiku-4-5-20251001"),
                                   "max_tokens": max_tokens,
                                   "messages": [{"role": "user", "content": prompt}]})
            if r.status_code != 200:
                return None
            d = r.json()
            return "".join(b.get("text", "") for b in d.get("content", []) if b.get("type") == "text")
    except Exception:
        return None

@app.get("/api/macro-brief")
async def get_macro_brief(request: Request, refresh: int = 0):
    import json as _mjson
    from datetime import datetime as _dtm
    today = _dtm.utcnow().date().isoformat()
    if not refresh and _MACRO_CACHE["day"] == today and _MACRO_CACHE["data"]:
        return _MACRO_CACHE["data"]
    facts = {"date": _dtm.utcnow().strftime("%B %d, %Y")}
    try:
        import httpx as _hx
        async with _hx.AsyncClient(timeout=15) as _c:
            arc = (await _c.get("https://alphacycle-production.up.railway.app/api/arc-summary")).json()
        facts["arc_score"] = round(arc.get("arc_score")) if arc.get("arc_score") is not None else None
        facts["zone"] = arc.get("zone_name")
        facts["btc_price_usd"] = round(arc.get("btc_price")) if arc.get("btc_price") else None
        facts["fear_greed"] = arc.get("fear_greed")
        nl = arc.get("net_liquidity_data") or {}
        if nl.get("net_liquidity"):
            facts["fed_net_liquidity_usd_tn"] = round(nl["net_liquidity"] / 1e6, 2)
        if nl.get("walcl"):
            facts["fed_balance_sheet_usd_tn"] = round(nl["walcl"] / 1e6, 2)
    except Exception:
        pass
    try:
        facts.update(await _fred_macro())
    except Exception:
        pass

    # Fixed brand voice — identical every week, beginner-friendly (real number -> plain meaning).
    style = (
        "VOICE (use this exact style every issue): 'The ARC Report' — calm, plain US English, written so a complete "
        "beginner with no finance background instantly understands it. No hype, no emojis, no price predictions or "
        "targets, no financial advice, no unexplained jargon. Method for every point: state the real number, then a "
        "short simple sentence on what it means for Bitcoin. Keep the same structure and length every week."
    )
    # Step 1 — generate
    gen_prompt = (
        style + "\n\nDATE: " + facts["date"] + "\nREAL DATA (JSON — use ONLY these numbers, never invent any): "
        + _mjson.dumps(facts) + "\n\n"
        "Write ONLY valid JSON (no markdown) with two string keys:\n"
        '"macro": 3-5 short sentences. Cover Fed net liquidity / balance sheet, M2, the dollar (DXY), rates (Fed funds, '
        "10Y) and Fear & Greed where present. For EACH: the real number, then a plain-English 'what this means for "
        "Bitcoin'. Explain simply that more liquidity + a weaker dollar + lower rates is usually good for Bitcoin, and "
        "the opposite is a headwind.\n"
        '"week_ahead": 2-3 short sentences naming the key upcoming U.S. data (CPI ~mid-month, jobs report first Friday, '
        "FOMC if scheduled, PCE ~month-end) and, in plain words, why each matters. Dates approximate."
    )
    draft = await _claude_text(gen_prompt, 750)
    # Step 2 — verify & correct against the real facts before we use it
    verified = None
    if draft:
        verify_prompt = (
            style + "\n\nDATE: " + facts["date"] + "\nREAL DATA (JSON — the single source of truth): "
            + _mjson.dumps(facts) + "\n\nDRAFT to review:\n" + draft + "\n\n"
            "Return a corrected final version. Rules: (1) EVERY number in the text must exactly match the REAL DATA — "
            "fix or remove any figure that doesn't, and never add numbers not in the data; (2) it must read so a total "
            "beginner understands it — each fact followed by a simple 'what it means'; (3) match the VOICE exactly; "
            "(4) add anything important that is in the data but missing; (5) no hype, predictions or advice. "
            'Return ONLY valid JSON with keys "macro" and "week_ahead".'
        )
        verified = await _claude_text(verify_prompt, 750)
    final = verified or draft
    macro = week = None
    if final:
        try:
            j = _mjson.loads(final[final.find("{"): final.rfind("}") + 1])
            macro = (j.get("macro") or "").strip() or None
            week = (j.get("week_ahead") or "").strip() or None
        except Exception:
            pass
    if not macro:
        # Beginner-friendly fallback: real number -> plain meaning, built only from the real facts.
        s = []
        liq = facts.get("fed_net_liquidity_usd_tn")
        if liq: s.append("Fed net liquidity is about $%.2f trillion — that's how much money is sloshing around the system; more of it usually helps Bitcoin." % liq)
        if facts.get("m2_yoy_pct") is not None: s.append("The US money supply (M2) is %s%.1f%% versus a year ago — growing money supply has historically been a tailwind for Bitcoin." % ("+" if facts["m2_yoy_pct"] >= 0 else "", facts["m2_yoy_pct"]))
        if facts.get("dollar_index"): s.append("The US dollar index is %.1f — a weaker dollar tends to help Bitcoin, a stronger one tends to weigh on it." % facts["dollar_index"])
        if facts.get("us_10y_pct"): s.append("The 10-year Treasury yield is %.2f%% — higher rates make safe bonds more attractive and pull money away from risk assets like Bitcoin." % facts["us_10y_pct"])
        if facts.get("fear_greed") is not None: s.append("Crypto Fear & Greed is %s out of 100 — low means people are fearful (historically closer to opportunity than danger)." % facts["fear_greed"])
        macro = " ".join(s) if s else "Macro data is being refreshed — check back shortly."
    if not week:
        week = ("Key US data to watch: inflation (CPI, ~mid-month) — cooler numbers usually help Bitcoin; the monthly "
                "jobs report (first Friday); any Fed interest-rate decision (FOMC); and the Fed's preferred inflation "
                "gauge (PCE, ~month-end). In short: softer inflation and easier policy support risk assets; hot data "
                "pressures them. (Dates approximate — confirm on an economic calendar.)")
    data = {"macro": macro, "week_ahead": week, "facts": facts, "asof": today,
            "generated_by": ("claude-verified" if verified else ("claude" if draft else "fallback"))}
    _MACRO_CACHE["day"] = today
    _MACRO_CACHE["data"] = data
    return data


# --- "Today's Read": AI plain-English summary of the whole dashboard (Claude, day-cached) ---
_READ_CACHE = {"day": None, "data": None}

@app.get("/api/daily-read")
async def get_daily_read(refresh: int = 0):
    import json as _rjson, httpx as _hx
    from datetime import datetime as _dtm
    today = _dtm.utcnow().date().isoformat()
    if not refresh and _READ_CACHE["day"] == today and _READ_CACHE["data"]:
        return _READ_CACHE["data"]
    base = "https://alphacycle-production.up.railway.app"
    f = {}
    try:
        async with _hx.AsyncClient(timeout=15) as c:
            arc = (await c.get(base + "/api/arc-summary")).json()
            cw = (await c.get(base + "/api/cycle-wave?asset=btc")).json()
            rsi = (await c.get(base + "/api/rsi")).json()
        sc = arc.get("arc_score")
        f["arc_score"] = round(sc) if sc is not None else None
        f["zone"] = arc.get("zone_name")
        f["decision"] = ("BUY (all-in)" if (sc is not None and sc <= 25) else ("SELL (take profit)" if (sc is not None and sc >= 75) else "HOLD"))
        f["btc_price_usd"] = round(arc.get("btc_price")) if arc.get("btc_price") else None
        f["fear_greed"] = arc.get("fear_greed")
        f["rsi"] = rsi.get("rsi")
        f["rsi_zone"] = rsi.get("zone")
        f["cycle_direction"] = cw.get("direction")
        nt = cw.get("next_turn") or {}
        f["next_cycle_turn"] = (nt.get("type") + " ~" + str(nt.get("date"))) if nt.get("type") else None
    except Exception:
        pass

    style = ("VOICE: 'AlphaCycle — Today's Read'. Calm, plain US English a complete beginner understands instantly. "
             "No hype, no emojis, no price predictions/targets, no financial advice, no jargon without a plain explanation.")
    read = None
    gen = (style + "\n\nDATE: " + _dtm.utcnow().strftime("%B %d, %Y") + "\nLIVE FACTS (use ONLY these, never invent): "
           + _rjson.dumps(f) + "\n\nWrite ONE short paragraph (3-4 sentences) called Today's Read that tells a beginner, "
           "in plain words: where Bitcoin is in its cycle right now (the score and zone), what the rule says to do, and "
           "one line on the short-term picture (RSI / cycle direction). End by reminding it's context, not advice. "
           'Return ONLY valid JSON: {"read": "..."}.')
    draft = await _claude_text(gen, 380)
    verified = None
    if draft:
        vp = (style + "\nLIVE FACTS (source of truth): " + _rjson.dumps(f) + "\nDRAFT:\n" + draft +
              "\n\nReturn a corrected final version: every number must match the FACTS exactly (fix/remove otherwise, "
              "add none), beginner-clear, on-voice, no advice. Return ONLY JSON {\"read\":\"...\"}.")
        verified = await _claude_text(vp, 380)
    final = verified or draft
    if final:
        try:
            read = (_rjson.loads(final[final.find("{"): final.rfind("}") + 1]).get("read") or "").strip() or None
        except Exception:
            pass
    if not read:
        if f.get("arc_score") is not None:
            read = ("Bitcoin's cycle score is %s out of 100 — %s. The rule says %s (buy only when it's extremely low under 25, "
                    "take profit only when it's extremely high over 75, otherwise hold). Short term, the daily RSI is %s and the "
                    "dominant cycle is %s. This is context to think with, not financial advice." % (
                        f["arc_score"], f.get("zone") or "—", f.get("decision") or "HOLD",
                        (str(f.get("rsi")) + " (" + (f.get("rsi_zone") or "") + ")") if f.get("rsi") is not None else "neutral",
                        f.get("cycle_direction") or "mixed"))
        else:
            read = "Today's read is refreshing — open the dashboard for the live score. Context, not financial advice."
    data = {"read": read, "facts": f, "asof": today,
            "generated_by": ("claude-verified" if verified else ("claude" if draft else "fallback"))}
    _READ_CACHE["day"] = today
    _READ_CACHE["data"] = data
    return data


# --- seasonality (computed from full daily BTC history) ---
_SEASON_CACHE = {"day": None, "data": None}

@app.get("/api/seasonality")
async def get_seasonality():
    from datetime import datetime as _dtm, timedelta as _td, date as _date
    import statistics as _st
    from collections import defaultdict as _dd
    today = _dtm.utcnow().date()
    if _SEASON_CACHE["day"] == today.isoformat() and _SEASON_CACHE["data"]:
        return _SEASON_CACHE["data"]
    try:
        from services.backtest_engine import _load_or_build_daily_cache
        daily = await _load_or_build_daily_cache()
    except Exception as ex:
        raise HTTPException(503, f"price history unavailable: {ex}")
    rows = [dict(r) for r in (daily or []) if r.get("price")]
    for r in rows:
        r["_dt"] = _dtm.fromisoformat(r["date"][:10]).date()
    rows.sort(key=lambda r: r["_dt"])
    if len(rows) < 400:
        raise HTTPException(503, "insufficient history")

    # monthly returns (last/first within calendar month)
    by_ym = _dd(list)
    for r in rows:
        by_ym[(r["_dt"].year, r["_dt"].month)].append(r)
    mret = {}
    for ym, seg in by_ym.items():
        seg.sort(key=lambda r: r["_dt"])
        mret[ym] = seg[-1]["price"] / seg[0]["price"] - 1
    bym = _dd(list)
    for (y, m), v in mret.items():
        bym[m].append(v)
    from math import comb as _comb
    def _binom_p(k, n):
        # two-sided p-value vs a fair coin (probability a directional bias this strong is chance)
        if n == 0:
            return 1.0
        le = sum(_comb(n, i) for i in range(0, k + 1)) / (2 ** n)
        ge = sum(_comb(n, i) for i in range(k, n + 1)) / (2 ** n)
        return min(1.0, 2 * min(le, ge))
    P_GATE = 0.10   # secondary info: probability the bias is chance
    N_MIN = 10
    WIN_GATE = 70   # show a month only if its directional consistency >= 70%
    months = []
    for m in range(1, 13):
        v = bym.get(m, [])
        n = len(v)
        up = sum(1 for x in v if x > 0)
        win = round(up / n * 100) if n else None
        p = round(_binom_p(up, n), 3) if n else None
        high = bool(n >= N_MIN and win is not None and max(win, 100 - win) >= WIN_GATE)
        months.append({"month": m,
                       "avg": round(_st.mean(v) * 100, 1) if v else None,
                       "median": round(_st.median(v) * 100, 1) if v else None,
                       "win": win, "n": n, "p": p,
                       "dir": (None if not n else ("up" if up * 2 > n else "down")),
                       "high_conf": high})
    month_signals = [{"month": m["month"], "dir": m["dir"], "median": m["median"],
                      "win": m["win"], "n": m["n"], "p": m["p"]}
                     for m in months if m["high_conf"]]
    # weekly scan (same >=70% gate) — usually noise, but check
    by_week_yr = _dd(list)
    for r in rows:
        iy, iw, _ = r["_dt"].isocalendar()
        by_week_yr[(iy, iw)].append(r)
    wk_ret = _dd(list)
    for (iy, iw), seg in by_week_yr.items():
        seg.sort(key=lambda r: r["_dt"])
        if len(seg) >= 2:
            wk_ret[iw].append(seg[-1]["price"] / seg[0]["price"] - 1)
    week_signals = []
    for iw in range(1, 54):
        v = wk_ret.get(iw, [])
        n = len(v)
        if n < 8:
            continue
        up = sum(1 for x in v if x > 0)
        win = round(up / n * 100)
        if max(win, 100 - win) >= WIN_GATE:
            week_signals.append({"week": iw, "dir": ("up" if up * 2 > n else "down"),
                                 "win": win, "median": round(_st.median(v) * 100, 1), "n": n})
    years = sorted({y for (y, m) in mret})
    grid = [{"year": y, "vals": [(round(mret[(y, m)] * 100, 1) if (y, m) in mret else None) for m in range(1, 13)]}
            for y in years]

    # quarterly
    byq = _dd(list)
    for (y, m), v in mret.items():
        byq[(m - 1) // 3 + 1].append(v)
    quarters = [{"q": q, "avg": round(_st.mean(byq[q]) * 100, 1), "n": len(byq[q])} for q in range(1, 5) if byq[q]]

    # halving cycle path (index, halving day = 1.0) — each cycle shown separately
    # (no self-referential average; the diminishing multiple per cycle is the real story)
    HALV = [_date(2016, 7, 9), _date(2020, 5, 11), _date(2024, 4, 20)]
    cur_halv = max([h for h in [_date(2012, 11, 28)] + HALV if h <= today], default=None)
    NMO = 25
    cycles_by_year = {}
    for hi, h in enumerate(HALV):
        base = next((r["price"] for r in rows if r["_dt"] >= h), None)
        if base is None:
            continue
        end = HALV[hi + 1] if hi + 1 < len(HALV) else rows[-1]["_dt"]
        arr = [None] * NMO
        seen = set()
        for r in rows:
            if h <= r["_dt"] < end:
                mo = (r["_dt"].year - h.year) * 12 + (r["_dt"].month - h.month)
                if 0 <= mo < NMO and mo not in seen:
                    seen.add(mo)
                    arr[mo] = round(r["price"] / base, 3)
        cycles_by_year[str(h.year)] = arr
    cur_key = str(cur_halv.year) if cur_halv else None
    # backward-compatible "cycle" array: avg of COMPLETED cycles + current path
    completed = [v for k, v in cycles_by_year.items() if k != cur_key]
    cycle = []
    for mo in range(0, NMO):
        vals = [c[mo] for c in completed if c[mo] is not None]
        cur_v = cycles_by_year.get(cur_key, [None] * NMO)[mo] if cur_key else None
        cycle.append({"mo": mo,
                      "avg": round(_st.mean(vals), 3) if vals else None,
                      "n": len(vals),
                      "current": cur_v})
    months_since_halving = ((today.year - cur_halv.year) * 12 + (today.month - cur_halv.month)) if cur_halv else None

    # forward outlook: calendar-anchored from TODAY, real N-day returns across all past years.
    # Only flagged high_conf when the directional bias is statistically unlikely to be chance.
    def _p_on_after(d):
        return next((r["price"] for r in rows if r["_dt"] >= d), None)
    last_dt = rows[-1]["_dt"]
    safe_day = min(today.day, 28)
    forward = []
    for hor in (30, 60, 90):
        rets = []
        for y in range(rows[0]["_dt"].year, today.year):  # completed years only
            try:
                start = _date(y, today.month, safe_day)
            except ValueError:
                continue
            tgt = start + _td(days=hor)
            if tgt > last_dt:
                continue
            p0 = _p_on_after(start)
            p1 = _p_on_after(tgt)
            if p0 and p1:
                rets.append(p1 / p0 - 1)
        if rets:
            up = sum(1 for x in rets if x > 0)
            win = round(up / len(rets) * 100)
            p = round(_binom_p(up, len(rets)), 3)
            forward.append({"hor": hor, "median": round(_st.median(rets) * 100, 1),
                            "win": win, "n": len(rets), "p": p,
                            "dir": ("up" if up * 2 > len(rets) else "down"),
                            "high_conf": bool(len(rets) >= 8 and p < P_GATE)})
        else:
            forward.append({"hor": hor, "median": None, "win": None, "n": 0, "p": None,
                            "dir": None, "high_conf": False})

    data = {"range": {"from": rows[0]["date"][:10], "to": rows[-1]["date"][:10], "days": len(rows)},
            "months": months, "month_signals": month_signals, "week_signals": week_signals,
            "grid": grid, "quarters": quarters,
            "cycle": cycle, "cycles_by_year": cycles_by_year,
            "months_since_halving": months_since_halving,
            "last_halving": cur_halv.isoformat() if cur_halv else None,
            "forward": forward}
    _SEASON_CACHE["day"] = today.isoformat()
    _SEASON_CACHE["data"] = data
    return data


# --- cycle moving-average top/bottom signals (Pi Cycle, Mayer, 200WMA) ---
_CYCLE_CACHE = {"day": None, "data": None}

@app.get("/api/cycle-signals")
async def get_cycle_signals(debug: int = 0):
    from datetime import datetime as _dtm
    today = _dtm.utcnow().date().isoformat()
    if not debug and _CYCLE_CACHE["day"] == today and _CYCLE_CACHE["data"]:
        return _CYCLE_CACHE["data"]
    try:
        from services.backtest_engine import _load_or_build_daily_cache
        daily = await _load_or_build_daily_cache()
    except Exception as ex:
        raise HTTPException(503, f"price history unavailable: {ex}")
    rows = [r for r in (daily or []) if r.get("price")]
    rows.sort(key=lambda r: r["date"])
    n = len(rows)
    if n < 800:
        raise HTTPException(503, "insufficient history")
    price = [r["price"] for r in rows]
    dates = [r["date"][:10] for r in rows]
    pref = [0.0] * (n + 1)
    for i in range(n):
        pref[i + 1] = pref[i] + price[i]

    def sma(w, i):
        if i + 1 < w:
            return None
        return (pref[i + 1] - pref[i + 1 - w]) / w

    # Pi Cycle Top: 111DMA crossing above 2 x 350DMA marks cycle tops
    crosses, prev_below = [], None
    for i in range(n):
        m111, m350 = sma(111, i), sma(350, i)
        if m111 is None or m350 is None:
            continue
        below = m111 < 2 * m350
        if prev_below is True and below is False:
            crosses.append({"date": dates[i], "price": round(price[i])})
        prev_below = below
    i = n - 1
    m111, m350, m200, m1400 = sma(111, i), sma(350, i), sma(200, i), sma(1400, i)
    ma350x2 = 2 * m350 if m350 else None
    # gap_pct: how far the top trigger sits above the 111DMA (smaller = closer to a top; <=0 = triggered)
    pi_gap = round((ma350x2 / m111 - 1) * 100, 1) if (m111 and ma350x2) else None
    pi_now = bool(m111 and ma350x2 and m111 >= ma350x2)
    mayer = round(price[i] / m200, 2) if m200 else None

    data = {"asof": dates[-1], "price": round(price[-1]),
            "pi": {"ma111": round(m111) if m111 else None,
                   "ma350x2": round(ma350x2) if ma350x2 else None,
                   "gap_pct": pi_gap, "triggered": pi_now, "crosses": crosses},
            "mayer": {"value": mayer, "ma200": round(m200) if m200 else None},
            "ma200w": {"value": round(m1400) if m1400 else None,
                       "pct_above": round((price[i] / m1400 - 1) * 100, 1) if m1400 else None}}

    if debug:
        # one-off empirical sweep: which short/long MA pair's cross-ups land nearest real tops?
        # known top dates across cycles
        tops = ["2013-12-04", "2017-12-17", "2021-04-14", "2021-11-10", "2025-10-06"]
        from datetime import date as _d
        def _parse(s):
            return _d(*[int(x) for x in s.split("-")])
        top_d = [_parse(t) for t in tops]
        sweep = []
        for short in (100, 111, 125, 150):
            for long, mult in ((350, 2), (365, 2), (300, 2)):
                cr = []
                pb = None
                for i2 in range(n):
                    a, b = sma(short, i2), sma(long, i2)
                    if a is None or b is None:
                        continue
                    bl = a < mult * b
                    if pb is True and bl is False:
                        cr.append(_parse(dates[i2]))
                    pb = bl
                # nearest distance of each real top to any cross
                if cr:
                    dist = []
                    for td in top_d:
                        dd = min(abs((td - c).days) for c in cr)
                        dist.append(dd)
                    sweep.append({"pair": f"{short}/{long}x{mult}", "ncross": len(cr),
                                  "avg_days_to_top": round(sum(dist) / len(dist), 1),
                                  "max_days": max(dist)})
        sweep.sort(key=lambda x: x["avg_days_to_top"])
        data["sweep"] = sweep

    if not debug:
        _CYCLE_CACHE["day"] = today
        _CYCLE_CACHE["data"] = data
    return data


# --- Seasonax-style seasonal pattern (avg intra-year path) for BTC & ETH ---
_SEASONAL_CACHE = {"day": None, "data": None}

async def _load_eth_daily():
    """Daily ETH/USD closes from CryptoCompare (full history ~2016+), cached in /tmp."""
    import json as _j, os as _o, httpx
    from datetime import datetime as _dt
    f = "/tmp/eth_daily_cache.json"
    try:
        if _o.path.exists(f):
            c = _j.load(open(f))
            if c and c[-1]["date"][:7] >= _dt.utcnow().date().isoformat()[:7]:
                return c
    except Exception:
        pass
    out = []
    try:
        async with httpx.AsyncClient(timeout=30, follow_redirects=True) as client:
            r = await client.get("https://min-api.cryptocompare.com/data/v2/histoday",
                                  params={"fsym": "ETH", "tsym": "USD", "allData": "true"})
            for row in (r.json().get("Data", {}) or {}).get("Data", []):
                close = float(row.get("close") or 0)
                if close > 0:
                    out.append({"date": _dt.utcfromtimestamp(row["time"]).date().isoformat(), "price": close})
        out.sort(key=lambda x: x["date"])
        if out:
            _j.dump(out, open(f, "w"))
    except Exception:
        return []
    return out


def _seasonal_curve(rows, cur_year):
    """Geometric-average intra-year path (Jan 1 = 100), robust to outlier years.
       Returns (path[365], n_years, monthly_pct[12])."""
    import math
    from collections import defaultdict
    from datetime import date as _date
    by_year = defaultdict(list)
    for r in rows:
        by_year[int(r["date"][:4])].append(r)
    by_doy = defaultdict(list)
    n_years = 0
    for y, seg in by_year.items():
        if y >= cur_year:
            continue
        seg.sort(key=lambda r: r["date"])
        if len(seg) < 350:
            continue
        n_years += 1
        for i in range(1, len(seg)):
            p0, p1 = seg[i - 1]["price"], seg[i]["price"]
            if p0 > 0 and p1 > 0:
                doy = _date(*[int(x) for x in seg[i]["date"].split("-")]).timetuple().tm_yday
                if doy <= 365:
                    by_doy[doy].append(math.log(p1 / p0))
    if n_years == 0:
        return None, 0, None
    path, cum = [], 0.0
    for doy in range(1, 366):
        rs = by_doy.get(doy, [])
        if rs:
            cum += sum(rs) / len(rs)
        path.append(round(100 * math.exp(cum), 1))
    # monthly % change from the curve (month boundaries by day-of-year)
    mb = [0, 31, 59, 90, 120, 151, 181, 212, 243, 273, 304, 334, 365]
    monthly = []
    for m in range(12):
        a, b = path[mb[m]], path[mb[m + 1] - 1]
        monthly.append(round((b / a - 1) * 100, 1))
    return path, n_years, monthly


@app.get("/api/seasonal-pattern")
async def get_seasonal_pattern():
    from datetime import datetime as _dtm
    today = _dtm.utcnow().date().isoformat()
    if _SEASONAL_CACHE["day"] == today and _SEASONAL_CACHE["data"]:
        return _SEASONAL_CACHE["data"]
    try:
        from services.backtest_engine import _load_or_build_daily_cache
        btc = await _load_or_build_daily_cache()
    except Exception as ex:
        raise HTTPException(503, f"price history unavailable: {ex}")
    btc = [{"date": r["date"][:10], "price": r["price"]} for r in (btc or []) if r.get("price")]
    eth = await _load_eth_daily()
    cur_year = int(today[:4])
    names = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]

    def pack(rows, label):
        path, ny, monthly = _seasonal_curve(rows, cur_year) if rows else (None, 0, None)
        if not path:
            return {"path": None, "years": 0, "monthly": None, "from": None, "to": None,
                    "strong": None, "weak": None}
        strong = names[max(range(12), key=lambda i: monthly[i])]
        weak = names[min(range(12), key=lambda i: monthly[i])]
        return {"path": path, "years": ny, "monthly": monthly,
                "from": rows[0]["date"][:4], "to": rows[-1]["date"][:4],
                "strong": strong, "weak": weak}

    data = {"asof": today,
            "btc": pack(btc, "BTC"),
            "eth": pack(eth, "ETH")}
    _SEASONAL_CACHE["day"] = today
    _SEASONAL_CACHE["data"] = data
    return data


# --- Engine 6 overlay: actual current-year BTC price vs its seasonal pattern ---
_OVERLAY_CACHE = {"day": None, "data": None}

@app.get("/api/seasonal-overlay")
async def get_seasonal_overlay():
    from datetime import datetime as _dtm, date as _date, timedelta as _td
    import statistics as _st
    from collections import defaultdict as _dd
    today = _dtm.utcnow().date()
    if _OVERLAY_CACHE["day"] == today.isoformat() and _OVERLAY_CACHE["data"]:
        return _OVERLAY_CACHE["data"]
    try:
        from services.backtest_engine import _load_or_build_daily_cache
        daily = await _load_or_build_daily_cache()
    except Exception as ex:
        raise HTTPException(503, f"price history unavailable: {ex}")
    rows = [{"date": r["date"][:10], "price": r["price"]} for r in (daily or []) if r.get("price")]
    rows.sort(key=lambda r: r["date"])
    if len(rows) < 400:
        raise HTTPException(503, "insufficient history")
    cur_year = today.year
    names = ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"]
    path, ny, _monthly = _seasonal_curve(rows, cur_year)
    if not path:
        raise HTTPException(503, "no seasonal curve")
    # actual: last ~18 months for context
    cutoff = (today - _td(days=540)).isoformat()
    actual = [r for r in rows if r["date"] >= cutoff]
    last_price = rows[-1]["price"]
    last_doy = min(today.timetuple().tm_yday, 365)
    base_path = path[last_doy - 1]
    # forward seasonal projection REBASED to current price (slope = seasonal tendency from here)
    seasonal = [{"date": rows[-1]["date"], "price": round(last_price)}]
    for doy in range(last_doy + 1, 366):
        dt = _date(cur_year, 1, 1) + _td(days=doy - 1)
        if dt.year != cur_year:
            break
        seasonal.append({"date": dt.isoformat(), "price": round(last_price * path[doy - 1] / base_path)})
    # monthly median + win across COMPLETE prior years
    by_ym = _dd(list)
    for r in rows:
        by_ym[(int(r["date"][:4]), int(r["date"][5:7]))].append(r)
    mret = {}
    for ym, seg in by_ym.items():
        seg.sort(key=lambda r: r["date"])
        mret[ym] = seg[-1]["price"] / seg[0]["price"] - 1
    bym = _dd(list)
    for (y, m), v in mret.items():
        if y < cur_year:
            bym[m].append(v)

    def mstat(m):
        v = bym.get(m, [])
        if not v:
            return None
        up = sum(1 for x in v if x > 0)
        return {"month": m, "name": names[m - 1], "median": round(_st.median(v) * 100, 1),
                "win": round(up / len(v) * 100), "n": len(v),
                "dir": "up" if up * 2 > len(v) else "down"}

    tm = today.month
    data = {"asof": rows[-1]["date"], "year": cur_year, "years": ny, "price": round(last_price),
            "actual": actual, "seasonal": seasonal,
            "this_month": mstat(tm), "next_month": mstat(tm % 12 + 1)}
    _OVERLAY_CACHE["day"] = today.isoformat()
    _OVERLAY_CACHE["data"] = data
    return data


# --- Dominant cycle wave (Seasonax-style): detect & project the rhythm ---
_WAVE_CACHE = {}

@app.get("/api/cycle-wave")
async def get_cycle_wave(asset: str = "btc", lookback: int = 2190, projection: int = 180):
    from datetime import datetime as _dtm, date as _date, timedelta as _td
    import math
    ck = f"{_dtm.utcnow().date().isoformat()}|{asset}|{lookback}|{projection}"
    if _WAVE_CACHE.get("key") == ck:
        return _WAVE_CACHE["data"]
    try:
        if asset == "eth":
            daily = await _load_eth_daily()
        else:
            from services.backtest_engine import _load_or_build_daily_cache
            daily = await _load_or_build_daily_cache()
    except Exception as ex:
        raise HTTPException(503, f"price history unavailable: {ex}")
    rows = [{"date": r["date"][:10], "price": float(r["price"])} for r in (daily or []) if r.get("price")]
    rows.sort(key=lambda r: r["date"])
    # day-of-year, day-of-week & month "tilts" from the FULL history (10y) for a realistic,
    # jagged daily forecast path — what the market actually did on that calendar day/week/month.
    _dow_sum, _dow_n, _mon_sum, _mon_n, _doy_sum, _doy_n, _all = {}, {}, {}, {}, {}, {}, []
    for _i in range(1, len(rows)):
        _p0, _p1 = rows[_i - 1]["price"], rows[_i]["price"]
        if _p0 > 0 and _p1 > 0:
            _lr = math.log(_p1 / _p0); _all.append(_lr)
            _d = _date.fromisoformat(rows[_i]["date"])
            _wd, _mo, _dy = _d.weekday(), _d.month, _d.timetuple().tm_yday
            _dow_sum[_wd] = _dow_sum.get(_wd, 0) + _lr; _dow_n[_wd] = _dow_n.get(_wd, 0) + 1
            _mon_sum[_mo] = _mon_sum.get(_mo, 0) + _lr; _mon_n[_mo] = _mon_n.get(_mo, 0) + 1
            _doy_sum[_dy] = _doy_sum.get(_dy, 0) + _lr; _doy_n[_dy] = _doy_n.get(_dy, 0) + 1
    _gmean = (sum(_all) / len(_all)) if _all else 0.0
    dow_tilt = {k: _dow_sum[k] / _dow_n[k] - _gmean for k in _dow_sum}
    mon_tilt = {k: _mon_sum[k] / _mon_n[k] - _gmean for k in _mon_sum}
    doy_tilt = {k: _doy_sum[k] / _doy_n[k] - _gmean for k in _doy_sum}  # granular daily texture
    rows = rows[-lookback:]
    n = len(rows)
    if n < 300:
        raise HTTPException(503, "insufficient history")
    y = [math.log(r["price"]) for r in rows]
    t = list(range(n))
    # Band-pass detrend: remove the multi-year arc with a centred 1-year moving average,
    # leaving the shorter oscillation a single sine can actually fit (Seasonax-style).
    W = 365
    half = W // 2
    csum = [0.0]
    for v in y:
        csum.append(csum[-1] + v)
    trend = [(csum[min(n, i + half + 1)] - csum[max(0, i - half)]) / (min(n, i + half + 1) - max(0, i - half))
             for i in range(n)]
    resid = [y[i] - trend[i] for i in range(n)]
    tot = sum(r * r for r in resid) or 1e-9
    k_end = min(180, n - 1)
    slope_end = (trend[n - 1] - trend[n - 1 - k_end]) / k_end

    def trend_at(i):
        return trend[i] if i < n else trend[n - 1] + slope_end * (i - (n - 1))
    # Search repeating cycles only (>=4 full cycles in the window) so we get a stable
    # oscillator whose peaks/troughs track real highs/lows — not one giant arc.
    Lmax = max(180, min(n // 4, 520))
    half = n // 2
    cands = []  # (score, L, c1, c2, r2, stab)
    for L in range(120, Lmax, 2):
        w = 2 * math.pi / L
        C = [math.cos(w * i) for i in t]
        S = [math.sin(w * i) for i in t]
        Scc = sum(v * v for v in C); Sss = sum(v * v for v in S); Scs = sum(C[i] * S[i] for i in range(n))
        Rc = sum(resid[i] * C[i] for i in range(n)); Rs = sum(resid[i] * S[i] for i in range(n))
        det = (Scc * Sss - Scs * Scs) or 1e-9
        c1 = (Rc * Sss - Rs * Scs) / det
        c2 = (Scc * Rs - Scs * Rc) / det
        ss = sum((resid[i] - (c1 * C[i] + c2 * S[i])) ** 2 for i in range(n))
        r2 = 1 - ss / tot
        # stability: amplitude consistency first vs second half (Bartels-like)
        amp1 = math.hypot(sum(resid[i] * C[i] for i in range(half)) / (half / 2 or 1),
                          sum(resid[i] * S[i] for i in range(half)) / (half / 2 or 1))
        amp2 = math.hypot(sum(resid[i] * C[i] for i in range(half, n)) / ((n - half) / 2 or 1),
                          sum(resid[i] * S[i] for i in range(half, n)) / ((n - half) / 2 or 1))
        stab = min(amp1, amp2) / (max(amp1, amp2) or 1e-9)
        score = stab * (0.4 + 0.6 * max(r2, 0))  # favour STABILITY (Seasonax/Bartels-like)
        cands.append((score, L, c1, c2, r2, stab))
    # pick top-3 distinct cycles (periods must differ >25% so we don't show near-duplicates)
    cands.sort(key=lambda x: -x[0])
    picked = []
    for cand in cands:
        if all(abs(cand[1] - p[1]) / p[1] > 0.25 for p in picked):
            picked.append(cand)
        if len(picked) >= 3:
            break
    _score, L, c1, c2, r2, stab = picked[0]
    w = 2 * math.pi / L
    phi = math.atan2(c2, c1)  # resid ~ R*cos(w*i - phi); peak at w*i = phi
    i_now = n - 1

    def _phase_label(L_, c1_, c2_):
        w_ = 2 * math.pi / L_; phi_ = math.atan2(c2_, c1_)
        cv = math.cos(w_ * i_now - phi_); dv = math.sin(w_ * i_now - phi_)
        if cv > 0.85: return "topping"
        if cv < -0.85: return "bottoming"
        return "rising" if dv < 0 else "falling"
    secondary = [{"period": int(p[1]), "phase_label": _phase_label(p[1], p[2], p[3]),
                  "stability": round(p[5], 2)} for p in picked[1:3]]

    # --- Seasonax-style display: a REGULAR constant-amplitude sine, price laid over it ---
    n_disp = min(1095, n)               # ~3y visible window (clean on a linear axis)
    off = n - n_disp                    # display start index in the detection frame
    disp = rows[-n_disp:]
    dprices = [r["price"] for r in disp]
    pmin, pmax = min(dprices), max(dprices)
    center = (pmax + pmin) / 2.0
    amp = (pmax - pmin) / 2.0

    def cyc(i_global):                  # constant-amplitude regular cycle (aligned to price highs/lows)
        return round(center + amp * math.cos(w * i_global - phi), 2)

    hist_dates = [r["date"] for r in disp]
    last = _date.fromisoformat(hist_dates[-1])
    proj_dates = [(last + _td(days=k)).isoformat() for k in range(1, projection + 1)]
    all_dates = hist_dates + proj_dates
    wave = [cyc(off + j) for j in range(n_disp + projection)]
    price = [round(p, 2) for p in dprices] + [None] * projection

    # phase read at the latest bar (theta=0 -> peak, theta=pi -> trough)
    theta = (w * i_now - phi) % (2 * math.pi)
    cos_now = math.cos(theta)
    if cos_now > 0.85:
        direction = "topping"
    elif cos_now < -0.85:
        direction = "bottoming"
    else:
        direction = "rising" if math.sin(theta) < 0 else "falling"
    days_to_high = round(((-theta) % (2 * math.pi)) / w)
    days_to_low = round(((math.pi - theta) % (2 * math.pi)) / w)
    pct_into_cycle = round(((theta - math.pi) % (2 * math.pi)) / (2 * math.pi) * 100)  # since last trough
    if days_to_high <= days_to_low:
        next_turn = {"type": "peak", "in_days": days_to_high,
                     "date": (last + _td(days=days_to_high)).isoformat()}
    else:
        next_turn = {"type": "trough", "in_days": days_to_low,
                     "date": (last + _td(days=days_to_low)).isoformat()}
    # red price forecast: follows the dominant cycle (the magenta line) in RELATIVE terms — so red
    # and the cycle always rise and fall TOGETHER (no contradiction) — anchored to today's price,
    # PLUS the real 10y day-of-year/weekday tendencies for a lifelike daily zig-zag (not a clean curve).
    # same phase as the magenta cycle (so they agree on direction) but a realistic, capped
    # amplitude (~peak-to-trough 25-35%), not the full visual range.
    A = 0.05 + 0.09 * stab               # log-amplitude of the forecast's cycle component
    forecast = [None] * (n_disp + projection)
    forecast[n_disp - 1] = round(dprices[-1], 2)
    logp = math.log(dprices[-1])
    for k in range(1, projection + 1):
        gi = i_now + k
        r_cyc = A * (math.cos(w * gi - phi) - math.cos(w * (gi - 1) - phi))
        D = last + _td(days=k)
        logp += r_cyc + doy_tilt.get(D.timetuple().tm_yday, 0.0) + 0.5 * dow_tilt.get(D.weekday(), 0.0)
        forecast[(n_disp - 1) + k] = round(math.exp(logp), 2)

    data = {"asset": asset.upper(), "cycle_len": int(L), "fit": round(r2, 2),
            "stability": round(stab, 2), "direction": direction, "next_turn": next_turn,
            "forecast": forecast,
            "days_to_high": days_to_high, "days_to_low": days_to_low,
            "high_date": (last + _td(days=days_to_high)).isoformat(),
            "low_date": (last + _td(days=days_to_low)).isoformat(),
            "pct_into_cycle": pct_into_cycle, "secondary": secondary,
            "split": n_disp, "dates": all_dates, "price": price, "wave": wave}
    _WAVE_CACHE["key"] = ck
    _WAVE_CACHE["data"] = data
    return data


# --- Daily RSI(14) with historical forward-return edge ---
_RSI_CACHE = {"key": None, "data": None}

@app.get("/api/rsi")
async def get_rsi(period: int = 14, horizon: int = 30):
    from datetime import datetime as _dtm
    import statistics as _st
    key = f"{_dtm.utcnow().date().isoformat()}|{period}|{horizon}"
    if _RSI_CACHE["key"] == key and _RSI_CACHE["data"]:
        return _RSI_CACHE["data"]
    try:
        from services.backtest_engine import _load_or_build_daily_cache
        daily = await _load_or_build_daily_cache()
    except Exception as ex:
        raise HTTPException(503, f"price history unavailable: {ex}")
    rows = [r for r in (daily or []) if r.get("price")]
    rows.sort(key=lambda r: r["date"])
    n = len(rows)
    if n < period + 60:
        raise HTTPException(503, "insufficient history")
    p = [r["price"] for r in rows]
    d = [r["date"][:10] for r in rows]
    # Wilder's RSI
    rsi = [None] * n
    gains = sum(max(p[i] - p[i - 1], 0) for i in range(1, period + 1))
    losses = sum(max(p[i - 1] - p[i], 0) for i in range(1, period + 1))
    ag, al = gains / period, losses / period
    rsi[period] = 100.0 if al == 0 else round(100 - 100 / (1 + ag / al), 1)
    for i in range(period + 1, n):
        ch = p[i] - p[i - 1]
        ag = (ag * (period - 1) + max(ch, 0)) / period
        al = (al * (period - 1) + max(-ch, 0)) / period
        rsi[i] = 100.0 if al == 0 else round(100 - 100 / (1 + ag / al), 1)
    cur = rsi[-1]
    zone = "Oversold" if cur < 25 else ("Overbought" if cur > 75 else "Neutral")

    def edge(enter):
        rets = []
        for i in range(period + 1, n - horizon):
            if rsi[i - 1] is not None and enter(rsi[i - 1], rsi[i]):
                rets.append(p[i + horizon] / p[i] - 1)
        if not rets:
            return None
        up = sum(1 for x in rets if x > 0)
        return {"median": round(_st.median(rets) * 100, 1), "avg": round(_st.mean(rets) * 100, 1),
                "win": round(up / len(rets) * 100), "n": len(rets)}

    oversold = edge(lambda a, b: a >= 25 and b < 25)      # crosses INTO deep oversold (<25)
    overbought = edge(lambda a, b: a <= 75 and b > 75)    # crosses INTO true overbought (>75)
    # baseline: average horizon-day forward return on any day (for comparison)
    base_rets = [p[i + horizon] / p[i] - 1 for i in range(period, n - horizon)]
    baseline = {"median": round(_st.median(base_rets) * 100, 1),
                "win": round(sum(1 for x in base_rets if x > 0) / len(base_rets) * 100),
                "n": len(base_rets)} if base_rets else None
    recent = [{"date": d[i], "rsi": rsi[i]} for i in range(max(period, n - 120), n)]
    data = {"asof": d[-1], "period": period, "horizon": horizon,
            "rsi": cur, "zone": zone,
            "oversold": oversold, "overbought": overbought, "baseline": baseline,
            "recent": recent}
    _RSI_CACHE["key"] = key
    _RSI_CACHE["data"] = data
    return data


# ============================================================================
# DECISION ENGINE — regime-adaptive staged ladder ("Adaptive Ladder")
# ----------------------------------------------------------------------------
# Locked strategy (chosen empirically over 2017-2026, pure python):
#   BUY  -> 40% when ARC <= 38  OR  ARC in bottom 5% of trailing 3yr (regime-proof)
#         -> 40% when ARC <= 45 AND in bottom 10% of trailing 3yr (deep-value net)
#         -> 100% when ARC <= 28
#   SELL -> 0% (all out) when ARC >= 75
#   HOLD -> in between (the ~57% middle), no trades
#   Cooldown: no re-buy within 120 days after a sell (avoids whipsaw)
# Result: 33.1x vs HODL 14.2x, and WINS the rising-floor regime test (the exact
# risk Noah flagged) — buys at 38/relative even if ARC never hits 25 again.
# ============================================================================

async def _full_daily_rows():
    """Full daily backtest rows (date/price/score/arc_score) — same source as
    history-daily/zone-history, which reliably carry the per-day ARC score."""
    rows = CACHE.get("backtest_results", []) if CACHE else []
    if not rows:
        bt = await run_daily_backtest_full()
        rows = bt.get("results", []) if isinstance(bt, dict) else (bt or [])
    return rows


def _decision_series(daily):
    rows = [r for r in (daily or []) if r.get("price") and
            (r.get("arc_score") is not None or r.get("score") is not None)]
    rows.sort(key=lambda r: r["date"])
    dates = [r["date"][:10] for r in rows]
    px = [float(r["price"]) for r in rows]
    arc = [float(r.get("arc_score", r.get("score"))) for r in rows]
    return dates, px, arc


def _pctile_rank(arc, i, window=1095, warm=365):
    if i < warm:
        return None
    lo = max(0, i - window + 1)
    w = arc[lo:i + 1]
    a = arc[i]
    return sum(1 for x in w if x <= a) / len(w)


def _ladder_target(a, alloc, rel, since_sell, state):
    """Fixed adaptive ladder (applied identically every cycle).
    BUY:  40% at ARC<=38 (or relative bottom 5%); FULL 100% at the deep bottom
          (ARC<=20), or — if it dips under 25 but recovers above 25 without
          reaching 20 — commit 100% on that recross (bottom confirmed). This
          chases the absolute low to cut drawdown, with a fallback so a shallow
          bottom is never missed.
    SELL: staged & late — 50% at ARC>=72, all out at >=80.
    Backtest 2017-26: 54x vs HODL 14x, max drawdown -48% vs -84%."""
    # SELL — staged & late (not gated by cooldown)
    if a >= 80:
        state["below25"] = False
        return 0.0
    if a >= 72:
        state["below25"] = False
        return min(alloc, 0.50)
    # BUY — cooldown after a sell to avoid whipsaw
    if since_sell < 120:
        return alloc
    if a < 25:
        state["below25"] = True
    if a <= 20:
        return 1.0  # absolute deep value — full size
    if state.get("below25") and a > 25:
        return 1.0  # bottom confirmed (dipped <25, recovered) — commit rest
    if a <= 38 or (rel is not None and rel <= 0.05):
        return max(alloc, 0.40)
    if a <= 45 and (rel is not None and rel <= 0.10):
        return max(alloc, 0.40)
    return alloc


def _run_ladder(dates, px, arc, start_i=0, cash0=10000.0, cash_yield=0.04):
    """Run the adaptive ladder; return final state + dated actions + value series."""
    cash = cash0
    btc = 0.0
    alloc = 0.0
    last_sell = -99999
    actions = []
    series = []  # (date, strategy_value, hodl_value)
    daily_cash = (1 + cash_yield) ** (1 / 365.0)
    base_px = px[start_i]
    state = {"below25": False}
    peak = 0.0
    max_dd = 0.0
    for i in range(start_i, len(px)):
        cash *= daily_cash
        a = arc[i]
        p = px[i]
        rel = _pctile_rank(arc, i)
        tgt = _ladder_target(a, alloc, rel, i - last_sell, state)
        if abs(tgt - alloc) > 0.02:
            port = cash + btc * p
            diff = port * tgt - btc * p
            if diff > 0:
                buy = min(diff, cash)
                btc += buy / p
                cash -= buy
                actions.append({"date": dates[i], "type": "BUY", "arc": round(a),
                                "price": round(p), "to_pct": round(tgt * 100)})
            else:
                sell = min(-diff, btc * p)
                btc -= sell / p
                cash += sell
                last_sell = i
                actions.append({"date": dates[i], "type": "SELL", "arc": round(a),
                                "price": round(p), "to_pct": round(tgt * 100)})
            alloc = tgt
        port = cash + btc * p
        if port > peak:
            peak = port
        if peak > 0:
            dd = port / peak - 1.0
            if dd < max_dd:
                max_dd = dd
        hodl = cash0 / base_px * p
        series.append((dates[i], round(port, 2), round(hodl, 2)))
    final_p = px[-1]
    return {
        "alloc": alloc,
        "cash": cash,
        "btc": btc,
        "value": round(cash + btc * final_p, 2),
        "actions": actions,
        "series": series,
        "invested_pct": round(alloc * 100),
        "max_dd": round(max_dd * 100, 1),
    }


def _next_step(alloc, cur_arc):
    """Plain-language next move given current allocation + ARC."""
    if alloc < 0.40:
        return {"action": "BUY", "trigger": "ARC \u2264 38",
                "to_pct": 40,
                "text": "First buy step: invest 40% at ARC 38 or below."}
    if alloc < 1.0:
        return {"action": "BUY", "trigger": "ARC \u2264 20",
                "to_pct": 100,
                "text": "Go 100% at the bottom: ARC 20 or below \u2014 or once ARC dips under 25 and then recovers above it (bottom confirmed)."}
    return {"action": "SELL", "trigger": "ARC \u2265 72",
            "to_pct": 50,
            "text": "Fully invested. Take profit 50% at ARC 72, the rest at ARC 80."}


_DECISION_CACHE = {"day": None, "data": None}


@app.get("/api/ladder")
async def get_ladder():
    from datetime import datetime as _dtm
    today = _dtm.utcnow().date().isoformat()
    if _DECISION_CACHE["day"] == today and _DECISION_CACHE["data"]:
        return _DECISION_CACHE["data"]
    try:
        daily = await _full_daily_rows()
    except Exception as ex:
        raise HTTPException(503, f"price history unavailable: {ex}")
    dates, px, arc = _decision_series(daily)
    if len(px) < 400:
        raise HTTPException(503, "insufficient history")
    res = _run_ladder(dates, px, arc, start_i=0)
    cur_arc = arc[-1]
    zone = ("Deep Value" if cur_arc < 30 else "Accumulation" if cur_arc < 40
            else "Expansion" if cur_arc < 60 else "Risk Rising" if cur_arc < 70
            else "Euphoria")
    nxt = _next_step(res["alloc"], cur_arc)
    hodl_mult = round(px[-1] / px[0], 1)
    strat_mult = round(res["value"] / 10000.0, 1)
    # HODL max drawdown for the safety comparison
    _peak = 0.0; _hdd = 0.0
    for _p in px:
        if _p > _peak:
            _peak = _p
        if _peak > 0:
            _d = _p / _peak - 1.0
            if _d < _hdd:
                _hdd = _d
    data = {
        "asof": dates[-1],
        "arc": round(cur_arc, 1),
        "zone": zone,
        "invested_pct": res["invested_pct"],
        "next_step": nxt,
        "last_actions": res["actions"][-4:],
        "backtest": {
            "since": dates[0],
            "strategy_mult": strat_mult,
            "hodl_mult": hodl_mult,
            "trades": len(res["actions"]),
            "buy_years": len(sorted(set(a["date"][:4] for a in res["actions"]
                                        if a["type"] == "BUY"))),
            "max_dd": res.get("max_dd"),
            "hodl_max_dd": round(_hdd * 100, 1),
        },
        "rules": {
            "buy_40": "ARC \u2264 38 (or the cheapest 5% of the last 3 years)",
            "buy_100": "ARC \u2264 20 \u2014 or bottom confirmed (dips under 25, then back above)",
            "sell_all": "50% at ARC \u2265 72, the rest at ARC \u2265 80",
            "note": "Fixed rule, the same every cycle. Keeps buying even if the bottom never reaches 25 again.",
        },
    }
    # Fire a Telegram alert if the ladder just produced a new action (safe/no-op if unset)
    try:
        if res["actions"]:
            from alerts import check_and_fire_decision_alert
            await asyncio.to_thread(check_and_fire_decision_alert, res["actions"][-1], px[-1])
    except Exception as _e:
        logger.warning("decision alert hook failed: %s", _e)
    _DECISION_CACHE["day"] = today
    _DECISION_CACHE["data"] = data
    return data


_DEMO_CACHE = {"key": None, "data": None}


@app.get("/api/demo-account")
async def get_demo_account(start: str = "2026-01-01"):
    """Live demo account: runs the adaptive ladder from a cycle-bottom start date."""
    from datetime import datetime as _dtm
    key = f"{_dtm.utcnow().date().isoformat()}|{start}"
    if _DEMO_CACHE["key"] == key and _DEMO_CACHE["data"]:
        return _DEMO_CACHE["data"]
    try:
        daily = await _full_daily_rows()
    except Exception as ex:
        raise HTTPException(503, f"price history unavailable: {ex}")
    dates, px, arc = _decision_series(daily)
    if len(px) < 50:
        raise HTTPException(503, "insufficient history")
    start_i = 0
    for i, dd in enumerate(dates):
        if dd >= start:
            start_i = i
            break
    res = _run_ladder(dates, px, arc, start_i=start_i)
    start_px = px[start_i]
    cur_px = px[-1]
    cur_val = res["value"]
    hodl_val = round(10000.0 / start_px * cur_px, 2)
    # downsample series to ~120 points for the chart (incl. BTC price for hover)
    s = res["series"]
    step = max(1, len(s) // 120)
    chart = [{"date": s[j][0], "value": s[j][1], "hodl": s[j][2],
              "btc": round(px[start_i + j], 2)}
             for j in range(0, len(s), step)]
    if chart and chart[-1]["date"] != s[-1][0]:
        chart.append({"date": s[-1][0], "value": s[-1][1], "hodl": s[-1][2],
                      "btc": round(px[-1], 2)})
    data = {
        "start": dates[start_i],
        "start_price": round(start_px),
        "asof": dates[-1],
        "current_price": round(cur_px),
        "start_capital": 10000,
        "value": cur_val,
        "value_mult": round(cur_val / 10000.0, 2),
        "hodl_value": hodl_val,
        "hodl_mult": round(hodl_val / 10000.0, 2),
        "invested_pct": res["invested_pct"],
        "actions": res["actions"],
        "n_actions": len(res["actions"]),
        "chart": chart,
    }
    _DEMO_CACHE["key"] = key
    _DEMO_CACHE["data"] = data
    return data


_COMPHIST_CACHE = {"key": None, "data": None}


@app.get("/api/component-history")
async def get_component_history(days: int = 1300):
    """Daily 0-100 sub-scores of the 4 ARC components over the recent cycle,
    for the click-through charts on Engine 1. Same source as the live cards."""
    from datetime import datetime as _dtm
    key = f"{_dtm.utcnow().date().isoformat()}|{days}"
    if _COMPHIST_CACHE["key"] == key and _COMPHIST_CACHE["data"]:
        return _COMPHIST_CACHE["data"]
    try:
        rows = await _full_daily_rows()
    except Exception as ex:
        raise HTTPException(503, f"history unavailable: {ex}")
    rows = [r for r in (rows or []) if r.get("price")]
    rows.sort(key=lambda r: r["date"])
    if not rows:
        raise HTTPException(503, "no history")
    rows = rows[-days:] if len(rows) > days else rows

    def col(k, alt=None):
        out = []
        for r in rows:
            v = r.get(k)
            if v is None and alt is not None:
                v = r.get(alt)
            out.append(round(float(v), 1) if v is not None else None)
        return out

    data = {
        "asof": rows[-1]["date"][:10],
        "dates": [r["date"][:10] for r in rows],
        "price": [round(float(r["price"]), 2) for r in rows],
        "components": {
            "trend":     {"label": "Trend (Price vs 200-week MA)", "series": col("c_trend")},
            "drawdown":  {"label": "Drawdown from ATH",            "series": col("c_drawdown")},
            "sentiment": {"label": "Sentiment (Fear & Greed)",     "series": col("c_sentiment")},
            "liquidity": {"label": "Liquidity (Fed net liquidity)","series": col("c_liquidity"),
                          "abs": col("c_liq_abs"), "abs_label": "Fed net liquidity ($T)", "abs_unit": "T"},
        },
        "note": "0-100 score per component; higher = more risk. Same scoring as the ARC Index.",
    }
    _COMPHIST_CACHE["key"] = key
    _COMPHIST_CACHE["data"] = data
    return data


@app.get("/api/daily-telegram-test")
async def daily_telegram_test(token: str = ""):
    """Manual trigger to fire the daily Telegram summary now (ADMIN_TOKEN gated)."""
    import os as _os
    if token != _os.getenv("ADMIN_TOKEN", "alphacycle-admin"):
        raise HTTPException(403, "forbidden")
    text = await _compose_daily_telegram()
    sent = await _send_daily_telegram()
    return {"sent": bool(sent), "preview": text}


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

