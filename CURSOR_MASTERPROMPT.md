# AlphaCycle — Cursor Masterprompt
> Lies diesen Prompt vollständig bevor du irgendetwas änderst.

---

## Was ist AlphaCycle?
AlphaCycle ist ein Crypto Cycle Intelligence SaaS Dashboard.
- **Backend:** FastAPI auf Railway (`alphacycle-production.up.railway.app`)
- **Frontend:** `index.html` (statisch, auf Netlify oder direkt)
- **Stack:** Python 3.12, FastAPI, Gunicorn + Uvicorn Workers
- **Repo:** `C:\Users\noahd\Documents\Cursor AlphaCycle\alphacycle-main`
- **GitHub:** `https://github.com/noahdeitmerg-svg/alphacycle`
- **Deploy:** Git Push → Railway auto-deploy

---

## Workflow — IMMER einhalten

### Vor jeder Änderung:
1. `DEPLOY_STATE.md` lesen (im Repo-Root)
2. `.cursor/rules/permanent-fixes.mdc` lesen
3. Alle dort dokumentierten Fixes einhalten — NIEMALS rückgängig machen

### Nach jeder Änderung:
1. `DEPLOY_STATE.md` updaten (neue Fixes dokumentieren)
2. `.cursor/rules/permanent-fixes.mdc` updaten
3. Dann deployen:
```bash
git add .
git commit -m "fix: was geändert wurde"
git push
```

---

## Projektstruktur
```
alphacycle-main/
├── backend/
│   ├── Dockerfile          ← NUR diese eine Datei, kein " Dockerfile" mit Leerzeichen
│   ├── main.py             ← FastAPI Endpoints
│   ├── fetcher.py          ← Alle externen API calls
│   ├── scoring.py          ← Scoring Algorithmen
│   ├── liquidity_engine.py ← Liquidity Regime Engine
│   ├── analyzer.py         ← CycleAnalyzer
│   ├── decision_engine.py  ← Decision Engine
│   ├── cycle_anchor.py     ← Cycle Anchor
│   ├── requirements.txt
│   └── services/
│       └── backtest_engine.py
├── index.html              ← Frontend (Single File)
└── DEPLOY_STATE.md         ← Deployment Status (IMMER aktuell halten)
```

---

## Architektur — LOCKED (nie ohne Genehmigung ändern)

### ARC Index Formel:
```
ma_200w * 0.30 + drawdown * 0.25 + fear_greed * 0.20 + liquidity * 0.25
```
**Gewichte NIEMALS ändern.**

### Scoring Range: 0–100 (niedrig = bullish, hoch = bearish)

### Phase Grenzen (phaseOf in index.html):
- < 30 → Low Risk
- < 61 → Moderate Risk
- < 81 → Elevated Risk
- ≥ 81 → Extreme Risk

---

## Permanent Fixes — NIEMALS rückgängig machen

### backend/fetcher.py
- **Kraken ist primäre Preisquelle** (Binance Spot blockiert auf Railway US-West)
- `fetch_all()` gather Reihenfolge: `fetch_kraken_prices("XBTUSD")`, `fetch_kraken_prices("XETHZUSD")`, `fetch_kraken_ticker("XBTUSD")`, `fetch_kraken_ticker("XETHZUSD")` — Indizes 0-3
- **OKX für Funding Rates** (Binance Futures UND Bybit beide 403 auf Railway):
```python
async def fetch_funding_rates():
    try:
        btc = await _get("https://www.okx.com/api/v5/public/funding-rate", params={"instId": "BTC-USDT-SWAP"})
        eth = await _get("https://www.okx.com/api/v5/public/funding-rate", params={"instId": "ETH-USDT-SWAP"})
        btc_rate = round(_sf(btc["data"][0].get("fundingRate", 0)) * 100, 4) if btc and btc.get("data") else 0.0
        eth_rate = round(_sf(eth["data"][0].get("fundingRate", 0)) * 100, 4) if eth and eth.get("data") else 0.0
        return {"btc_funding_rate": btc_rate, "eth_funding_rate": eth_rate}
    except Exception as e:
        logger.warning(f"Funding rates (OKX): {e}")
        return {"btc_funding_rate": 0.0, "eth_funding_rate": 0.0}
```
- `merge()`: BTC market_cap Fallback wenn 0 → `price * 19_700_000`
- Nach `merge()`: btc_dominance Fallback wenn 50.0 → berechne aus `btc_market_cap / total_market_cap`

### backend/scoring.py
- `drawdown_score()`: Guard `if len(clean) < 10: return 50.0`
- `compute_btc_score()`: IMMER `short_term` dict zurückgeben (rsi, funding, mvrv, power_law, pi_cycle, puell)
- `macro_liq`: 52-Wochen-Fenster + pct*2.5 Amplification (`50 - pct*2.5`, clamped) — NICHT plain trend_score
- `compute_macro_score()`: IMMER `regime` Key zurückgeben (EXPANSION/NEUTRAL/CONTRACTION)
- `compute_combined()`: IMMER `signal` + `confidence` Keys zurückgeben

### backend/main.py
- Kein Unicode in Kommentaren oder Strings (═ ─ — → ™ …)
- `/api/arc-summary` Endpoint aktiv
- `/api/analyzer` Endpoint aktiv
- `arc-summary components.liquidity`: `btc.get("macro_liq", 50.0)` — NICHT `btc.get("liquidity")`
- `regime = mac.get("regime", "NEUTRAL") or "NEUTRAL"`
- `decision = com.get("signal", "HOLD") or "HOLD"`

### backend/liquidity_engine.py
- `bond_score` aus absolutem 10Y-Yield-Niveau berechnen (nicht aus trend_score):
  - < 2% → 20.0
  - 2-3% → clamp(20 + (yield-2)*30)
  - 3-4% → clamp(50 + (yield-3)*20)
  - 4-5% → clamp(70 + (yield-4)*15)
  - ≥ 5% → clamp(85 + (yield-5)*5)
- Return Keys: `liquidity_regime`, `liquidity_score` (NICHT `regime`, `score`)

### backend/Dockerfile
- NUR eine Dockerfile im `backend/` Ordner (keine Datei mit Leerzeichen im Namen)
- CMD mit `$PORT` (NICHT hardcoded 8000):
```dockerfile
FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
CMD gunicorn main:app --workers 1 --worker-class uvicorn.workers.UvicornWorker --bind 0.0.0.0:$PORT --timeout 120 --access-logfile -
```

### index.html
- `BACKEND_URL = 'https://alphacycle-production.up.railway.app'`
- `Promise.allSettled` (NICHT Promise.all)
- `S.btcShortTerm = btcC?.short_term || null` nach btcComponents
- `S.ethComponents = ethC?.components || null`
- `S.btcScore`: nur API-Wert wenn `btcC.score > 0`, sonst Fallback
- Data Inspector: IMMER am Ende der Seite, SHOW/HIDE Toggle, collapsed by default
- Data Inspector Scores: `roundScore(v)` = `Math.round(Number(v) * 10) / 10`
- Data Inspector Funding: `fmtFunding` → "N/A (Binance blocked)" wenn 0 oder null
- Data Inspector Liquidity Regime: `liq.liquidity_regime` und `liq.liquidity_score` (NICHT liq.regime / liq.score)
- CoinGecko direkte Calls im Frontend: KEINE — alles über Railway Backend

---

## Aktuelle offene Fixes (sofort umsetzen)

### FIX 1 — backend/Dockerfile: Duplikat entfernen
Im `backend/` Ordner gibt es 2 Dateien:
- `" Dockerfile"` (mit Leerzeichen, 255 bytes) — korrektes CMD mit $PORT
- `"Dockerfile"` (434 bytes) — altes CMD mit Port 8000 hardcoded

**Lösung:** Lösche `"Dockerfile"` (434 bytes). Benenne `" Dockerfile"` um zu `"Dockerfile"`.
Inhalt soll sein:
```dockerfile
FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
CMD gunicorn main:app --workers 1 --worker-class uvicorn.workers.UvicornWorker --bind 0.0.0.0:$PORT --timeout 120 --access-logfile -
```

### FIX 2 — backend/fetcher.py: OKX Funding Rates
Ersetze `fetch_funding_rates()` komplett mit OKX Version (siehe Permanent Fixes oben).
Bybit gibt 403 auf Railway — genau wie Binance.

### FIX 3 — DEPLOY_STATE.md + permanent-fixes.mdc updaten
Nach FIX 1 und FIX 2:
- DEPLOY_STATE.md: Fixes 37-38 ergänzen
- permanent-fixes.mdc: OKX Funding + Dockerfile Regel ergänzen

---

## Datenquellen
| Quelle | Was | Status |
|--------|-----|--------|
| Kraken | BTC/ETH Preise + Ticker | ✅ funktioniert |
| OKX | Funding Rates | 🔄 zu implementieren |
| Alternative.me | Fear & Greed | ✅ funktioniert |
| DeFiLlama | TVL + Stablecoins | ✅ funktioniert |
| FRED | WALCL + 10Y Yield | ✅ funktioniert |
| CoinGecko | Market Cap, Global Data | ⚠️ 429 Rate Limit (Fallback aktiv) |
| Binance Futures | Funding (ALT) | ❌ 403 auf Railway |
| Bybit | Funding (ALT) | ❌ 403 auf Railway |

---

## Active Endpoints
```
/health
/api/prices
/api/cycle/btc
/api/cycle/eth
/api/cycle/macro
/api/arc-summary
/api/cycle/combined
/api/history
/api/fear-greed
/api/cycle-anchor
/api/analyzer
/api/backtest
/api/liquidity-regime
/api/decision
```

---

## Nach jedem Deploy prüfen
1. `https://alphacycle-production.up.railway.app/health` → `{"status":"ok"}`
2. Dashboard öffnen → Data Inspector → SHOW
3. Checkliste:
   - BTC Price → echter Wert (nicht —)
   - BTC Score → nicht 50
   - Regime → EXPANSION/NEUTRAL/CONTRACTION
   - Decision → BUY/SELL/HOLD etc.
   - Funding → N/A (solange OKX blockiert) oder echter Wert
   - Bond → zwischen 20-90 (nicht 100)
