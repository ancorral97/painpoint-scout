import time
import pandas as pd

# Simple Spanish → English translations for common niches
# Claude generates niches in Spanish so we map them to English for Google Trends
ES_EN = {
    "gestión de facturas": "invoice management",
    "gestion de facturas": "invoice management",
    "automatización de tareas": "task automation",
    "productividad personal": "personal productivity",
    "onboarding remoto": "remote onboarding",
    "herramientas para freelancers": "freelance tools",
    "marketing de contenidos": "content marketing",
    "gestión de clientes": "client management",
    "facturación electrónica": "electronic invoicing",
    "salud mental": "mental health",
    "finanzas personales": "personal finance",
    "educación en línea": "online education",
    "comercio electrónico": "ecommerce",
    "inteligencia artificial": "artificial intelligence",
    "automatización de marketing": "marketing automation",
    "gestión de proyectos": "project management",
    "trabajo remoto": "remote work",
    "redes sociales": "social media",
    "programación sin código": "no code",
    "aplicaciones móviles": "mobile apps",
    "seguridad digital": "cybersecurity",
    "control de consumo compulsivo": "screen time management",
    "adicción digital": "digital addiction",
    "detección de contenido generado por ia": "ai content detection",
    "productividad con salud mental": "mental health productivity",
    "mentoría para emprendedores novatos": "startup mentorship",
    "posicionamiento agencia": "agency positioning",
    "posicionamiento de agencia": "agency positioning",
}


def translate_niche(niche: str) -> str:
    """Translate a Spanish niche to English for better Google Trends results."""
    lower = niche.lower().strip()
    # Direct match
    if lower in ES_EN:
        return ES_EN[lower]
    # Partial match
    for es, en in ES_EN.items():
        if es in lower or lower in es:
            return en
    # If it looks like it's already English (no Spanish chars), keep it
    spanish_chars = set("áéíóúñüàèì¿¡")
    if not any(c in lower for c in spanish_chars) and len(lower.split()) <= 4:
        return niche
    # Fallback: return as-is (Google Trends handles some Spanish)
    return niche


def get_trend_data(keywords: list[str], timeframe: str = "today 12-m") -> dict:
    """Fetch Google Trends interest over time for up to 5 keywords.
    Auto-translates Spanish niches to English for better results.
    Returns dict keyed by ORIGINAL keyword (for display), data in English search term.
    """
    try:
        from pytrends.request import TrendReq
    except ImportError:
        return {}

    if not keywords:
        return {}

    keywords = keywords[:5]

    # Build translation map: original → english search term
    translation = {kw: translate_niche(kw) for kw in keywords}
    en_keywords  = list(translation.values())[:5]

    try:
        pt = TrendReq(hl="en-US", tz=360, timeout=(15, 30))
        pt.build_payload(en_keywords, timeframe=timeframe, geo="")
        df = pt.interest_over_time()

        if df.empty:
            # Try one keyword at a time as fallback
            results = {}
            for orig_kw, en_kw in translation.items():
                try:
                    pt2 = TrendReq(hl="en-US", tz=360, timeout=(15, 30))

                    pt2.build_payload([en_kw], timeframe=timeframe, geo="")
                    df2 = pt2.interest_over_time()
                    if not df2.empty and en_kw in df2.columns:
                        series = df2[en_kw].dropna()
                        results[orig_kw] = _build_result(series, en_kw)
                    time.sleep(1)
                except Exception:
                    continue
            return results

        results = {}
        for orig_kw, en_kw in translation.items():
            if en_kw not in df.columns:
                continue
            series = df[en_kw].dropna()
            if len(series) < 2:
                continue
            results[orig_kw] = _build_result(series, en_kw)

        return results

    except Exception as e:
        print(f"  Trends error: {e}")
        return {}


def _build_result(series: pd.Series, en_kw: str) -> dict:
    """Build result dict from a pandas Series of trend data."""
    current  = series.iloc[-4:].mean() if len(series) >= 4 else series.mean()
    previous = series.iloc[-12:-4].mean() if len(series) >= 12 else series.iloc[:len(series)//2].mean()
    peak     = series.max()

    pct_change = ((current - previous) / previous * 100) if previous > 0 else 0

    if pct_change > 15:
        direction, arrow = "up", "📈"
    elif pct_change < -15:
        direction, arrow = "down", "📉"
    else:
        direction, arrow = "stable", "➡️"

    return {
        "score":      round(float(current), 1),
        "peak":       round(float(peak), 1),
        "pct_change": round(float(pct_change), 1),
        "direction":  direction,
        "arrow":      arrow,
        "weekly":     series.tolist()[-24:],
        "dates":      [str(d)[:10] for d in series.index[-24:]],
        "en_term":    en_kw,   # show what was actually searched
    }


def trend_label(direction: str, pct: float) -> str:
    if direction == "up":
        return f"+{pct:.0f}% creciendo"
    elif direction == "down":
        return f"{pct:.0f}% bajando"
    return "estable"
