"""
BTC seasonal patterns — monthly average return bias (informational only).
Does not affect ARC score or decision engine.
"""
from datetime import datetime

MONTHLY_BIAS = {
    1:  +8.2,
    2:  +14.1,
    3:  +9.3,
    4:  +18.7,
    5:  -6.2,
    6:  -8.1,
    7:  +7.4,
    8:  +3.2,
    9:  -5.8,
    10: +21.4,
    11: +26.3,
    12: +4.7,
}


def get_seasonal_context():
    now = datetime.utcnow()
    month = now.month
    bias = MONTHLY_BIAS[month]
    if bias > 10:
        label = "Historically Strong"
        color = "#00D4AA"
    elif bias > -5:
        label = "Historically Neutral"
        color = "#6b7280"
    else:
        label = "Historically Weak"
        color = "#FF9500"
    next_month = (month % 12) + 1
    return {
        "month": month,
        "month_name": now.strftime("%B"),
        "avg_return": bias,
        "label": label,
        "color": color,
        "next_month_return": MONTHLY_BIAS[next_month],
    }
