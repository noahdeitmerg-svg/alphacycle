# AlphaCycle — Deploy State
**Zuletzt aktualisiert:** 2026-03-04
**Aktuelle Version:** live auf Railway (alphacycle-production.up.railway.app)

## Letzter Session-Status (2026-03-04) — VOLLSTÄNDIG DEPLOYED
- ✅ FIX 1: /api/arc-summary Endpoint ergänzt
- ✅ FIX 2: /api/prices mit ATH + Dominanz (Kraken-basiert)
- ✅ FIX 3: backtest_engine.py auf Kraken OHLC umgestellt (CoinGecko-Reste entfernt)
- ✅ FIX 4: index.html ATH/Dominanz aus /api/prices (kein CoinGecko mehr)
- ✅ FIX 5: index.html backtest + liquidity-regime in Promise.allSettled + liquidity-components
- ✅ FIX 6: scoring.py short_term dict in compute_btc_score()
- ✅ FIX 37: backend/Dockerfile — eine Datei, CMD mit $PORT, workers=1; Duplikat entfernt
- ✅ FIX 38: fetcher.py Funding Rates OKX (Bybit/Binance 403 auf Railway); fetch_funding_rates mit if-blocks
- ✅ Deployed auf Railway, getestet — Dashboard live bei Score 30/100

## Nächste Schritte
- [ ] X Content für AlphaCycle erstellen
- [ ] Paid SaaS Funnel planen



## Architecture Lock (NEVER change without architect approval)
ARC Formula: ma_200w*0.30 + drawdown*0.25 + fear_greed*0.20 + liquidity*0.25
DO NOT modify weights. DO NOT add scoring components.

## Permanent Fixes (never revert)
1. main.py: All Unicode removed from comments AND string literals
2. main.py: CycleAnalyzer imported + /api/analyzer endpoint active
3. main.py: /api/arc-summary endpoint active
4. fetcher.py: Kraken primary price source (Binance blocked Railway US-West)
5. scoring.py: drawdown_score() returns 50.0 if len(prices) < 10
6. index.html: BACKEND_URL = https://alphacycle-production.up.railway.app
7. index.html: Promise.allSettled (NOT Promise.all)
8. index.html: phaseOf() boundaries: <30 Low Risk, <61 Moderate Risk, <81 Elevated Risk
9. index.html: S.btcShortTerm = btcC?.short_term || null (after btcComponents)
10. index.html: S.ethComponents = ethC?.components || null (after btcShortTerm)
11. index.html: S.btcScore guard: only use API value if btcC.score > 0
12. main.py: short_term exposed in /api/cycle/btc response
13. main.py: /api/arc-summary endpoint active
14. main.py: BTC/ETH ATH computed from Kraken price history (max of btc_prices)
15. backtest_engine.py: Uses Kraken OHLC (not CoinGecko)
16. index.html: CoinGecko direct calls removed — all data via Railway backend
17. index.html: updatePhaseBanner() uses phaseOf() only — analyzerPhase override removed
18. index.html: hero card has single risk label (btc-tag removed, hero-risk-label kept)
19. index.html: change_24h computed from last 2 history points (Kraken has no 24h change)
20. index.html: /api/backtest and /api/liquidity-regime fetched in Promise.allSettled
21. scoring.py: short_term dict in compute_btc_score() return (rsi, funding, mvrv, power_law, pi_cycle, puell)
22. main.py: arc-summary components.liquidity nutzt macro_liq (nicht liquidity)
23. scoring.py: macro_liq uses 52w window + pct*2.5 amplification (not plain trend_score for WALCL)
24. index.html: Data Inspector panel at bottom (before footer), SHOW/HIDE toggle, renders from S.*; values 0/null orange, 50 default yellow
25. index.html: Data Inspector ARC Summary Liquidity — numeric from S.arcSummary?.components?.liquidity (or .score if object); never display [object Object]
26. main.py: arc-summary regime/decision fallbacks: regime = mac.get("regime","NEUTRAL") or "NEUTRAL", decision = com.get("signal","HOLD") or "HOLD"
27. fetcher.py: merge() BTC/ETH market_cap fallback when 0 — use price * 19_700_000 (approx circulating supply)
28. index.html: /api/arc-summary in Promise.allSettled, S.arcSummary stored; Data Inspector uses S.arcSummary for Regime, Decision, Confidence
29. index.html: Data Inspector all scores rounded to 1 decimal (roundScore / Math.round(x*10)/10) — no floating point display (e.g. 34.135000000005)
30. fetcher.py: after merge(), if gdata.btc_dominance == 50.0 and btc_market.market_cap + total_market_cap > 0, set gdata["btc_dominance"] = round(btc_mc/total_mc*100, 1)
31. index.html: Data Inspector Funding Rate — when 0 or null show "N/A (Binance blocked)" instead of "0.0000%"
32. scoring.py: compute_combined() returns signal + confidence; compute_macro_score() returns regime (EXPANSION/NEUTRAL/CONTRACTION)
33. index.html: Data Inspector ARC Score = Math.round((S.combined ?? 50) * 10) / 10; Funding formatter fmtFunding → "N/A" when 0/null
34. fetcher.py: Funding Rates von Binance auf Bybit umgestellt (Binance Futures auf Railway blockiert)
35. index.html: Data Inspector Liquidity Regime/ARC Summary — liq.liquidity_regime und liq.liquidity_score (NICHT liq.regime / liq.score)
36. liquidity_engine.py: bond_score aus absolutem 10Y-Yield-Niveau berechnen, nicht aus trend_score (Bug: us10y_trend=0 → 100)
37. backend/Dockerfile: Nur eine Dockerfile im backend/ (keine Datei mit Leerzeichen); CMD mit $PORT (nicht hardcoded 8000)
38. fetcher.py: Funding Rates von OKX (Binance Futures und Bybit 403 auf Railway) — fetch_funding_rates() nutzt okx.com/api/v5/public/funding-rate
39. fetcher.py: Global data (btc_dominance, total_market_cap) via CoinCap — CoinGecko /global gibt 429
40. index.html: FRED-Label dynamisch — src-fred je nach S.walclCurrent: FRED oder FRED (synthetic fallback) + class status-src / warn
41. fetcher.py: btc_dominance hardcoded 55.0, total_market_cap 0 — alle externen APIs (CoinGecko 429, CoinCap/Bybit/Binance) auf Railway US-West blockiert. index.html: Data Inspector ohne diRow BTC Dominance / Total Market Cap / BTC Dominance %
42. backtest_engine.py: Paginated Kraken OHLC (max 720/request), ARC = ma_200w*0.35 + drawdown*0.35 + fg(50)*0.15 + liq(50)*0.15. Return {date, price, score}. index.html: ARC History Chart (arc-history-chart) mit Chart.js, S.backtest, Risk-Zonen als fill, Placeholder "Lade historische Daten...".
43. backtest_engine.py: File cache /tmp/backtest_cache.json; einmal 10y laden, taeglich 1-2 fehlende Tage nachladen. WINDOW_200W=200.

## Active Endpoints (Railway)
/health /api/prices /api/cycle/btc /api/cycle/eth /api/cycle/macro
/api/arc-summary /api/cycle/combined /api/history /api/fear-greed
/api/cycle-anchor /api/analyzer /api/backtest /api/liquidity-regime /api/decision

## Frontend Sections (in order)
1. Hero: ARC Index (btc-card with hero-card class)
2. Decision Engine card
3. Short Term Tactical Layer card
4. Cycle Anchor card
5. Sub-Analysis: ETH Relative Strength + Liquidity Regime
6. Phase Banner, Key Indicators, Live Prices, Cycle Phase Guide
7. Data Inspector (collapsed by default, SHOW/HIDE toggle)

## Data Sources
Prices: Kraken (primary), CoinGecko (fallback)
Global/dominance: hardcoded 55% (APIs blockiert auf Railway)
Funding: OKX (Binance Futures + Bybit 403 auf Railway)
F&G: Alternative.me
TVL+Stablecoins: DeFiLlama
Fed Balance: FRED
