> **Before working on this repository, read these 5 documents in order:**
> 1. `docs/SYSTEM_TRUTH.md` — Immutable rules, ARC v1.2 formula
> 2. `docs/AI_MASTER_CONTEXT.md` — Complete system architecture
> 3. `docs/AI_AGENT_ROLES.md` — Agent definitions + initialization protocol
> 4. `docs/AI_MASTER_PROMPT.md` — Behavioral rules + Cursor workflow
> 5. `docs/AI_AGENT_MASTERPROMPTS.md` — Detailed masterprompt per agent

# Alpha Cycle Intelligence

Proprietary crypto market cycle intelligence platform.
Real-time BTC, ETH, and Macro cycle scoring.

**Production backend:** `https://alphacycle-production.up.railway.app` (see `index.html` `BACKEND_URL`). Deploy log: `DEPLOY_STATE.md`. Canonical docs: the five files listed above under `docs/`.

---

## 🚀 Deployment Guide (15 minutes total)

### Step 1 — Push this repo to GitHub

1. Go to **github.com** → click **New repository**
2. Name it `alphacycle` (or anything you want)
3. Set to **Public** (required for Render free tier)
4. Click **Create repository**
5. Follow GitHub's instructions to push this folder:

```bash
git init
git add .
git commit -m "Alpha Cycle Intelligence v2.0"
git remote add origin https://github.com/YOUR_USERNAME/alphacycle.git
git push -u origin main
```

---

### Step 2 — Get your free FRED API key

1. Go to **https://research.stlouisfed.org/useraccount/apikeys**
2. Create a free account (just email + password)
3. Click **Request API Key** → approve instantly
4. Copy your key — looks like: `abcdef1234567890abcdef1234567890`

This gives you real Fed balance sheet data (WALCL). Without it, the app uses synthetic data as fallback — still works fine.

---

### Step 3 — Deploy backend to Render

1. Go to **render.com** → Sign up / Log in (free)
2. Click **New** → **Web Service**
3. Connect your GitHub account → select `alphacycle` repo
4. Configure:
   - **Name:** `alphacycle-api` (or anything)
   - **Root Directory:** `backend`
   - **Runtime:** `Python 3`
   - **Build Command:** `pip install -r requirements.txt`
   - **Start Command:** `gunicorn main:app --workers 2 --worker-class uvicorn.workers.UvicornWorker --bind 0.0.0.0:$PORT --timeout 120`
   - **Plan:** `Free`
5. Click **Advanced** → **Add Environment Variable:**
   - Key: `FRED_API_KEY`
   - Value: *(paste your FRED key from Step 2)*
6. Click **Create Web Service**
7. Wait ~3 minutes for build to complete
8. Your backend URL will be: `https://alphacycle-api.onrender.com`

✅ Test it: open `https://YOUR-RENDER-URL.onrender.com/health` in browser
You should see: `{"status":"ok","service":"Alpha Cycle Intelligence API",...}`

---

### Step 4 — Connect frontend to backend

1. Open `index.html` in a text editor
2. Find line ~1305 (search for `BACKEND_URL`):
```javascript
const BACKEND_URL = window.BACKEND_URL || '';
```
3. Change it to your Render URL:
```javascript
const BACKEND_URL = 'https://alphacycle-api.onrender.com';
```
4. Save the file

---

### Step 5 — Deploy frontend to Netlify

**Option A — Drag & Drop (fastest):**
1. Go to **app.netlify.com/drop**
2. Drag `index.html` onto the page
3. Done! Netlify gives you a live URL instantly.

**Option B — Connect to GitHub (auto-deploys on every push):**
1. Go to **app.netlify.com** → **Add new site** → **Import an existing project**
2. Connect GitHub → select `alphacycle` repo
3. Build settings:
   - **Base directory:** *(leave empty)*
   - **Build command:** *(leave empty)*
   - **Publish directory:** `.`
4. Click **Deploy site**
5. Rename site to `alphacycledashboard` (or custom domain)

---

### Step 6 — (Optional) Set custom domain

1. In Netlify: **Site settings** → **Domain management** → **Add custom domain**
2. Enter your domain, follow DNS instructions
3. SSL certificate is automatic (free via Let's Encrypt)

---

## 📁 Project Structure

```
alphacycle/
├── index.html              # Frontend dashboard (single file)
├── netlify.toml            # Netlify deployment config
├── render.yaml             # Render deployment config (optional)
├── .env.example            # Environment variable template
├── .gitignore
└── backend/
    ├── main.py             # FastAPI app — 11 endpoints
    ├── scoring.py          # Cycle scoring engine (zero NaN)
    ├── fetcher.py          # API integrations with fallbacks
    ├── analyzer.py         # Cycle Analyzer Engine
    ├── decision_engine.py  # Decision Engine
    ├── cycle_anchor.py     # Cycle Anchor Engine (historical timing)
    ├── requirements.txt    # Python dependencies
    └── Dockerfile          # Optional Docker deployment
```

---

## 🔌 API Endpoints

Once deployed, your backend serves:

| Endpoint | Description |
|----------|-------------|
| `GET /health` | Service status + cache age |
| `GET /api/prices` | BTC/ETH live prices + history |
| `GET /api/cycle/btc` | BTC cycle score + 7 components |
| `GET /api/cycle/eth` | ETH cycle score + 9 components |
| `GET /api/cycle/macro` | Macro liquidity score + WALCL |
| `GET /api/cycle/combined` | Master score + phase classification |
| `GET /api/history` | Full chart data (730d prices) |
| `GET /api/fear-greed` | Fear & Greed index + 90d history |
| `GET /api/analyzer` | Cycle Analyzer (phase, seasonality, probabilities) |
| `GET /api/decision` | Decision Engine (signal, allocation, strategy) |
| `GET /api/cycle-anchor` | Cycle Anchor (historical cycle timing, halving position) |

---

## 📊 Data Sources

| Source | Data | Free |
|--------|------|------|
| CoinGecko | BTC/ETH prices, market data | ✅ |
| Alternative.me | Fear & Greed index | ✅ |
| DeFiLlama | ETH TVL, stablecoin supply | ✅ |
| FRED (St. Louis Fed) | WALCL (Fed balance sheet) | ✅ free API key |

---

## ⚠️ Important Notes

- **Render free tier** spins down after 15min of inactivity. First request after idle takes ~30s to warm up. Upgrade to $7/mo Starter plan to avoid this.
- **Netlify:** Wenn die Seite beim ersten Aufruf keine Daten zeigt, 30–60 Sekunden warten und auf **„Erneut versuchen“** klicken (Backend-Retry ist eingebaut).
- **CoinGecko free API** has rate limits. The backend caches all data for 60s so this is not an issue in practice.
- **FRED API** is completely free, no rate limits for typical usage.

---

*Alpha Cycle Intelligence — Proprietary market cycle scoring system.*
