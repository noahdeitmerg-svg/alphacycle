"""
Generate placeholder btc_daily_kraken.csv (3727 rows, 2013-10-06 to 2023-12-31).
Run from backend/: python scripts/gen_btc_csv.py
Replace with official Kraken export for production if available.
"""
import csv
from datetime import datetime, timedelta
from pathlib import Path

OUT = Path(__file__).resolve().parent.parent / "data" / "btc_daily_kraken.csv"
START = datetime(2013, 10, 6)
ROWS = 3727  # through 2023-12-31

def main():
    OUT.parent.mkdir(parents=True, exist_ok=True)
    p0, p1 = 122.0, 42000.0
    with open(OUT, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["timestamp", "open", "high", "low", "close", "volume", "trades"])
        for i in range(ROWS):
            dt = START + timedelta(days=i)
            ts = int(dt.timestamp())
            t = i / (ROWS - 1) if ROWS > 1 else 1.0
            close = p0 + (p1 - p0) * (t ** 0.5)
            o, h, l = close * 0.998, close * 1.01, close * 0.99
            vol = 100.0 + (i % 1000)
            w.writerow([ts, round(o, 2), round(h, 2), round(l, 2), round(close, 2), round(vol, 1), 100])
    print(f"Wrote {ROWS} rows to {OUT}")

if __name__ == "__main__":
    main()
