"""
scoring.py — Alpha Cycle Intelligence v3.0
Zero NaN guarantee. All outputs [0,100].
"""
import math, logging
logger = logging.getLogger(__name__)

def safe_div(a,b,fb=1.0):
    try:
        if b==0 or math.isnan(b) or math.isinf(b): return fb
        r=a/b; return fb if (math.isnan(r) or math.isinf(r)) else r
    except: return fb

def safe_float(v,fb=0.0):
    try:
        if v is None: return fb
        f=float(v); return fb if (math.isnan(f) or math.isinf(f)) else f
    except: return fb

def clamp(v,lo=0.0,hi=100.0):
    return max(lo,min(hi,safe_float(v,(lo+hi)/2)))

def safe_mean(values,fb=50.0):
    clean=[safe_float(v) for v in values if v is not None]
    clean=[v for v in clean if not math.isnan(v)]
    return sum(clean)/len(clean) if clean else fb

def pct_change(cur,prev,fb=0.0):
    return safe_div((cur-prev),abs(prev)+1e-10,fb)*100

def compute_rsi(prices,period=14):
    if len(prices)<period+1: return 50.0
    deltas=[prices[i]-prices[i-1] for i in range(1,len(prices))]
    gains=[max(0.0,d) for d in deltas[-period:]]
    losses=[max(0.0,-d) for d in deltas[-period:]]
    ag=safe_mean(gains,0.0); al=safe_mean(losses,0.0)
    if al==0: return 100.0 if ag>0 else 50.0
    rsi=100-safe_div(100,1+safe_div(ag,al,1.0),50.0)
    return clamp(rsi)

def rsi_to_score(rsi):
    rsi=clamp(rsi)
    if rsi<=20: return clamp(5+rsi*0.25)
    if rsi<=30: return clamp(10+(rsi-20)*0.5)
    if rsi<=50: return clamp(15+(rsi-30)*1.5)
    if rsi<=70: return clamp(45+(rsi-50)*1.25)
    if rsi<=80: return clamp(70+(rsi-70)*1.5)
    return clamp(85+(rsi-80)*0.5)

def moving_average(prices,window):
    if len(prices)<window: return None
    return safe_mean(prices[-window:])

def ma_deviation_score(price,ma):
    if ma<=0: return 50.0
    dev=pct_change(price,ma)
    if dev<=-60:  return 2.0
    if dev<=0:    return clamp(2+(dev+60)*0.55)
    if dev<=100:  return clamp(35+dev*0.30)
    if dev<=200:  return clamp(65+(dev-100)*0.17)
    if dev<=500:  return clamp(82+(dev-200)*0.043)
    return 95.0

def trend_score(values,window=30,neutral=50.0):
    if len(values)<max(2,window): return neutral
    clean=[safe_float(v) for v in values if v is not None and safe_float(v)>0]
    if len(clean)<2: return neutral
    cur=clean[-1]; prev=clean[-min(window,len(clean)-1)-1] if window<len(clean) else clean[0]
    if prev<=0: return neutral
    return clamp(50+clamp(pct_change(cur,prev),-50,50))

def drawdown_score(prices):
    if not prices: return 50.0
    clean=[p for p in prices if p and p>0]
    if not clean: return 50.0
    if len(clean) < 10: return 50.0
    dd=safe_div(clean[-1]-max(clean),max(clean),-0.5)*100
    if dd>=0:   return 85.0
    if dd>=-15: return clamp(70+(dd+15)*1.0)
    if dd>=-40: return clamp(45+(dd+40)*1.0)
    if dd>=-70: return clamp(15+(dd+70)*1.0)
    return 5.0

def fg_to_score(v): return clamp(safe_float(v,50.0))

def funding_rate_to_score(rate_pct):
    r=safe_float(rate_pct,0.0)
    if r<=-0.05: return 10.0
    if r<=-0.01: return 20.0
    if r<=0.01:  return 45.0
    if r<=0.03:  return 55.0
    if r<=0.05:  return 65.0
    if r<=0.10:  return 78.0
    return 90.0

def btc_dominance_to_score(dom_pct):
    d=clamp(safe_float(dom_pct,50.0),30,70)
    if d>=65:  return clamp(75+(d-65)*2)
    if d>=55:  return clamp(55+(d-55)*2)
    if d>=45:  return clamp(45-(d-45)*2)
    if d>=35:  return clamp(65+(45-d)*2)
    return 85.0

def _power_law_score(prices):
    if len(prices)<30: return 50.0
    try:
        n=len(prices)
        lp=[math.log(max(p,1)) for p in prices]
        ld=[math.log(max(i+1,1)) for i in range(n)]
        mlp=safe_mean(lp); mld=safe_mean(ld)
        num=sum((ld[i]-mld)*(lp[i]-mlp) for i in range(n))
        den=sum((ld[i]-mld)**2 for i in range(n))
        slope=safe_div(num,den,1.0); intercept=mlp-slope*mld
        fair=math.exp(intercept+slope*ld[-1])
        dev=pct_change(prices[-1],fair)
        if dev<=-80: return 5.0
        if dev<=0:   return clamp(5+(dev+80)*0.4375)
        if dev<=100: return clamp(40+dev*0.30)
        if dev<=300: return clamp(70+(dev-100)*0.125)
        return 95.0
    except: return 50.0

def compute_btc_score(prices_daily, fear_greed, walcl_values, stablecoin_supply,
                      indicators=None, funding_data=None, btc_dominance=None):
    s={}
    prices=[safe_float(p) for p in prices_daily if p and safe_float(p)>0]
    if not prices: prices=[50000.0]
    current=prices[-1]

    weekly=prices[::7] if len(prices)>=14 else prices
    rsi_val=compute_rsi(weekly,min(14,max(2,len(weekly)-1)))
    s["rsi"]=rsi_to_score(rsi_val); s["rsi_raw"]=round(rsi_val,1)

    weekly_all=prices[::7]
    ma200=moving_average(weekly_all,200) or moving_average(weekly_all,max(2,len(weekly_all)))
    if ma200 and ma200>0:
        s["ma_200w"]=ma_deviation_score(current,ma200)
        s["ma_200w_raw"]=round(ma200,0); s["ma_200w_dev_pct"]=round(pct_change(current,ma200),1)
    else:
        s["ma_200w"]=50.0; s["ma_200w_raw"]=current; s["ma_200w_dev_pct"]=0.0

    s["drawdown"]=drawdown_score(prices)
    s["fear_greed"]=fg_to_score(fear_greed)

    walcl=[safe_float(v) for v in walcl_values if v and safe_float(v)>0]
    s["macro_liq"]=clamp(100-trend_score(walcl,min(26,len(walcl)-1))) if len(walcl)>=2 else 50.0

    stable=[safe_float(v) for v in stablecoin_supply if v and safe_float(v)>0]
    s["stable_supply"]=clamp(100-trend_score(stable,min(90,len(stable)-1))) if len(stable)>=2 else 50.0

    s["power_law"]=_power_law_score(prices)

    ind=indicators or {}
    s["mvrv"]    =clamp(safe_float(ind.get("mvrv_score",  50.0)))
    s["pi_cycle"]=clamp(safe_float(ind.get("pi_score",    50.0)))
    s["puell"]   =clamp(safe_float(ind.get("puell_score", 50.0)))

    fd=funding_data or {}
    s["funding"]    =funding_rate_to_score(fd.get("btc_funding_rate",0.0))
    s["funding_raw"]=round(safe_float(fd.get("btc_funding_rate",0.0)),4)

    dom=safe_float(btc_dominance,50.0)
    s["btc_dom"]=btc_dominance_to_score(dom); s["btc_dom_raw"]=round(dom,1)

    weights={
        "ma_200w":0.18,"mvrv":0.15,"fear_greed":0.12,"drawdown":0.10,
        "rsi":0.10,"puell":0.10,"pi_cycle":0.08,"macro_liq":0.08,
        "stable_supply":0.05,"funding":0.02,"power_law":0.02,
    }
    s["btc_score"]=_weighted(s,weights)
    s["current_price"]=round(current,2)
    return s

def compute_eth_score(eth_prices, btc_prices, tvl_series, stablecoin_supply,
                      fear_greed, funding_data=None):
    s={}
    eth =[safe_float(p) for p in eth_prices       if p and safe_float(p)>0]
    btc =[safe_float(p) for p in btc_prices        if p and safe_float(p)>0]
    tvl =[safe_float(v) for v in tvl_series        if v and safe_float(v)>0]
    stbl=[safe_float(v) for v in stablecoin_supply if v and safe_float(v)>0]

    n=min(len(eth),len(btc))
    if n>=2:
        ratios=[safe_div(e,b,0.05) for e,b in zip(eth[-n:],btc[-n:]) if 0<safe_div(e,b,0)<1]
        if len(ratios)>=2:
            s["eth_btc_ratio"]=trend_score(ratios,min(60,len(ratios)-1))
            s["eth_btc_ratio_raw"]=round(ratios[-1],5)
        else:
            s["eth_btc_ratio"]=50.0; s["eth_btc_ratio_raw"]=0.05
    else:
        s["eth_btc_ratio"]=50.0; s["eth_btc_ratio_raw"]=0.05

    if len(eth)>=2:
        s["price_trend_30d"]=trend_score(eth,min(30,len(eth)-1))
        s["price_trend_90d"]=trend_score(eth,min(90,len(eth)-1))
    else:
        s["price_trend_30d"]=s["price_trend_90d"]=50.0

    s["tvl_trend"]=trend_score(tvl,min(90,len(tvl)-1)) if len(tvl)>=2 else 50.0
    s["stable_growth"]=clamp(50+(trend_score(stbl,min(90,len(stbl)-1))-50)*0.5) if len(stbl)>=2 else 50.0

    ew=eth[::7] if len(eth)>=14 else eth
    s["rsi"]=rsi_to_score(compute_rsi(ew,min(14,max(2,len(ew)-1))))

    ew_all=eth[::7]
    ma200=moving_average(ew_all,200) or moving_average(ew_all,max(2,len(ew_all)))
    s["ma_200w"]=ma_deviation_score(eth[-1],ma200) if (ma200 and ma200>0 and eth) else 50.0
    s["drawdown"]=drawdown_score(eth)
    s["fear_greed"]=fg_to_score(fear_greed)

    fd=funding_data or {}
    s["eth_funding"]=funding_rate_to_score(fd.get("eth_funding_rate",0.0))

    weights={
        "eth_btc_ratio":0.20,"tvl_trend":0.17,"price_trend_30d":0.12,
        "rsi":0.12,"ma_200w":0.10,"price_trend_90d":0.09,
        "drawdown":0.07,"stable_growth":0.06,"fear_greed":0.04,"eth_funding":0.03,
    }
    s["eth_score"]=_weighted(s,weights)
    s["current_price"]=round(eth[-1],2) if eth else 0.0
    return s

def compute_macro_score(walcl_series, stablecoin_supply, btc_prices,
                        dxy_series=None, us10y_series=None,
                        global_data=None, funding_data=None):
    s={}
    walcl=[safe_float(v) for v in walcl_series       if v and safe_float(v)>0]
    stbl =[safe_float(v) for v in stablecoin_supply  if v and safe_float(v)>0]
    btc  =[safe_float(v) for v in btc_prices         if v and safe_float(v)>0]

    if len(walcl)>=2:
        s["walcl_trend"]=clamp(100-trend_score(walcl,min(26,len(walcl)-1)))
        w26=min(26,len(walcl)-1)
        s["walcl_yoy_pct"]=round(pct_change(walcl[-1],walcl[-w26-1]),2)
        s["walcl_current"]=round(walcl[-1]/1e6,2)
    else:
        s["walcl_trend"]=50.0; s["walcl_yoy_pct"]=0.0; s["walcl_current"]=8.0

    if len(stbl)>=2:
        s["stable_trend"]=clamp(100-trend_score(stbl,min(90,len(stbl)-1)))
        s["stable_current_B"]=round(stbl[-1]/1e9,1)
    else:
        s["stable_trend"]=50.0; s["stable_current_B"]=150.0

    s["btc_risk_on"]=trend_score(btc,min(60,len(btc)-1)) if len(btc)>=2 else 50.0

    if dxy_series and len(dxy_series)>=2:
        dxy=[safe_float(v) for v in dxy_series if v and safe_float(v)>0]
        s["dxy_trend"]=trend_score(dxy,min(26,len(dxy)-1)) if len(dxy)>=2 else 50.0
    else: s["dxy_trend"]=50.0

    if us10y_series and len(us10y_series)>=2:
        us10y=[safe_float(v) for v in us10y_series if v and safe_float(v)>0]
        s["yield_trend"]=trend_score(us10y,min(26,len(us10y)-1)) if len(us10y)>=2 else 50.0
    else: s["yield_trend"]=50.0

    gd=global_data or {}
    dom=safe_float(gd.get("btc_dominance",50.0))
    s["btc_dom_macro"]=btc_dominance_to_score(dom)
    s["btc_dominance_pct"]=round(dom,1)

    weights={
        "walcl_trend":0.30,"stable_trend":0.22,"btc_risk_on":0.18,
        "dxy_trend":0.10,"yield_trend":0.10,"btc_dom_macro":0.10,
    }
    s["macro_score"]=_weighted(s,weights)
    return s

def compute_combined(btc_score,eth_score,macro_score):
    btc=clamp(safe_float(btc_score,50.0))
    eth=clamp(safe_float(eth_score,50.0))
    macro=clamp(safe_float(macro_score,50.0))
    combined=clamp(btc*0.45+eth*0.30+macro*0.25)
    if combined<28:
        phase="Accumulation";color="#22c55e"
        desc="Market undervalued. Smart money accumulating. Extreme fear elevated."
    elif combined<55:
        phase="Bull Market";color="#3b82f6"
        desc="Uptrend confirmed. Liquidity expanding. Momentum building."
    elif combined<72:
        phase="Distribution";color="#f59e0b"
        desc="Market overheating. FOMO elevated. Whales distributing supply."
    else:
        phase="Bear Market";color="#ef4444"
        desc="Risk-off. Liquidity contracting. Downtrend confirmed."
    return {
        "combined_score":round(combined,1),
        "btc_weight":0.45,"eth_weight":0.30,"macro_weight":0.25,
        "phase":phase,"phase_color":color,"phase_desc":desc,
    }

def _weighted(scores,weights):
    tw=ts=0.0
    for k,w in weights.items():
        v=scores.get(k)
        if v is None: continue
        ts+=safe_float(v,50.0)*w; tw+=w
    return round(clamp(ts/tw),1) if tw else 50.0
