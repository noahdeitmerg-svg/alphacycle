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
Funding: Binance Futures
F&G: Alternative.me
TVL+Stablecoins: DeFiLlama
Fed Balance: FRED
