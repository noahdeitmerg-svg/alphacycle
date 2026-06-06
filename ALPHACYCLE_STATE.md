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
8. **Engine 6 · Market Context** — ETH/BTC rotation, seasonality, Fed liquidity.
8b. **Engine 6B · Seasonality** — computed live from full daily history (back to 2013): **Halving Clock** (months-since-halving + avg-cycle path vs this cycle), **Monthly Edge** (avg return + win rate per calendar month — Oct +18.9% strongest, Jun/Aug/Sep weakest), **Next-90-days weekly seasonal path** (compounded week-of-year averages), and a **Year×Month heatmap**. Source: `/api/seasonality` (day-cached). Framed as context, not a trade signal.
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
