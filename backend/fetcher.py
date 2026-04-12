"""
fetcher.py - Alpha Cycle Intelligence v3.0
Sources: Binance, CoinGecko, Alternative.me, DeFiLlama, FRED
"""
import os, math, asyncio, logging, time
from datetime import datetime, timedelta
from typing import Optional, Any
import httpx

logger = logging.getLogger(__name__)
FRED_API_KEY      = os.getenv("FRED_API_KEY", "")
COINGECKO_API_KEY = os.getenv("COINGECKO_API_KEY", "")

HEADERS = {"User-Agent":"AlphaCycle/3.0 (+https://alphacycledashboard.netlify.app)","Accept":"application/json"}
TIMEOUT = httpx.Timeout(25.0, connect=10.0)

async def _get(
    url: str,
    params: Optional[dict] = None,
    headers: Optional[dict] = None,
    retries: int = 2,
) -> Optional[Any]:
    h={**HEADERS,**(headers or {})}
    for attempt in range(retries+1):
        try:
            async with httpx.AsyncClient(timeout=TIMEOUT,follow_redirects=True) as c:
                r=await c.get(url,params=params,headers=h)
                r.raise_for_status(); return r.json()
        except Exception as e:
            if attempt<retries: await asyncio.sleep(1.5**attempt)
            else: logger.warning(f"FAILED {url}: {e}")
    return None

def _sf(v: Any, fb: float = 0.0) -> float:
    try:
        f=float(v); return fb if (math.isnan(f) or math.isinf(f)) else f
    except: return fb

# -- BINANCE ------------------------------------------------------------------
_BN="https://api.binance.com/api/v3"
_SYM={"bitcoin":"BTCUSDT","ethereum":"ETHUSDT"}

async def fetch_binance_prices(coin_id: str, days: int = 730) -> list[float]:
    sym=_SYM.get(coin_id)
    if not sym: return []
    data=await _get(f"{_BN}/klines",params={"symbol":sym,"interval":"1d","limit":min(days,1000)})
    if not data: return []
    prices=[_sf(c[4]) for c in data if _sf(c[4])>0]
    logger.info(f"Binance {sym}: {len(prices)}d"); return prices

async def fetch_binance_ticker(coin_id: str) -> dict:
    sym=_SYM.get(coin_id)
    if not sym: return {}
    data=await _get(f"{_BN}/ticker/24hr",params={"symbol":sym})
    if not data: return {}
    return {"price":_sf(data.get("lastPrice")),"change_24h":_sf(data.get("priceChangePercent")),"volume_24h":_sf(data.get("quoteVolume"))}

async def fetch_funding_rates() -> dict[str, float]:
    """OKX public funding rate - no auth, Railway-compatible."""
    try:
        btc = await _get(
            "https://www.okx.com/api/v5/public/funding-rate",
            params={"instId": "BTC-USDT-SWAP"}
        )
        eth = await _get(
            "https://www.okx.com/api/v5/public/funding-rate",
            params={"instId": "ETH-USDT-SWAP"}
        )
        btc_rate = 0.0
        eth_rate = 0.0
        if btc and btc.get("data"):
            btc_rate = round(_sf(btc["data"][0].get("fundingRate", 0)) * 100, 4)
        if eth and eth.get("data"):
            eth_rate = round(_sf(eth["data"][0].get("fundingRate", 0)) * 100, 4)
        return {"btc_funding_rate": btc_rate, "eth_funding_rate": eth_rate}
    except Exception as e:
        logger.warning(f"Funding rates (OKX): {e}")
        return {"btc_funding_rate": 0.0, "eth_funding_rate": 0.0}


async def fetch_kraken_prices(pair: str = "XBTUSD", days: int = 730) -> list[float]:
    """Kraken OHLC daily - reliable from Railway US-West."""
    since = int(time.time()) - (days * 86400)
    data = await _get(
        "https://api.kraken.com/0/public/OHLC",
        params={"pair": pair, "interval": 1440, "since": since}
    )
    if not data or data.get("error") or "result" not in data:
        return []
    keys = [k for k in data["result"] if k != "last"]
    if not keys:
        return []
    prices = [_sf(c[4]) for c in data["result"][keys[0]] if _sf(c[4]) > 0]
    logger.info(f"Kraken {pair}: {len(prices)}d")
    return prices


async def fetch_kraken_ohlc_latest(pair: str = "XBTUSD") -> dict:
    """Fetch latest daily OHLC from Kraken. Returns {high, low, close}."""
    since = int(time.time()) - 3 * 86400
    data = await _get(
        "https://api.kraken.com/0/public/OHLC",
        params={"pair": pair, "interval": 1440, "since": since},
    )
    if not data or data.get("error") or "result" not in data:
        return {}
    keys = [k for k in data["result"] if k != "last"]
    if not keys:
        return {}
    candles = data["result"][keys[0]]
    if not candles:
        return {}
    last = candles[-1]
    return {
        "high": _sf(last[2]),
        "low": _sf(last[3]),
        "close": _sf(last[4]),
    }


async def fetch_kraken_ticker(pair: str = "XBTUSD") -> dict:
    """Kraken spot ticker."""
    data = await _get(
        "https://api.kraken.com/0/public/Ticker",
        params={"pair": pair}
    )
    if not data or data.get("error") or "result" not in data:
        return {}
    keys = list(data["result"].keys())
    if not keys:
        return {}
    t = data["result"][keys[0]]
    return {
        "price":      _sf(t.get("c", [0])[0]),
        "change_24h": 0.0,
        "volume_24h": _sf(t.get("v", [0, 0])[1]),
    }

# -- COINGECKO -----------------------------------------------------------------
_CG="https://api.coingecko.com/api/v3"

def _cgp(extra: Optional[dict] = None) -> dict:
    p=dict(extra or {})
    if COINGECKO_API_KEY: p["x_cg_demo_api_key"]=COINGECKO_API_KEY
    return p

async def fetch_market_data(coin_id: str) -> dict:
    data=await _get(f"{_CG}/coins/{coin_id}",params=_cgp({"localization":"false","tickers":"false","community_data":"false","developer_data":"false"}))
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

async def fetch_coin_prices_cg(coin_id: str, days: int = 365) -> list[float]:
    data=await _get(f"{_CG}/coins/{coin_id}/market_chart",params=_cgp({"vs_currency":"usd","days":days,"interval":"daily"}))
    if not data or "prices" not in data: return []
    prices=[_sf(i[1]) for i in data["prices"] if _sf(i[1])>0]
    logger.info(f"CoinGecko {coin_id}: {len(prices)}d"); return prices

async def fetch_global_data() -> dict:
    default = {
        "btc_dominance": 55.0,
        "total_market_cap": 0.0,
        "total_volume_24h": 0.0,
        "market_cap_change_24h": 0.0,
    }
    try:
        # CoinCap v2: no API key required, suitable for Railway
        data = await _get("https://api.coincap.io/v2/assets", params={"limit": "5"})
        if not data or "data" not in data:
            return default
        assets = data["data"]
        btc = next((a for a in assets if a.get("id") == "bitcoin"), None)
        if not btc:
            return default

        btc_mc = _sf(btc.get("marketCapUsd", 0))

        # Approximate total market cap from top 5, assuming they are ~78% of total
        total_top5 = 0.0
        for a in assets:
            total_top5 += _sf(a.get("marketCapUsd", 0))
        total_mc = total_top5 / 0.78 if total_top5 > 0 else 0.0

        dom = round(btc_mc / total_mc * 100, 1) if total_mc > 0 else 55.0

        return {
            "btc_dominance": dom,
            "total_market_cap": total_mc,
            "total_volume_24h": _sf(btc.get("volumeUsd24Hr", 0)),
            "market_cap_change_24h": _sf(btc.get("changePercent24Hr", 0)),
        }
    except Exception as e:
        logger.warning("fetch_global_data failed: %s", e)
        return default

# -- FEAR & GREED -----------------------------------------------------------------
async def fetch_fear_greed(limit: int = 90) -> dict:
    default={"current":50,"label":"Neutral","history":[]}
    data=await _get("https://api.alternative.me/fng/",params={"limit":limit,"format":"json"})
    if not data or "data" not in data: return default
    history=[]
    for item in reversed(data["data"]):
        try: history.append({"t":int(item["timestamp"])*1000,"v":int(item["value"]),"label":item["value_classification"]})
        except: continue
    cur=history[-1] if history else {"v":50,"label":"Neutral"}
    return {"current":cur["v"],"label":cur.get("label","Neutral"),"history":history}

# -- DEFILLAMA --------------------------------------------------------------------
async def fetch_eth_tvl() -> list[dict]:
    for chain in ["Ethereum","ethereum"]:
        data=await _get(f"https://api.llama.fi/v2/historicalChainTvl/{chain}")
        if data:
            result=[{"t":int(i["date"])*1000,"v":_sf(i.get("tvl",0))} for i in data if _sf(i.get("tvl",0))>0]
            logger.info(f"DeFiLlama TVL: {len(result)} pts"); return result
    return []

async def fetch_stablecoin_supply() -> list[dict]:
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

# -- FRED -------------------------------------------------------------------------
async def fetch_walcl() -> list[dict]:
    if not FRED_API_KEY or FRED_API_KEY in ("","your_key_here"):
        return _synthetic_walcl()
    data=await _get("https://api.stlouisfed.org/fred/series/observations",params={
        "series_id":"WALCL","api_key":FRED_API_KEY,"file_type":"json","observation_start":"2018-01-01"})
    if not data or "observations" not in data: return _synthetic_walcl()
    result=[{"t":int(datetime.strptime(o["date"],"%Y-%m-%d").timestamp())*1000,"v":_sf(o["value"])}
            for o in data["observations"] if o.get("value",".")!="."]
    return result if result else _synthetic_walcl()

def _synthetic_walcl() -> list[dict]:
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

async def fetch_fred_series(series_id: str, start: str = "2020-01-01") -> list[dict]:
    if not FRED_API_KEY or FRED_API_KEY in ("","your_key_here"): return []
    data=await _get("https://api.stlouisfed.org/fred/series/observations",params={
        "series_id":series_id,"api_key":FRED_API_KEY,"file_type":"json","observation_start":start})
    if not data or "observations" not in data: return []
    result=[{"t":int(datetime.strptime(o["date"],"%Y-%m-%d").timestamp())*1000,"v":_sf(o["value"])}
            for o in data["observations"] if o.get("value",".")!="."]
    logger.info("FRED %s: %s pts", series_id, len(result))
    return result


def _compute_net_liquidity(
    walcl: list[dict],
    tga: list[dict],
    rrp: list[dict],
) -> list[dict]:
    """
    Net Liquidity = WALCL - TGA - RRP
    Alle drei Serien sind weekly/daily FRED Daten {"t":..,"v":..}
    Wir alignen auf gemeinsame Timestamps (nearest week).
    Returns list of {"t": timestamp_ms, "v": net_liq_value}
    """
    if not walcl:
        return []
    tga_dict = {item["t"]: item["v"] for item in tga if isinstance(item, dict)}
    rrp_dict = {item["t"]: item["v"] for item in rrp if isinstance(item, dict)}
    result = []
    for item in walcl:
        t = item["t"]
        w = _sf(item.get("v", 0))
        if w <= 0:
            continue
        tga_val = 0.0
        rrp_val = 0.0
        for delta in [0, 86400000, -86400000, 172800000, -172800000,
                      604800000, -604800000]:
            if t + delta in tga_dict:
                tga_val = _sf(tga_dict[t + delta])
                break
        for delta in [0, 86400000, -86400000, 172800000, -172800000,
                      604800000, -604800000]:
            if t + delta in rrp_dict:
                # FRED RRPONTSYD in billions USD; WALCL/TGA in millions
                rrp_val = _sf(rrp_dict[t + delta]) * 1000
                break
        net = w - tga_val - rrp_val
        if net != 0:
            result.append({"t": t, "v": net})
    return result


# -- ON-CHAIN PROXIES -------------------------------------------------------------
def _compute_mvrv_zscore(prices: list[float]) -> float:
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

def _compute_pi_cycle(prices: list[float]) -> float:
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

def _compute_puell_multiple(prices: list[float]) -> float:
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

# -- AGGREGATE --------------------------------------------------------------------
async def fetch_all() -> dict:
    logger.info("fetch_all v3: starting...")
    results=await asyncio.gather(
        fetch_kraken_prices("XBTUSD", 730),     # 0
        fetch_kraken_prices("XETHZUSD", 730),   # 1
        fetch_kraken_ticker("XBTUSD"),          # 2
        fetch_kraken_ticker("XETHZUSD"),        # 3
        fetch_fear_greed(90),                   # 4
        fetch_eth_tvl(),                        # 5
        fetch_stablecoin_supply(),              # 6
        fetch_walcl(),                          # 7
        fetch_fred_series("DGS10"),             # 8
        fetch_global_data(),                   # 9
        fetch_funding_rates(),                 # 10
        fetch_fred_series("WTREGEN", start="2015-01-01"),   # 11 Treasury General Account
        fetch_fred_series("RRPONTSYD", start="2015-01-01"), # 12 Reverse Repo
        return_exceptions=True,
    )
    def safe(r,d): return d if (isinstance(r,Exception) or r is None) else r

    btc_p  =safe(results[0],[])
    eth_p  =safe(results[1],[])
    btc_tk =safe(results[2],{})
    eth_tk =safe(results[3],{})
    btc_cg ={"price":0,"change_24h":0,"market_cap":0,"volume":0,"ath":0,"ath_change_pct":0}
    eth_cg ={"price":0,"change_24h":0,"market_cap":0,"volume":0,"ath":0,"ath_change_pct":0}
    fg     =safe(results[4],{"current":50,"label":"Neutral","history":[]})
    tvl    =safe(results[5],[])
    stable =safe(results[6],[])
    walcl  =safe(results[7],_synthetic_walcl())
    us10y  =safe(results[8],[])
    gdata  =safe(results[9],{"btc_dominance":50.0,"total_market_cap":0.0})
    funding=safe(results[10],{"btc_funding_rate":0.0,"eth_funding_rate":0.0})
    tga_series = safe(results[11], [])
    rrp_series = safe(results[12], [])

    btc_prices=btc_p if len(btc_p)>10 else await fetch_coin_prices_cg("bitcoin",365)
    eth_prices=eth_p if len(eth_p)>10 else await fetch_coin_prices_cg("ethereum",365)
    if not walcl: walcl=_synthetic_walcl()

    def merge(tk, cg, cap_fallback_supply=None):
        price = _sf(tk.get("price") or cg.get("price",0))
        mcap = _sf(cg.get("market_cap",0))
        if mcap <= 0 and price > 0 and cap_fallback_supply is not None:
            mcap = price * cap_fallback_supply  # e.g. BTC ~19.7M circulating
        return {
            "price":         price,
            "change_24h":    _sf(tk.get("change_24h") or cg.get("change_24h",0)),
            "volume":        _sf(tk.get("volume_24h") or cg.get("volume",0)),
            "market_cap":    mcap,
            "ath":           _sf(cg.get("ath",0)),
            "ath_date":      cg.get("ath_date",""),
            "ath_change_pct":_sf(cg.get("ath_change_pct",0)),
        }

    indicators={
        "mvrv_score":  round(_compute_mvrv_zscore(btc_prices),1),
        "pi_score":    round(_compute_pi_cycle(btc_prices),1),
        "puell_score": round(_compute_puell_multiple(btc_prices),1),
    }

    btc_market = merge(btc_tk, btc_cg, 19_700_000)
    eth_market = merge(eth_tk, eth_cg)
    if gdata.get("btc_dominance", 50.0) == 50.0:
        btc_mc = btc_market.get("market_cap", 0)
        total_mc = gdata.get("total_market_cap", 0)
        if btc_mc > 0 and total_mc > 0:
            gdata["btc_dominance"] = round(btc_mc / total_mc * 100, 1)

    net_liq_series = _compute_net_liquidity(walcl, tga_series, rrp_series)

    logger.info(f"fetch_all done - BTC:{len(btc_prices)}d F&G:{fg['current']} "
                f"DOM:{gdata.get('btc_dominance',0):.1f}% "
                f"MVRV:{indicators['mvrv_score']} Pi:{indicators['pi_score']} Puell:{indicators['puell_score']}")

    return {
        "btc_prices":   btc_prices,
        "eth_prices":   eth_prices,
        "btc_market":   btc_market,
        "eth_market":   eth_market,
        "fear_greed":   fg,
        "tvl_series":   tvl,
        "stable_series":stable,
        "walcl_series": walcl,
        "us10y_series": us10y,
        "global_data":  gdata,
        "funding_data": funding,
        "net_liq_series": net_liq_series,
        "tga_series":   tga_series,
        "rrp_series":   rrp_series,
        "indicators":   indicators,
        "fetched_at":   int(time.time()*1000),
    }
