import time
import pandas as pd


def get_trend_data(keywords: list[str], timeframe: str = "today 12-m") -> dict:
    """Fetch Google Trends interest over time for up to 5 keywords.
    Returns dict: {keyword: {"score": 0-100, "direction": "up/down/stable", "data": [...]} }
    """
    try:
        from pytrends.request import TrendReq
    except ImportError:
        return {}

    if not keywords:
        return {}

    # Pytrends max 5 keywords at once
    keywords = [k[:100] for k in keywords[:5]]

    try:
        pt = TrendReq(hl="en-US", tz=360, timeout=(10, 25), retries=2, backoff_factor=0.5)
        pt.build_payload(keywords, timeframe=timeframe, geo="")
        df = pt.interest_over_time()

        if df.empty:
            return {}

        results = {}
        for kw in keywords:
            if kw not in df.columns:
                continue
            series = df[kw].dropna()
            if len(series) < 4:
                continue

            current  = series.iloc[-4:].mean()   # last 4 weeks avg
            previous = series.iloc[-12:-4].mean() # prior 8 weeks avg
            peak     = series.max()

            if previous > 0:
                pct_change = (current - previous) / previous * 100
            else:
                pct_change = 0

            if pct_change > 15:
                direction = "up"
                arrow = "📈"
            elif pct_change < -15:
                direction = "down"
                arrow = "📉"
            else:
                direction = "stable"
                arrow = "➡️"

            results[kw] = {
                "score":     round(float(current), 1),
                "peak":      round(float(peak), 1),
                "pct_change": round(float(pct_change), 1),
                "direction": direction,
                "arrow":     arrow,
                "weekly":    series.tolist()[-24:],   # last 24 weeks
                "dates":     [str(d)[:10] for d in series.index[-24:]],
            }

        return results

    except Exception as e:
        print(f"  Trends error: {e}")
        return {}


def trend_label(direction: str, pct: float) -> str:
    """Return a short human-readable label."""
    if direction == "up":
        return f"+{pct:.0f}% creciendo"
    elif direction == "down":
        return f"{pct:.0f}% bajando"
    return "estable"
