"""
fetcher.py — Alpha Cycle Intelligence v3.0
Sources: Binance, CoinGecko, Alternative.me, DeFiLlama, FRED
"""
import os, math, asyncio, logging, time
from datetime import datetime, timedelta
import httpx

logger = logging.getLogger(__name__)
FRED_API_KEY      = os.getenv("FRED_API_KEY", "")
COINGECKO_API_KEY = os.getenv("COINGECKO_API_KEY", "")

HEADERS = {"User-Agent":"AlphaCycle/3.0 (+https://alphacycledashboard.netlify.app)","Accept":"application/json"}
TIMEOUT = httpx.Timeout(25.0, connect=10.0)

async def _get(url, params=None, headers=None, retries=2):
    h={**HEADERS,**(headers or {})}
    for attempt in range(retries+1):
        try:
            async with httpx.AsyncClient(timeout=TIMEOUT,follow_redirects=True) as c:
                r=await c.get(url,params=params,headers=h)
                r.raise_for_status(); return r.json()
        except Exception as e:
            if attempt<retries: await asyncio.sleep(3.0**attempt)
            else: logger.warning(f"FAILED {url}: {e}")
    return None

def _sf(v,fb=0.0):
    try:
        f=float(v); return fb if (math.isnan(f) or math.isinf(f)) else f
    except: return fb

# ── BINANCE ──────────────────────────────────────────────────────────────────
_BN="https://api.binance.com/api/v3"
_SYM={"bitcoin":"BTCUSDT","ethereum":"ETHUSDT"}

async def fetch_binance_prices(coin_id,days=730):
    sym=_SYM.get(coin_id)
    if not sym: return []
    data=await _get(f"{_BN}/klines",params={"symbol":sym,"interval":"1d","limit":min(days,1000)})
    if not data: return []
    prices=[_sf(c[4]) for c in data if _sf(c[4])>0]
    logger.info(f"Binance {sym}: {len(prices)}d"); return prices

async def fetch_binance_ticker(coin_id):
    sym=_SYM.get(coin_id)
    if not sym: return {}
    data=await _get(f"{_BN}/ticker/24hr",params={"symbol":sym})
    if not data: return {}
    return {"price":_sf(data.get("lastPrice")),"change_24h":_sf(data.get("priceChangePercent")),"volume_24h":_sf(data.get("quoteVolume"))}

async def fetch_funding_rates():
    try:
        btc=await _get("https://fapi.binance.com/fapi/v1/fundingRate",params={"symbol":"BTCUSDT","limit":1})
        eth=await _get("https://fapi.binance.com/fapi/v1/fundingRate",params={"symbol":"ETHUSDT","limit":1})
        return {
            "btc_funding_rate": round(_sf(btc[0]["fundingRate"])*100,4) if btc else 0.0,
            "eth_funding_rate": round(_sf(eth[0]["fundingRate"])*100,4) if eth else 0.0,
        }
    except Exception as e:
        logger.warning(f"Funding rates: {e}"); return {"btc_funding_rate":0.0,"eth_funding_rate":0.0}

# ── COINGECKO ────────────────────────────────────────────────────────────────
_CG="https://api.coingecko.com/api/v3"

def _cg_headers():
    h = {**HEADERS}
    if COINGECKO_API_KEY:
        h["x-cg-demo-api-key"] = COINGECKO_API_KEY
    return h

async def fetch_market_data(coin_id):
    data=await _get(
        f"{_CG}/coins/{coin_id}",
        params={"localization":"false","tickers":"false","community_data":"false","developer_data":"false"},
        headers=_cg_headers(),
    )
    d={"price":0.0,"change_24h":0.0,"market_cap":0.0,"volume":0.0,"ath":0.0,"ath_date":"","ath_change_pct":0.0}
    if not data or "market_data" not in data: return d
    md=data["market_data"]
    return {
        "price":          _sf(md.get("current_price",{}).get("usd",0)),
        "change_24h":     _sf(md.get("price_change_percentage_24h",0)),
        "market_cap":     _sf(md.get("market_cap",{}).get("usd",0)),
        "volume":         _sf(md.get("total_volume",{}).get("usd",0)),
        "ath":            _sf(md.get("ath",{}).get("usd",0)),
        "ath_date":       str(md.get("ath_date",{}).get("usd","")),
        "ath_change_pct": _sf(md.get("ath_change_percentage",{}).get("usd",0)),
    }

async def fetch_coin_prices_cg(coin_id,days=365):
    await asyncio.sleep(1)
    data = await _get(
        f"{_CG}/coins/{coin_id}/market_chart",
        params={"vs_currency": "usd", "days": days, "interval": "daily"},
        headers=_cg_headers(),
        retries=4,
    )
    if not data:
        logger.error(f"CoinGecko {coin_id}: no data returned")
        return []
    if "prices" not in data:
        logger.error(f"CoinGecko {coin_id}: unexpected response keys={list(data.keys())}")
        return []
    prices = [_sf(i[1]) for i in data["prices"] if _sf(i[1]) > 0]
    logger.info(f"CoinGecko {coin_id}: {len(prices)}d")
    return prices

async def fetch_global_data():
    try:
        data=await _get(f"{_CG}/global",headers=_cg_headers())
        if not data or "data" not in data: return {"btc_dominance":50.0,"total_market_cap":0.0}
        d=data["data"]
        return {
            "btc_dominance":         _sf(d.get("market_cap_percentage",{}).get("btc",50)),
            "total_market_cap":      _sf(d.get("total_market_cap",{}).get("usd",0)),
            "total_volume_24h":      _sf(d.get("total_volume",{}).get("usd",0)),
            "market_cap_change_24h": _sf(d.get("market_cap_change_percentage_24h_usd",0)),
        }
    except Exception as e:
        logger.warning(f"Global data: {e}"); return {"btc_dominance":50.0,"total_market_cap":0.0}

# ── FEAR & GREED ─────────────────────────────────────────────────────────────
async def fetch_fear_greed(limit=90):
    default={"current":50,"label":"Neutral","history":[]}
    data=await _get("https://api.alternative.me/fng/",params={"limit":limit,"format":"json"})
    if not data or "data" not in data: return default
    history=[]
    for item in reversed(data["data"]):
        try: history.append({"t":int(item["timestamp"])*1000,"v":int(item["value"]),"label":item["value_classification"]})
        except: continue
    cur=history[-1] if history else {"v":50,"label":"Neutral"}
    return {"current":cur["v"],"label":cur.get("label","Neutral"),"history":history}

# ── DEFILLAMA ────────────────────────────────────────────────────────────────
async def fetch_eth_tvl():
    for chain in ["Ethereum","ethereum"]:
        data=await _get(f"https://api.llama.fi/v2/historicalChainTvl/{chain}")
        if data:
            result=[{"t":int(i["date"])*1000,"v":_sf(i.get("tvl",0))} for i in data if _sf(i.get("tvl",0))>0]
            logger.info(f"DeFiLlama TVL: {len(result)} pts"); return result
    return []

async def fetch_stablecoin_supply():
    data=await _get("https://stablecoins.llama.fi/stablecoincharts/all")
    if not data: return []
    result=[]
    for item in data:
        try:
            circ=item.get("totalCirculatingUSD",{})
            total=sum(_sf(v) for v in circ.values() if isinstance(v,(int,float)))
            if total>0: result.append({"t":int(item["date"])*1000,"v":total})
        except: continue
    return result

# ── FRED ─────────────────────────────────────────────────────────────────────
async def fetch_walcl():
    if not FRED_API_KEY or FRED_API_KEY.strip() in ("","your_key_here"):
        logger.warning("WALCL: FRED_API_KEY missing — using synthetic")
        return _synthetic_walcl()
    
    url = "https://api.stlouisfed.org/fred/series/observations"
    params = {
        "series_id": "WALCL",
        "api_key": FRED_API_KEY.strip(),
        "file_type": "json",
        "observation_start": "2018-01-01"
    }
    data = await _get(url, params=params)
    
    if not data:
        logger.warning("WALCL: _get returned None — using synthetic")
        return _synthetic_walcl()
    
    if "observations" not in data:
        logger.warning(f"WALCL: no 'observations' key — got keys: {list(data.keys())}")
        return _synthetic_walcl()
    
    result = [
        {"t": int(datetime.strptime(o["date"], "%Y-%m-%d").timestamp()) * 1000,
         "v": _sf(o["value"])}
        for o in data["observations"]
        if o.get("value", ".") != "."
    ]
    
    if not result:
        logger.warning("WALCL: empty result after parsing — using synthetic")
        return _synthetic_walcl()
    
    logger.info(f"WALCL: loaded {len(result)} real datapoints ✅")
    return result

def _synthetic_walcl():
    import random; random.seed(42)
    start=datetime(2018,1,1); weeks=int((datetime.utcnow()-start).days/7); result=[]
    for i in range(weeks):
        d=start+timedelta(weeks=i); p=i/max(weeks,1)
        if p<0.35:   v=4_000_000+p*2_000_000
        elif p<0.55: v=4_700_000+(p-0.35)/0.20*4_200_000
        elif p<0.75: v=8_900_000-(p-0.55)/0.20*900_000
        else:        v=8_000_000-(p-0.75)/0.25*500_000
        result.append({"t":int(d.timestamp())*1000,"v":max(3_000_000,v+random.uniform(-50_000,50_000))})
    return result

async def fetch_fred_series(series_id,start="2020-01-01"):
    if not FRED_API_KEY or FRED_API_KEY in ("","your_key_here"): return []
    data=await _get("https://api.stlouisfed.org/fred/series/observations",params={
        "series_id":series_id,"api_key":FRED_API_KEY,"file_type":"json","observation_start":start})
    if not data or "observations" not in data: return []
    return [{"t":int(datetime.strptime(o["date"],"%Y-%m-%d").timestamp())*1000,"v":_sf(o["value"])}
            for o in data["observations"] if o.get("value",".")!="."]

# ── ON-CHAIN PROXIES ─────────────────────────────────────────────────────────
def _compute_mvrv_zscore(prices):
    if len(prices)<30: return 50.0
    try:
        clean=[p for p in prices if p>0]; window=min(730,len(clean))
        lt=clean[-window:]; mean=sum(lt)/len(lt)
        std=math.sqrt(sum((p-mean)**2 for p in lt)/len(lt)) or mean*0.3
        z=(clean[-1]-mean)/std
        if z<=-2:  return max(5.0,15+z*5)
        if z<=0:   return 15+(z+2)*15
        if z<=2:   return 45+z*12.5
        if z<=4:   return 70+(z-2)*10
        return min(95.0,90+(z-4)*2.5)
    except: return 50.0

def _compute_pi_cycle(prices):
    if len(prices)<350: return 50.0
    try:
        c=[p for p in prices if p>0]
        if len(c)<350: return 50.0
        ma111=sum(c[-111:])/111; ma350x2=(sum(c[-350:])/350)*2
        r=ma111/ma350x2 if ma350x2>0 else 1.0
        if r<=0.4:  return 5.0
        if r<=0.7:  return 5+(r-0.4)/0.3*30
        if r<=0.9:  return 35+(r-0.7)/0.2*25
        if r<=1.0:  return 60+(r-0.9)/0.1*25
        if r<=1.2:  return 85+(r-1.0)/0.2*10
        return 95.0
    except: return 50.0

def _compute_puell_multiple(prices):
    if len(prices)<365: return 50.0
    try:
        c=[p for p in prices if p>0]
        if len(c)<365: return 50.0
        puell=c[-1]/(sum(c[-365:])/365)
        if puell<=0.3: return 5.0
        if puell<=0.5: return 5+(puell-0.3)/0.2*15
        if puell<=1.0: return 20+(puell-0.5)/0.5*25
        if puell<=2.0: return 45+(puell-1.0)/1.0*25
        if puell<=4.0: return 70+(puell-2.0)/2.0*20
        return min(95.0,90+(puell-4.0)*2)
    except: return 50.0

# ── AGGREGATE ────────────────────────────────────────────────────────────────
async def fetch_all():
    logger.info("fetch_all v3: starting…")
    results=await asyncio.gather(
        fetch_binance_prices("bitcoin",730),   # 0
        fetch_binance_prices("ethereum",730),  # 1
        fetch_binance_ticker("bitcoin"),        # 2
        fetch_binance_ticker("ethereum"),       # 3
        fetch_market_data("bitcoin"),           # 4
        fetch_market_data("ethereum"),          # 5
        fetch_fear_greed(90),                   # 6
        fetch_eth_tvl(),                        # 7
        fetch_stablecoin_supply(),              # 8
        fetch_walcl(),                          # 9
        fetch_fred_series("DGS10"),             # 10
        fetch_global_data(),                    # 11
        fetch_funding_rates(),                  # 12
        return_exceptions=True,
    )
    def safe(r,d): return d if (isinstance(r,Exception) or r is None) else r

    btc_p  =safe(results[0],[])
    eth_p  =safe(results[1],[])
    btc_tk =safe(results[2],{})
    eth_tk =safe(results[3],{})
    btc_cg =safe(results[4],{"price":0,"change_24h":0,"market_cap":0,"volume":0,"ath":0,"ath_change_pct":0})
    eth_cg =safe(results[5],{"price":0,"change_24h":0,"market_cap":0,"volume":0,"ath":0,"ath_change_pct":0})
    fg     =safe(results[6],{"current":50,"label":"Neutral","history":[]})
    tvl    =safe(results[7],[])
    stable =safe(results[8],[])
    walcl  =safe(results[9],_synthetic_walcl())
    us10y  =safe(results[10],[])
    gdata  =safe(results[11],{"btc_dominance":50.0,"total_market_cap":0.0})
    funding=safe(results[12],{"btc_funding_rate":0.0,"eth_funding_rate":0.0})

    await asyncio.sleep(2)
    try:
        cg_btc = await fetch_coin_prices_cg("bitcoin",730)
        logger.info(f"CG BTC prices: {len(cg_btc)} pts, last={cg_btc[-1] if cg_btc else 'EMPTY'}")
    except Exception as e:
        logger.error(f"CG BTC fetch failed: {e}")
        cg_btc = []
    try:
        cg_eth = await fetch_coin_prices_cg("ethereum",730)
        logger.info(f"CG ETH prices: {len(cg_eth)} pts, last={cg_eth[-1] if cg_eth else 'EMPTY'}")
    except Exception as e:
        logger.error(f"CG ETH fetch failed: {e}")
        cg_eth = []
    btc_prices=cg_btc if len(cg_btc)>10 else (btc_p if len(btc_p)>10 else [])
    eth_prices=cg_eth if len(cg_eth)>10 else (eth_p if len(eth_p)>10 else [])
    if not walcl: walcl=_synthetic_walcl()

    def merge(tk,cg,prices=None):
        return {
            "price":         _sf(
                tk.get("price")
                or cg.get("price")
                or (prices[-1] if prices else 0)
            ),
            "change_24h":    _sf(tk.get("change_24h") or cg.get("change_24h",0)),
            "volume":        _sf(tk.get("volume_24h") or cg.get("volume",0)),
            "market_cap":    _sf(cg.get("market_cap",0)),
            "ath":           _sf(cg.get("ath",0)),
            "ath_date":      cg.get("ath_date",""),
            "ath_change_pct":_sf(cg.get("ath_change_pct",0)),
        }

    indicators={
        "mvrv_score":  round(_compute_mvrv_zscore(btc_prices),1),
        "pi_score":    round(_compute_pi_cycle(btc_prices),1),
        "puell_score": round(_compute_puell_multiple(btc_prices),1),
    }

    logger.info(f"fetch_all done — BTC:{len(btc_prices)}d F&G:{fg['current']} "
                f"DOM:{gdata.get('btc_dominance',0):.1f}% "
                f"MVRV:{indicators['mvrv_score']} Pi:{indicators['pi_score']} Puell:{indicators['puell_score']}")

    return {
        "btc_prices":   btc_prices,
        "eth_prices":   eth_prices,
        "btc_market":   merge(btc_tk,btc_cg,btc_prices),
        "eth_market":   merge(eth_tk,eth_cg,eth_prices),
        "fear_greed":   fg,
        "tvl_series":   tvl,
        "stable_series":stable,
        "walcl_series": walcl,
        "us10y_series": us10y,
        "global_data":  gdata,
        "funding_data": funding,
        "indicators":   indicators,
        "fetched_at":   int(time.time()*1000),
    }
