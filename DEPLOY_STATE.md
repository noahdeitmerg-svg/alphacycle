# AlphaCycle — Deploy State
**Zuletzt aktualisiert:** 2026-03-04
**Aktuelle Version:** live auf Railway (alphacycle-production.up.railway.app)

## Letzter Session-Status (2026-03-04) — VOLLSTÄNDIG DEPLOYED
- ✅ ARC Formula Unification: scoring.compute_arc_score() (ma*0.35 + dd*0.25 + liq*0.25 + fg*0.15), backtest_engine same weights + fg_to_score, /api/arc-summary uses compute_arc_score()
- ✅ **ARC v2**: Percentile-Rescaling (HISTORICAL_ARC_MIN 22 / HISTORICAL_ARC_MAX 78.5), rescale_arc() in scoring.py; compute_arc_score() returns rescale_arc(clamp(arc)). Momentum from backtest: scoring.compute_arc_momentum(arc_history, days=30); /api/arc-summary exposes arc_momentum (value, label, direction), arc_momentum_30d, arc_momentum_label; percentile from analyzer.
- ✅ **ARC v2 Nachfixes**: backtest_engine run_backtest() wendet rescale_arc(arc) nach clamp an; /api/backtest liefert rescaled ARC (0-100). Expected Range in main.py _get_expected_range() feste Lookup-Tabelle fuer rescaled ARC (0-100), avg_12m hard cap 300%.
- ✅ **Cycle Anchor Bear-Phase**: compute_cycle_anchor() phase-aware (today >= TENTATIVE_CYCLE_TOP → BEAR), cycle_position_percent from bear_progress/bull_progress; return current_phase, phase_label, phase_description, bear_progress_percent.
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
ARC Formula (unified, research-validated): ma_200w*0.35 + drawdown*0.25 + liquidity*0.25 + fear_greed*0.15
Use fg_to_score(fear_greed) for F&G input. Same formula in scoring.compute_arc_score(), backtest_engine, and /api/arc-summary.
DO NOT modify weights. DO NOT add scoring components.
**ARC v2 output**: compute_arc_score() returns rescale_arc(clamp(arc)); rescale_arc maps empirical 22–78.5 to 0–100 with 50 neutral. Momentum from backtest via scoring.compute_arc_momentum(arc_history, days=30).

## Permanent Fixes (never revert)
1. main.py: All Unicode removed from comments AND string literals
2. main.py: CycleAnalyzer imported + /api/analyzer endpoint active
3. main.py: /api/arc-summary endpoint active
4. fetcher.py: Kraken primary price source (Binance blocked Railway US-West)
5. scoring.py: drawdown_score() returns 50.0 if len(prices) < 10
6. index.html: BACKEND_URL = https://alphacycle-production.up.railway.app
7. index.html: Promise.allSettled (NOT Promise.all)
8. index.html: phaseOf() boundaries: <30 Low Risk, <60 Moderate Risk, <75 Elevated Risk
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
43. backtest_engine.py: File cache /tmp/backtest_cache.json; einmal 10y laden, taeglich 1-2 fehlende Tage nachladen.
44. backtest_engine.py: WINDOW_200W=1400, HTTP_TIMEOUT=60, Cache min 2000, Fetch 5200d, Abbruch len(candles)<10. index.html Chart UX: yPrice dynamisch skaliert (validPrices 0.88/1.08), Tooltip nur ARC Index + BTC Price.
45. fetcher.py: CoinGecko fetch_market_data aus fetch_all() entfernt (429 auf Railway). asyncio.gather nur noch 11 Aufrufe (0: Kraken BTC/ETH prices+ticker, 4: F&G, 5: TVL, 6: stable, 7: WALCL, 8: DGS10, 9: global_data, 10: funding). btc_cg/eth_cg = leere Fallback-Dicts. Spart ~3s pro Refresh.
46. backtest_engine.py: _fetch_btc_history() since=1381363200 (2013-10-10, Kraken BTC live); bei Kraken OHLC error/kein result Logging; _load_or_build_cache() Exception loggen statt pass.
47. fetcher.py: FRED Net Liquidity (WALCL - WTREGEN - RRPONTSYD). fetch_all() gather 13 Aufrufe: 11/12 fetch_fred_series("WTREGEN") und ("RRPONTSYD"). _compute_net_liquidity(); return net_liq_series, tga_series, rrp_series.
48. scoring.py: macro_liq aus Net Liquidity (net_liq_values). compute_btc_score(net_liq_values=None); 52w Fenster, pct*2.0; Fallback WALCL (pct*2.5). main.py: net_liq_series an compute_btc_score übergeben (data.get("net_liq_series", []) im Cache-Refresh).
49. backtest_engine.py: Net Liquidity im Backtest. _fetch_fred(series_id) lädt WALCL/WTREGEN/RRPONTSYD ab 2013-01-01; net_liq_by_date = WALCL - TGA - RRP; _get_net_liq_score(date_str, net_liq_by_date) für 52w-Trend (50 - pct*2.0). macro_liq pro Tag dynamisch, Fallback 50.0.
50. backtest_engine.py: Kraken OHLC weekly (interval=10080) — Daily max 720 Tage API-Grenze. 720 Wochen = ~13.8 Jahre. WINDOW_200W=200 (200 wöchentliche Punkte = 200-Wochen MA). since=1381363200 (2013-10-10). Cache min 400 Einträge. Ergebnis ~520 ARC-Punkte = ~10 Jahre Chart ab ~2014.
51. index.html: Data Inspector nach WALCL-Zeile: Net Liquidity (S.arcSummary?.components?.net_liq, $XB), TGA (S.arcSummary?.components?.tga, $XB), Macro Liq Score (S.arcSummary?.components?.liquidity, roundScore).
52. fetcher.py: fetch_fred_series() Logging (FRED series_id: len pts). WTREGEN/RRPONTSYD mit start="2015-01-01". main.py /api/arc-summary: components.net_liq + components.tga aus raw (net_liq_series/tga_series letzter Wert) fuer Data Inspector.
53. backtest_engine.py: F&G im Backtest: _fetch_fg_history() (limit=0, alle Daten ab 2018), Mapping {date_str: value}. _rsi_to_fg() als RSI-Proxy für Perioden ohne echte F&G-Werte (Aug 2017–Feb 2018). In run_backtest() pro Tag: fear_greed = fg_history[date] oder _rsi_to_fg(prices_so_far); ARC-Gewicht weiterhin 15%.
54. index.html: ARC History Chart Export (PNG). Button „↓ EXPORT PNG“ unter dem ARC-Chart (arc-history-chart). exportArcChart(): 1200x675 Canvas, Hintergrund #0D1117, Chart-Canvas als Bild (volle Höhe), kein Footer mehr; Download als alphacycle-arc-YYYY-MM-DD.png; Button im Monospace-Style (DM Mono) an Dashboard-Design angepasst.
55. main.py: Daily Snapshot System. /api/snapshot/today speichert aktuellen ARC Snapshot in /tmp/arc_snapshots.json (date, arc, btc_price, regime, liquidity, fear_greed, decision, confidence) und gibt ihn zurück. /api/snapshots liefert alle Snapshots. Nach erfolgreichem Cache-Refresh wird _save_today_snapshot() automatisch aufgerufen.
56. index.html: Mobile Responsive Dashboard. @media (max-width: 768px): dashboard/cards/scores/metrics auf 1 Spalte, kleinere Hero-Padding, ARC-Chart-Container für Mobile. ARC Chart (Chart.js) mit maintainAspectRatio: false. Boot-Screen Text „CONNECTING TO KRAKEN…“ (statt COINGECKO).
57. index.html: ARC Chart Resize-Hotfix. Fester Container #arc-chart-wrap (Desktop: height 420px, width 100%), Canvas #arc-history-chart absolut (width/height 100%). Auf Mobile (max-width:768px) #arc-chart-wrap height 280px. In Kombination mit responsive:true + maintainAspectRatio:false verhindert dies unendliches Wachstum beim Scroll/Resize.
58. index.html: Hero Gauge + Liquidity Fix. Hero-Gauge nutzt kombinierten ARC Score (S.combined ?? S.arcSummary?.arc_score ?? S.btcScore) für Farbe, Gauge-Animation und Wert. BTC Liquidity-Component-Bar liest primär S.arcSummary?.components?.liquidity, dann btcComponents.macro_liq (.score oder Wert), fallback 50; kein harter 50er-Default mehr bei vorhandenen Net-Liq-Daten.
59. index.html: ARC History Cycle Marker. Hardcodierte CYCLE_MARKERS-Liste mit Top-/Bottom-Daten (2017-12-17, 2021-11-10, 2018-12-15, 2022-11-21). Chart.js inline Plugin `cycleMarkers` im ARC History Chart (options.plugins.cycleMarkers.afterDraw) zeichnet Dreiecksmarker auf der BTC-Preisachse (rot für Tops, grün für Bottoms) und Label „Cycle Top“ / „Cycle Bottom“ direkt im Chart; Marker-Liste kann später erweitert werden.
60. index.html: AlphaCycle Logo Integration. Favicon im <head> zeigt auf `/static/logo.png` (PNG). Nav-Bar Logo nutzt `<img src="/static/logo.png" alt="AlphaCycle" style="width:32px;height:32px;border-radius:6px;object-fit:contain;">` anstelle des generischen "α"-Marks; erwarteter Auslieferungspfad über backend/static/logo.png auf Railway.
61. ARC Formula Unification: Single formula ma_200w*0.35 + drawdown*0.25 + liquidity*0.25 + fear_greed*0.15. scoring.compute_arc_score() (same liquidity logic as compute_btc_score; compute_btc_score unchanged). backtest_engine: fg_to_score(fear_greed), weights ma*0.35 + dd*0.25 + macro_liq*0.25 + fg*0.15. main.py /api/arc-summary: arc_score from compute_arc_score(), not combined_score.
62. Cycle Anchor Cleanup: TENTATIVE_CYCLE_TOP = date(2025, 10, 6) (BTC ATH ~$126,200) in cycle_anchor.py only. main/analyzer import from cycle_anchor. API returns cycle_top_date (isoformat) and cycle_top_confirmed: False.
63. **ARC v2 rescaling**: scoring.py HISTORICAL_ARC_MIN=22.0, HISTORICAL_ARC_MAX=78.5; rescale_arc(raw_arc) maps 22–50→0–50, 50–78.5→50–100; compute_arc_score() returns rescale_arc(clamp(arc)). Weights unchanged.
64. **ARC momentum layer**: scoring.compute_arc_momentum(arc_history, days=30) returns {value, label, direction}. /api/arc-summary: arc_history from backtest; arc_momentum = full dict; arc_momentum_30d = momentum["value"]; arc_momentum_label = momentum["label"]; arc_percentile/arc_percentile_label from analyzer.
65. **Cycle Anchor Bear-Phase**: compute_cycle_anchor() if today >= TENTATIVE_CYCLE_TOP then current_phase=BEAR, cycle_position_percent from bear_progress; else BULL from bull_progress. Return: current_phase, phase_label, phase_description, bear_progress_percent (0 in BULL).
66. **Backtest rescale_arc**: backtest_engine.py import rescale_arc from scoring; after arc = max(0, min(100, arc)) apply arc = rescale_arc(arc) before results.append. /api/backtest results use rescaled ARC (0-100).
67. **Expected Range Kalibrierung**: main.py _get_expected_range(arc, forward_returns) uses fixed lookup for rescaled ARC (0-100): bands <10, <25, <40, <55, <70, >=70 with range_low/range_high and avg_12m; avg_12m hard cap 300%.

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
Prices: Kraken (primary). CoinGecko fetch_market_data entfernt (429 auf Railway); btc_cg/eth_cg = leere Fallbacks.
Global/dominance: hardcoded 55% (APIs blockiert auf Railway)
Funding: OKX (Binance Futures + Bybit 403 auf Railway)
F&G: Alternative.me
TVL+Stablecoins: DeFiLlama
Fed Balance: FRED (WALCL, DGS10, WTREGEN, RRPONTSYD). Net Liquidity = WALCL - TGA - RRP.
