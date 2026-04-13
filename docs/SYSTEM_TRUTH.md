# AlphaCycle — SYSTEM TRUTH
# Immutable Rules · Extracted from Production Code · ARC v1.2

> **These rules are LOCKED. No AI agent may modify them without explicit approval from Noah + version bump.**

---

## 1. ARC FORMULA (LOCKED)

```
ARC = ma_200w × 0.35 + drawdown × 0.30 + liquidity × 0.15 + fear_greed × 0.20
```

**Source:** `backend/arc_config.py` → `ARC_WEIGHTS`
**Version:** ARC v1.2 (`ARC_FORMULA_VERSION` in `backend/arc_config.py`)
**Constraint:** `sum(ARC_WEIGHTS.values()) == 1.0` — enforced by `assert_weights_sum()` on import

```python
ARC_WEIGHTS = {
    "trend":     0.35,
    "drawdown":  0.30,
    "liquidity": 0.15,
    "sentiment": 0.20,
}
```

---

## 2. EXTREME CONDITION BOOST (ECB)

**Source:** `backend/scoring.py` → `compute_arc_score()` lines 453–461

| Condition | Boost |
|---|---|
| `trend > 78` AND `sentiment > 82` | +7 |
| `trend > 72` AND `sentiment > 75` | +3 |
| `drawdown < 18` AND `sentiment < 15` | −7 |
| `drawdown < 25` AND `sentiment < 20` | −3 |

- Single extreme signals do NOT trigger a boost
- Result clamped to 0–100 after boost
- ECB is part of the locked ARC methodology — version tracked in `arc_config`

---

## 3. DISPLAY TRANSFORM

**Source:** `backend/scoring.py` → `arc_display_score(arc_raw, k=0.0)`

```python
def arc_display_score(arc_raw: float, k: float = 0.0) -> float:
    x = (arc_raw - 50.0) / 50.0
    stretched = x * (1.0 + k * x * x)
    return clamp(50.0 + stretched * 50.0)
```

- **Default `k=0`:** UI/API display equals raw ARC (no stretch). Optional `k > 0` keeps the legacy sigmoid-style stretch for special cases only.
- Internal ARC math uses `arc_raw`. Hero zone **name** uses raw `arc_score` in `index.html`; gauge number uses `arc_display` (same as raw when k=0).
- Zone bands for API / HR “YOU ARE HERE” / zone history follow raw score rules in `permanent-fixes.mdc` and `AI_MASTER_CONTEXT.md` (Boundary Implementation).

---

## 4. ZONE BOUNDARIES (LOCKED)

**Source:** `backend/arc_config.py` → `ARC_ZONES`

| Zone | Range | Operator | Color |
|---|---|---|---|
| Deep Value | 0–29 | `< 30` | #00DC78 |
| Accumulation | 30–39 | `< 40` | #00B4D8 |
| Expansion | 40–59 | `< 60` | #58A6FF |
| Risk Rising | 60–69 | `< 70` | #FF9500 |
| Euphoria | 70–100 | `>= 70` | #FF3B3B |

**All zone functions must use `< 30 / < 40 / < 60 / < 70`:**
`arc_config.get_zone()`, `get_zone_name()`, `_phase_label()`, `phaseOf()`, `scoreColor()`, `renderDecisionInterpretation()`, `get_position()`

---

## 5. SINGLE ARC SOURCE

`compute_arc_score()` is the ONLY valid ARC calculation.

**NEVER** derive ARC from: `combined_score`, `alpha_cycle_position`, analyzer outputs.

---

## 6. SINGLE BACKTEST SOURCE

`run_daily_backtest_full()` is the ONLY authoritative backtest.

`run_backtest()` and `run_daily_backtest()` are **DELETED**. No weekly fallback.

---

## 7. DECISION ENGINE

```python
if a < 30: return "BUY"        → display: "EARLY CYCLE"
if a < 40: return "ACCUMULATE" → display: "ACCUMULATION PHASE"
if a < 60: return "HOLD"       → display: "MID CYCLE"
if a < 70: return "REDUCE"     → display: "ELEVATED RISK"
else:      return "SELL"       → display: "EXTREME RISK"
```

---

## 8. LIQUIDITY IMPULSE MODEL

```
Impulse Score = 50.0 − (30d_change × 2.5) − (90d_change × 1.5)
```

Net Liquidity = WALCL − TGA − RRP. Requires ≥22 data points. FRED updates weekly (Thursday).

---

## 9. HI/LO ENGINE

When daily high/low are passed into `compute_arc_score` (`weekly_high` / `weekly_low` parameters): MA and drawdown components can use those extremes. **Live:** `fetch_kraken_ohlc_latest()` → `CACHE["ohlc_latest"]` → same parameters for parity with `run_daily_backtest_full()`.

---

## 10. LANGUAGE RULES

| FORBIDDEN | REQUIRED |
|---|---|
| BUY / SELL | EARLY CYCLE / EXTREME RISK |
| SIGNAL | PHASE / REGIME |
| PREDICTED | CLASSIFIED |
| 10/10 / 6/6 | "All major transitions classified" |

**Exception:** "Bottom Formation Signal" (technical indicator name)

---

## 11. METHODOLOGY GOVERNANCE

Changes require: research justification → backtest evaluation → public documentation → version bump (e.g. v1.1 → v1.2). Must preserve historical reproducibility.

---

*ARC Version: v1.2 · Last verified: 2026-04-12*
