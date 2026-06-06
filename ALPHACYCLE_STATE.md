# AlphaCycle — Master Status (Launch-Ready)

> Single source of truth. Last updated by the autonomous build pass. Everything below is **live on alphacycle.app** unless marked "Noah to do".

## The core value (the thing that sells)
A transparent 0–100 Bitcoin cycle score (ARC) **plus a backtested rule that beat HODL ~4×**:

> **All-in at ARC ≤ 25 · all-out at ARC ≥ 75 · hold the middle.**
> $10,000 since Aug 2017 → **$711,000 (71×)** vs **$142,000 (14×)** for buy-and-hold, at **−36% max drawdown instead of −84%**. 6 trades in 9 years. Robust across a wide threshold range (not one magic number). In-sample backtest on daily OHLC; past performance ≠ future results.

This proof now leads both the **landing page** and the **dashboard**.

## ARC formula (LOCKED — do not change without version bump)
`ma_200w×0.35 + drawdown×0.30 + liquidity×0.15 + fear_greed×0.20` (v1.2). Zones: Deep Value <30, Accumulation <40, Expansion <60, Risk Rising <70, Euphoria ≥70. Source of truth: `backend/arc_config.py`. Backtest uses daily high/low for trend & drawdown (verified — not weekly closes). ARC peaks *before* the final price top (liquidity/sentiment cool), which is correct and helps the sell signal fire early.

## Dashboard engines (live at /app)
1. **Hero gauge** — live ARC, zone, plain-English read.
2. **Engine 1 · Composite** — the 4 weighted signals (trend 35 / drawdown 30 / sentiment 20 / liquidity 15).
3. **Engine 2 · Decision** — *the clear rule*. Shows live action (BUY ALL-IN / HOLD / SELL) from the current ARC, with "X to go" to the next trigger, the 3-band rule, and the backtest result.
4. **THE PROOF** — ARC vs HODL equity chart + headline stats ($711k vs $142k).
5. **Engine 3 · Track Record** — 12M forward return per zone (Deep Value +236% 100% win, Accumulation +220% 100% win, Euphoria −48% avg drawdown).
6. **Engine 4 · Cycle Clock** — phase, days since top, drawdown, percentile.
7. **Engine 5 · Near-Term** — short-term oscillators (contextual).
8. **Engine 6 · Cycle Wave** — Seasonax-style dominant-cycle overlay: a best-fit sine (detected dominant cycle) laid over the real BTC/ETH price and projected forward, showing whether we're **rising or falling** in the cycle now + the **next turn** (peak/trough) date and the cycle length + fit strength. BTC/ETH toggle. Source: `/api/cycle-wave` (pure-python sine fit on log-detrended price, day-cached). A detected rhythm for timing, NOT a price prediction — fit strength shown for honesty.
8b. **Engine 6B · Seasonality** — simple 4-card read (same design as the other engines): Halving-cycle month + phase, strongest month, weakest month, next-90-day lean. **Confidence-gated**: a month shows only if up or down in ≥70% of years (currently Oct up 77%, Aug down 83%); next-90d shows a lean only when statistically unlikely to be chance, else "No edge". Weekly checked → noise. Source: `/api/seasonality` (full daily history back to 2013, day-cached). Context, not a trade signal.
8c. **Engine 6C · Cycle Extremes** — simple 3-card read: **Pi Cycle Top** (111d vs 2×350d — empirically the best top-marker, hit 2017 & 2021 tops within 1–2 days; did NOT fire this muted post-ETF cycle, currently +157% away), **Mayer Multiple** (price/200d, 0.78× = undervalued), **200-week MA** (price on the bear-market floor). All point to the value end, matching ARC. Source: `/api/cycle-signals` (day-cached). Context, not a trade signal.
9. **Engine 7 · 10-Year Chart** — ARC + BTC since 2017, zone bands, TOP/BOTTOM/NOW markers on the ARC line. **Interactions:** scroll chart = zoom time, scroll price axis = zoom price only (DexScreener/TV style, custom handler), drag = pan all directions, click legend to toggle lines + each zone, fullscreen button, 1Y/10Y/reset.
10. **Engine 8 · Regime Timeline** — dated log of every zone change with the stance it implied (ACCUMULATE/HOLD/REDUCE/TAKE PROFIT). No misleading return number — it's the live signal log.

## Landing page (live at /)
Hero → **proof stat bar (71× / 5.0× / −36%)** → **The Proof section** with equity chart → Problem/Solution → Features → How → Pricing (Free + Pro $29) → FAQ (incl. "beats HODL?") → CTA. Legal: /privacy /terms /disclaimer (Brazil/LGPD).

## Backend
FastAPI on Railway. Endpoints: `/api/arc-summary`, `/api/backtest`, `/api/historical-returns`, `/api/zone-history`, `/api/seasonality`, `/api/track` + `/api/stats` (funnel analytics → see **/stats.html**), `/api/checkout`, `/api/create-portal-session`, `/api/stripe-webhook`. Regime-change **alert engine** built (`backend/alerts.py`) — posts to Telegram on zone flips; hooked into the refresh loop; email hook stubbed.

## Noah to do (to take money + fire alerts) — see GO_LIVE_NOAH.md
1. **Supabase** tables (SQL in GO_LIVE_NOAH.md) — fixes signup capture.
2. **Stripe** live keys + products + webhook in Railway env (`STRIPE_SECRET_KEY`, `STRIPE_WEBHOOK_SECRET`, `STRIPE_PRICE_MONTHLY`, `STRIPE_PRICE_YEARLY`).
3. **Auth** (your domain) — then wire "Go Pro" → `/api/checkout` and the soft gates to the real plan check.
4. **Telegram** — create channel, bot token + `TELEGRAM_ALERT_CHANNEL_ID` in Railway.

## Marketing kit (local files in the project folder)
- `FUNNEL_PLAN.md` — path to $3k MRR, low-effort faceless content + ElevenLabs.
- `FLOW_30_PROMPTS_READY.md` — 60 ready Veo prompts (2× 8s per reel, all branded).
- `FLOW_CHARACTER.md` — consistent character block. `FLOW_GUIDE.md` — Flow how-to.
- `social/` — 20 branded graphics (Score Card, Carousels A/B/C). `AlphaCycle_ARC_vs_HODL.png` — the backtest chart.
- `AlphaCycle_Reel_v1/v2.mp4` — reel templates.

## Honest notes
- The backtest is in-sample; the README/landing/FAQ all state "past performance ≠ future results."
- Veo character+voice consistency across many clips is unreliable → funnel recommends **faceless + one ElevenLabs voice** as the scalable path.
- Gates are currently open (build phase); re-enable + tie to auth when ready.
