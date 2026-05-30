import os
import json
import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from sqlalchemy import func
from database import Session, PainPoint, init_db
from scraper import run_scraper, SUBREDDITS, mark_trending
from analyzer import run_analyzer

st.set_page_config(
    page_title="PainPoint Scout",
    page_icon="🔍",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Design System ─────────────────────────────────────────────────────────────
st.markdown("""
<style>
  /* ── Global ── */
  @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');
  html, body, [class*="css"] { font-family: 'Inter', sans-serif; }
  .main .block-container { padding: 2rem 2.5rem 3rem; max-width: 1280px; }

  /* ── Sidebar ── */
  [data-testid="stSidebar"] {
    background: #0a0a0f !important;
    border-right: 1px solid #1e1e2e;
  }
  [data-testid="stSidebar"] label,
  [data-testid="stSidebar"] .stMarkdown p { color: #94a3b8 !important; font-size: 13px; }

  /* ── Metric cards ── */
  .metric-row { display: flex; gap: 16px; margin-bottom: 32px; }
  .metric-card {
    flex: 1; background: #0f0f1a; border: 1px solid #1e2035;
    border-radius: 14px; padding: 20px 24px;
    display: flex; flex-direction: column; gap: 6px;
  }
  .metric-label { font-size: 12px; font-weight: 600; color: #64748b; letter-spacing: .06em; text-transform: uppercase; }
  .metric-value { font-size: 32px; font-weight: 700; color: #f1f5f9; line-height: 1; }
  .metric-sub   { font-size: 12px; color: #475569; }

  /* ── Section headers ── */
  .section-header {
    font-size: 13px; font-weight: 700; color: #64748b;
    letter-spacing: .08em; text-transform: uppercase;
    margin: 0 0 16px; padding-bottom: 10px;
    border-bottom: 1px solid #1e2035;
  }

  /* ── Opportunity card ── */
  .opp-card {
    background: #0f0f1a; border: 1px solid #1e2035;
    border-radius: 16px; padding: 22px 26px;
    margin-bottom: 14px; position: relative;
    transition: border-color .2s;
  }
  .opp-card:hover { border-color: #334155; }
  .opp-score {
    position: absolute; top: 22px; right: 26px;
    font-size: 13px; font-weight: 700;
    padding: 4px 12px; border-radius: 20px;
  }
  .opp-title {
    font-size: 15px; font-weight: 600; color: #e2e8f0;
    line-height: 1.5; margin-bottom: 12px; padding-right: 80px;
  }
  .opp-meta {
    font-size: 12px; color: #475569; margin-bottom: 14px;
    display: flex; gap: 14px; flex-wrap: wrap; align-items: center;
  }
  .opp-meta span { display: flex; align-items: center; gap: 4px; }
  .badge {
    display: inline-flex; align-items: center; gap: 4px;
    border-radius: 6px; padding: 3px 9px;
    font-size: 11px; font-weight: 600; margin-right: 6px; margin-bottom: 6px;
  }
  .b-cat  { background: #1e1b4b; color: #a5b4fc; border: 1px solid #312e81; }
  .b-size { background: #052e16; color: #86efac; border: 1px solid #14532d; }
  .b-comp { background: #2d1515; color: #fca5a5; border: 1px solid #7f1d1d; }
  .b-mono { background: #0c1a2e; color: #7dd3fc; border: 1px solid #0c4a6e; }
  .b-niche{ background: #1a1a2e; color: #c4b5fd; border: 1px solid #4c1d95; }
  .b-trending { background: #1a0f00; color: #fb923c; border: 1px solid #7c2d12; }
  .b-opp { background: #1a0a2e; color: #a78bfa; border: 1px solid #4c1d95; }

  .divider-label {
    font-size: 12px; font-weight: 600; color: #64748b;
    letter-spacing: .06em; text-transform: uppercase;
    margin: 6px 0 4px;
  }
  .field-block { margin-bottom: 10px; }
  .field-title { font-size: 11px; font-weight: 600; color: #475569; text-transform: uppercase; letter-spacing: .06em; margin-bottom: 3px; }
  .field-body  { font-size: 13.5px; color: #cbd5e1; line-height: 1.6; }
  .field-solution { font-size: 13.5px; color: #a78bfa; line-height: 1.6; }
  .field-mono     { font-size: 13.5px; color: #7dd3fc; line-height: 1.6; }

  .opp-footer {
    margin-top: 14px; padding-top: 12px;
    border-top: 1px solid #1e2035;
    display: flex; justify-content: space-between; align-items: center;
  }
  .view-link {
    font-size: 12px; color: #6366f1; text-decoration: none; font-weight: 500;
  }
  .view-link:hover { color: #818cf8; }

  /* ── Chart container ── */
  .chart-card {
    background: #0f0f1a; border: 1px solid #1e2035;
    border-radius: 14px; padding: 20px 20px 10px;
  }

  /* ── Streamlit overrides ── */
  div[data-testid="stMetric"] { background: transparent !important; }
  .stButton > button {
    border-radius: 8px !important; font-weight: 600 !important;
    font-size: 13px !important; padding: 8px 0 !important;
    transition: all .15s !important;
  }
  div[data-testid="stSelectbox"] > div,
  div[data-testid="stMultiSelect"] > div { border-radius: 8px !important; }
  .stSlider > div > div > div { border-radius: 4px !important; }
  [data-testid="stExpander"] { background: #0f0f1a !important; border: 1px solid #1e2035 !important; border-radius: 10px !important; }

  @media (max-width: 768px) {
    .main .block-container { padding: 1rem !important; }
    .metric-row { flex-direction: column; gap: 8px; }
    .opp-card { padding: 14px 16px; }
    .opp-score { position: static; margin-bottom: 8px; display: inline-block; }
    .opp-title { padding-right: 0; }
  }
</style>
""", unsafe_allow_html=True)


# ── Helpers ───────────────────────────────────────────────────────────────────

def check_setup() -> list[dict]:
    """Returns list of setup items with status."""
    import os
    items = []
    # Check API key
    has_key = bool(os.environ.get("ANTHROPIC_API_KEY", ""))
    items.append({"label": "Anthropic API Key", "ok": has_key, "fix": "Agrega ANTHROPIC_API_KEY a tu .env"})
    # Check data
    init_db()
    s = Session()
    count = s.query(func.count(PainPoint.id)).scalar() or 0
    s.close()
    items.append({"label": f"Datos scrapeados ({count} posts)", "ok": count > 0, "fix": "Haz click en 🚀 Buscar Oportunidades"})
    analyzed_s = Session()
    a_count = analyzed_s.query(func.count(PainPoint.id)).filter(PainPoint.analyzed == 1).scalar() or 0
    analyzed_s.close()
    items.append({"label": f"Posts analizados ({a_count} de {count})", "ok": a_count > 0, "fix": "Haz click en 🚀 Buscar Oportunidades"})
    return items


@st.cache_data(ttl=60)
def get_last_updated():
    init_db()
    s = Session()
    latest = s.query(func.max(PainPoint.scraped_at)).scalar()
    s.close()
    if latest:
        from datetime import datetime, timezone
        diff = datetime.utcnow() - latest
        if diff.days > 0:
            return f"Última actualización: hace {diff.days} días"
        elif diff.seconds > 3600:
            return f"Última actualización: hace {diff.seconds // 3600}h"
        else:
            return f"Última actualización: hace {diff.seconds // 60} min"
    return "Sin datos aún"


def parse_extra(s: str) -> tuple[str, dict]:
    if s and "|||" in s:
        parts = s.split("|||", 1)
        try:
            return parts[0].strip(), json.loads(parts[1])
        except Exception:
            return s, {}
    return (s or ""), {}


def urgency_color(score: float) -> str:
    if score >= 7:   return "#ef4444"
    if score >= 4.5: return "#f97316"
    return "#eab308"


SOURCE_META = {
    "hackernews":     {"icon": "🟡", "label": "Hacker News",    "bg": "#1c1a00", "color": "#fbbf24", "border": "#92400e"},
    "youtube_shorts": {"icon": "🔴", "label": "YouTube Shorts", "bg": "#1f0000", "color": "#f87171", "border": "#7f1d1d"},
    "youtube_videos": {"icon": "▶️", "label": "YouTube Videos", "bg": "#1a0a0a", "color": "#fca5a5", "border": "#991b1b"},
    "producthunt":    {"icon": "🟠", "label": "Product Hunt",   "bg": "#1a0a00", "color": "#ff6154", "border": "#7c2d12"},
    "twitter":        {"icon": "🐦", "label": "Twitter / X",   "bg": "#00101a", "color": "#38bdf8", "border": "#0c4a6e"},
}

def source_badge(source: str) -> str:
    if source.startswith("r/"):
        sub = source
        return (f'<span style="display:inline-flex;align-items:center;gap:5px;'
                f'background:#1a0f00;border:1px solid #7c2d12;color:#fb923c;'
                f'border-radius:6px;padding:3px 10px;font-size:12px;font-weight:600">'
                f'🟠 Reddit &nbsp;<span style="color:#9a3412;font-weight:400">{sub}</span></span>')
    m = SOURCE_META.get(source, {"icon": "📡", "label": source, "bg": "#111", "color": "#94a3b8", "border": "#334155"})
    return (f'<span style="display:inline-flex;align-items:center;gap:5px;'
            f'background:{m["bg"]};border:1px solid {m["border"]};color:{m["color"]};'
            f'border-radius:6px;padding:3px 10px;font-size:12px;font-weight:600">'
            f'{m["icon"]} {m["label"]}</span>')


def toggle_favorite(post_id: str, current: int):
    session = Session()
    pp = session.get(PainPoint, post_id)
    if pp:
        pp.favorite = 0 if current else 1
        session.commit()
    session.close()
    st.cache_data.clear()


@st.cache_data(ttl=30)
def load_data():
    init_db()
    session = Session()
    rows = session.query(PainPoint).filter(PainPoint.analyzed == 1).all()
    session.close()
    if not rows:
        return pd.DataFrame()
    records = []
    for r in rows:
        sol, extra = parse_extra(r.solution_suggestion)
        records.append({
            "id": r.id, "source": r.source, "title": r.title, "url": r.url,
            "upvotes": r.upvotes or 0, "num_comments": r.num_comments or 0,
            "created_at": r.created_at, "is_pain_point": r.is_pain_point,
            "category": r.category or "other",
            "urgency_score": r.urgency_score or 0,
            "opportunity_score": r.opportunity_score or 0,
            "trending": r.trending or 0,
            "favorite": r.favorite or 0,
            "problem_summary": r.problem_summary or "",
            "solution": sol,
            "niche":        extra.get("niche", ""),
            "market_size":  extra.get("market_size", ""),
            "who":          extra.get("who", ""),
            "monetization": extra.get("monetization", ""),
            "competition":  extra.get("competition", ""),
        })
    return pd.DataFrame(records)


@st.cache_data(ttl=30)
def get_counts():
    init_db()
    session = Session()
    total    = session.query(func.count(PainPoint.id)).scalar() or 0
    analyzed = session.query(func.count(PainPoint.id)).filter(PainPoint.analyzed == 1).scalar() or 0
    pain     = session.query(func.count(PainPoint.id)).filter(PainPoint.is_pain_point == 1).scalar() or 0
    pending  = session.query(func.count(PainPoint.id)).filter(PainPoint.analyzed == 0).scalar() or 0
    session.close()
    return total, analyzed, pain, pending


CHART_THEME = dict(
    paper_bgcolor="rgba(0,0,0,0)",
    plot_bgcolor="rgba(0,0,0,0)",
    font=dict(color="#94a3b8", size=12),
    margin=dict(l=0, r=0, t=36, b=0),
    height=260,
)


# ── Sidebar ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("""
    <div style="padding: 8px 0 20px">
      <div style="font-size:20px;font-weight:700;color:#f1f5f9;margin-bottom:4px">🔍 PainPoint Scout</div>
      <div style="font-size:12px;color:#475569">Business opportunity finder</div>
    </div>
    """, unsafe_allow_html=True)

    st.markdown('<div class="section-header">Fuentes</div>', unsafe_allow_html=True)

    inc_reddit     = st.toggle("🟠 Reddit",          value=True)
    inc_hn         = st.toggle("🟡 Hacker News",     value=True)
    inc_yt_shorts  = st.toggle("🔴 YouTube Shorts",  value=False)
    inc_yt_videos  = st.toggle("▶️ YouTube Videos",  value=False)
    inc_ph         = st.toggle("🟠 Product Hunt",    value=False)
    st.caption("🐦 Twitter/X — requiere plan de pago ($100/mes). No disponible.")

    selected_subs = []
    if inc_reddit:
        selected_subs = st.multiselect(
            "Subreddits",
            SUBREDDITS,
            default=["entrepreneur", "smallbusiness", "productivity", "SaaS"],
            placeholder="Selecciona subreddits...",
        )

    limit = st.slider("Posts por subreddit", 20, 200, 75, 5)

    run_btn = st.button("🚀 Buscar Oportunidades", use_container_width=True, type="primary")

    if run_btn:
        try:
            # ── Step 1: Scrape ──
            status = st.empty()
            status.info("⏳ Paso 1/2 — Scrapeando fuentes...")
            results = run_scraper(
                subreddits=selected_subs,
                limit=limit,
                include_reddit=inc_reddit,
                include_hn=inc_hn,
                include_yt_shorts=inc_yt_shorts,
                include_yt_videos=inc_yt_videos,
                include_ph=inc_ph,
            )
            new_posts = sum(results.values())
            st.cache_data.clear()

            # ── Step 2: Analyze ──
            _, _, _, pending_count = get_counts()
            if pending_count == 0:
                status.success(f"✓ {new_posts} posts nuevos — nada pendiente de analizar")
            else:
                status.info(f"⏳ Paso 2/2 — Analizando {pending_count} posts con Claude AI...")
                prog_bar  = st.progress(0)
                prog_text = st.empty()

                def on_progress(done, total, title):
                    prog_bar.progress(done / total)
                    prog_text.caption(f"({done}/{total}) {title}...")

                pain_found = run_analyzer(batch_size=min(50, pending_count), progress_callback=on_progress)
                prog_bar.empty()
                prog_text.empty()

                # Mark trending after analysis
                mark_trending()

                _, _, _, still_pending = get_counts()
                status.success(
                    f"✓ {new_posts} posts nuevos · {pain_found} oportunidades identificadas"
                    + (f" · {still_pending} pendientes" if still_pending else "")
                )
                st.cache_data.clear()
        except Exception as _e:
            st.error(f"❌ Error durante el scraping/análisis: {_e}\n\nVerifica tu ANTHROPIC_API_KEY y conexión a internet.")

    st.markdown('<div class="section-header" style="margin-top:24px">Filtros</div>', unsafe_allow_html=True)

    # Source filter — pre-populated from active toggles above
    active_sources = []
    if inc_reddit:    active_sources.append("Reddit")
    if inc_hn:        active_sources.append("Hacker News")
    if inc_yt_shorts: active_sources.append("YouTube Shorts")
    if inc_yt_videos: active_sources.append("YouTube Videos")
    if inc_ph:        active_sources.append("Product Hunt")

    source_filter = st.multiselect(
        "Fuente",
        ["Reddit", "Hacker News", "YouTube Shorts", "YouTube Videos", "Product Hunt"],
        default=active_sources,
        placeholder="Todas las fuentes",
    )
    categories = ["productivity","finance","health","tech","social",
                  "education","ecommerce","hr","legal","marketing","other"]
    category_filter = st.multiselect("Categoría", categories, placeholder="Todas")
    market_filter   = st.multiselect("Tamaño de mercado", ["small","medium","large"], placeholder="Cualquiera")
    comp_filter     = st.multiselect("Competencia", ["none","low","medium","high"], placeholder="Cualquiera")
    min_urgency     = st.slider("Urgencia mínima", 0.0, 10.0, 5.0, 0.5)
    min_upvotes     = st.number_input("Upvotes mínimos", 0, 10000, 0, step=10)

    st.markdown('<div class="section-header" style="margin-top:24px">Display</div>', unsafe_allow_html=True)
    only_pain = st.toggle("Pain points only", value=True)
    sort_by   = st.selectbox("Sort by", ["Opportunity Score", "Urgency score", "Upvotes", "Comments"], label_visibility="collapsed")

    st.markdown("---")
    _sb_total, _sb_analyzed, _sb_pain, _sb_pending = get_counts()
    st.markdown(f"""
<div style="font-size:11px;color:#475569;padding:8px 0">
  <div style="margin-bottom:4px">📊 <strong style="color:#64748b">{_sb_total:,}</strong> posts scrapeados</div>
  <div style="margin-bottom:4px">🔥 <strong style="color:#a78bfa">{_sb_pain:,}</strong> oportunidades</div>
  <div>⏳ <strong style="color:#64748b">{_sb_pending:,}</strong> pendientes</div>
</div>
""", unsafe_allow_html=True)


# ── Header ────────────────────────────────────────────────────────────────────
total, analyzed, pain, pending = get_counts()

st.markdown("""
<div style="margin-bottom:8px">
  <h1 style="font-size:28px;font-weight:700;color:#f1f5f9;margin:0 0 4px">
    Business Opportunity Finder
  </h1>
  <p style="color:#475569;font-size:14px;margin:0">
    Real complaints from Reddit, Hacker News & Product Hunt, analyzed by AI to surface product opportunities
  </p>
</div>
""", unsafe_allow_html=True)
st.caption(f"🕐 {get_last_updated()}")

# ── Setup checklist ───────────────────────────────────────────────────────────
setup_items = check_setup()
if not all(i["ok"] for i in setup_items):
    with st.expander("⚙️ Guía de inicio rápido", expanded=True):
        for item in setup_items:
            icon = "✅" if item["ok"] else "❌"
            if item["ok"]:
                st.markdown(f"{icon} **{item['label']}**")
            else:
                st.markdown(f"{icon} **{item['label']}** — _{item['fix']}_")

# Metrics
hit_rate = f"{pain/analyzed*100:.0f}%" if analyzed else "—"
st.markdown(f"""
<div class="metric-row">
  <div class="metric-card">
    <div class="metric-label">Total Scraped</div>
    <div class="metric-value">{total:,}</div>
    <div class="metric-sub">{pending} pending analysis</div>
  </div>
  <div class="metric-card">
    <div class="metric-label">Analyzed</div>
    <div class="metric-value">{analyzed:,}</div>
    <div class="metric-sub">by Claude AI</div>
  </div>
  <div class="metric-card" style="border-color:#2d1b4e">
    <div class="metric-label">Opportunities</div>
    <div class="metric-value" style="color:#a78bfa">{pain:,}</div>
    <div class="metric-sub">real pain points found</div>
  </div>
  <div class="metric-card">
    <div class="metric-label">Hit Rate</div>
    <div class="metric-value">{hit_rate}</div>
    <div class="metric-sub">posts with clear need</div>
  </div>
</div>
""", unsafe_allow_html=True)

# ── Search bar ────────────────────────────────────────────────────────────────
search_query = st.text_input("🔍 Buscar...", placeholder="Buscar por título, nicho, problema... (filtra en tiempo real)")

# ── Load & filter data ────────────────────────────────────────────────────────
df = load_data()

if df.empty:
    _active_sources = []
    if inc_reddit:    _active_sources.append("🟠 Reddit (" + ", ".join(selected_subs[:3]) + ("..." if len(selected_subs) > 3 else "") + ")" if selected_subs else "🟠 Reddit")
    if inc_hn:        _active_sources.append("🟡 Hacker News")
    if inc_yt_shorts: _active_sources.append("🔴 YouTube Shorts")
    if inc_yt_videos: _active_sources.append("▶️ YouTube Videos")
    if inc_ph:        _active_sources.append("🟠 Product Hunt")
    if inc_twitter:   _active_sources.append("🐦 Twitter / X")
    _sources_html = "".join(
        f'<div style="margin:4px 0;color:#94a3b8">• {s}</div>'
        for s in _active_sources
    ) if _active_sources else '<div style="color:#475569">Ninguna fuente activa — activa al menos una en el sidebar.</div>'
    st.markdown(f"""
    <div style="background:#0f0f1a;border:1px dashed #1e2035;border-radius:16px;padding:48px 40px;max-width:600px;margin:0 auto">
      <div style="font-size:36px;margin-bottom:16px;text-align:center">🔍</div>
      <div style="font-size:18px;font-weight:700;color:#e2e8f0;margin-bottom:8px;text-align:center">Sin datos todavía</div>
      <div style="color:#475569;font-size:14px;margin-bottom:24px;text-align:center">Sigue estos pasos para encontrar oportunidades de negocio:</div>
      <div style="background:#080810;border-radius:10px;padding:16px 20px;margin-bottom:12px">
        <div style="font-size:12px;font-weight:700;color:#64748b;text-transform:uppercase;letter-spacing:.06em;margin-bottom:10px">Pasos</div>
        <div style="color:#94a3b8;font-size:13px;margin-bottom:8px">1️⃣ Asegúrate de tener <strong style="color:#a78bfa">ANTHROPIC_API_KEY</strong> en tu <code>.env</code></div>
        <div style="color:#94a3b8;font-size:13px;margin-bottom:8px">2️⃣ Activa las fuentes que quieras en el sidebar (Reddit, Hacker News, etc.)</div>
        <div style="color:#94a3b8;font-size:13px;margin-bottom:8px">3️⃣ Haz click en <strong style="color:#a78bfa">🚀 Buscar Oportunidades</strong> en el sidebar</div>
        <div style="color:#94a3b8;font-size:13px">4️⃣ ¡Espera unos minutos mientras Claude AI analiza los posts!</div>
      </div>
      <div style="background:#080810;border-radius:10px;padding:14px 20px">
        <div style="font-size:12px;font-weight:700;color:#64748b;text-transform:uppercase;letter-spacing:.06em;margin-bottom:8px">Fuentes activas ahora</div>
        {_sources_html}
      </div>
    </div>
    """, unsafe_allow_html=True)
    st.stop()

flt = df[df["is_pain_point"] == 1].copy() if only_pain else df.copy()

# Source filter
if source_filter:
    masks = []
    if "Reddit"          in source_filter: masks.append(flt["source"].str.startswith("r/"))
    if "Hacker News"     in source_filter: masks.append(flt["source"] == "hackernews")
    if "YouTube Shorts"  in source_filter: masks.append(flt["source"] == "youtube_shorts")
    if "YouTube Videos"  in source_filter: masks.append(flt["source"] == "youtube_videos")
    if "Product Hunt"    in source_filter: masks.append(flt["source"] == "producthunt")
    if masks:
        import functools, operator
        combined = functools.reduce(operator.or_, masks)
        flt = flt[combined]

if category_filter: flt = flt[flt["category"].isin(category_filter)]
if market_filter:   flt = flt[flt["market_size"].isin(market_filter)]
if comp_filter:     flt = flt[flt["competition"].isin(comp_filter)]
flt = flt[flt["urgency_score"] >= min_urgency]
flt = flt[flt["upvotes"] >= min_upvotes]

# Search filter
if search_query:
    q = search_query.lower()
    mask = (
        flt["title"].str.lower().str.contains(q, na=False) |
        flt["problem_summary"].str.lower().str.contains(q, na=False) |
        flt["niche"].str.lower().str.contains(q, na=False) |
        flt["solution"].str.lower().str.contains(q, na=False)
    )
    flt = flt[mask]

sort_map = {
    "Opportunity Score": "opportunity_score",
    "Urgency score": "urgency_score",
    "Upvotes": "upvotes",
    "Comments": "num_comments",
}
flt = flt.sort_values(sort_map[sort_by], ascending=False)

# ── Charts ────────────────────────────────────────────────────────────────────
pain_df = df[df["is_pain_point"] == 1]

if not pain_df.empty:
    ch1, ch2, ch3 = st.columns(3)

    with ch1:
        cat = pain_df["category"].value_counts().reset_index()
        cat.columns = ["category", "count"]
        fig = px.bar(cat, x="count", y="category", orientation="h",
                     color="count", color_continuous_scale=["#312e81","#7c3aed","#a78bfa"])
        fig.update_layout(title=dict(text="By Category", font=dict(size=13, color="#94a3b8")),
                          showlegend=False, yaxis=dict(gridcolor="#1e2035"),
                          xaxis=dict(gridcolor="#1e2035"), **CHART_THEME)
        st.plotly_chart(fig, use_container_width=True)

    with ch2:
        urg = pain_df["urgency_score"]
        labels = ["High  7–10", "Mid  4–6", "Low  1–3"]
        vals   = [(urg >= 7).sum(), ((urg >= 4) & (urg < 7)).sum(), (urg < 4).sum()]
        fig2 = go.Figure(go.Pie(
            labels=labels, values=vals, hole=.6,
            marker_colors=["#ef4444","#f97316","#eab308"],
            textinfo="percent", textfont_size=12,
        ))
        fig2.update_layout(title=dict(text="Urgency Split", font=dict(size=13, color="#94a3b8")),
                           legend=dict(font=dict(color="#94a3b8", size=11)), **CHART_THEME)
        st.plotly_chart(fig2, use_container_width=True)

    with ch3:
        if "market_size" in pain_df.columns and pain_df["market_size"].any():
            ms = pain_df[pain_df["market_size"] != ""]["market_size"].value_counts().reset_index()
            ms.columns = ["size","count"]
            order = {"small":0,"medium":1,"large":2}
            ms["ord"] = ms["size"].map(order)
            ms = ms.sort_values("ord")
            fig3 = px.bar(ms, x="size", y="count",
                          color="size",
                          color_discrete_map={"small":"#0284c7","medium":"#7c3aed","large":"#059669"})
            fig3.update_layout(title=dict(text="Market Size", font=dict(size=13, color="#94a3b8")),
                               showlegend=False, xaxis=dict(gridcolor="#1e2035"),
                               yaxis=dict(gridcolor="#1e2035"), **CHART_THEME)
            st.plotly_chart(fig3, use_container_width=True)
        else:
            src = pain_df["source"].value_counts().reset_index()
            src.columns = ["source","count"]
            fig3 = px.bar(src.head(6), x="source", y="count",
                          color="count", color_continuous_scale=["#0c4a6e","#0284c7","#7dd3fc"])
            fig3.update_layout(title=dict(text="By Source", font=dict(size=13, color="#94a3b8")),
                               showlegend=False, xaxis=dict(gridcolor="#1e2035"),
                               yaxis=dict(gridcolor="#1e2035"), **CHART_THEME)
            st.plotly_chart(fig3, use_container_width=True)

    st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)

# ── Top niches strip ──────────────────────────────────────────────────────────
if not pain_df.empty and "niche" in pain_df.columns:
    niches = pain_df[pain_df["niche"] != ""]["niche"].value_counts().head(8)
    if not niches.empty:
        badges = "".join(
            f'<span style="background:#1a1a2e;border:1px solid #4c1d95;color:#c4b5fd;'
            f'border-radius:6px;padding:5px 12px;font-size:12px;font-weight:600;margin-right:8px">'
            f'#{n} <span style="color:#6d28d9;margin-left:4px">{c}</span></span>'
            for n, c in niches.items()
        )
        st.markdown(f"""
        <div style="background:#0f0f1a;border:1px solid #1e2035;border-radius:12px;padding:14px 18px;margin-bottom:24px">
          <div style="font-size:11px;font-weight:700;color:#64748b;letter-spacing:.08em;text-transform:uppercase;margin-bottom:10px">Top Niches</div>
          <div style="display:flex;flex-wrap:wrap;gap:4px">{badges}</div>
        </div>
        """, unsafe_allow_html=True)

# ── Results header ────────────────────────────────────────────────────────────
_col_title, _col_dl, _col_refresh = st.columns([5, 1, 1])
with _col_title:
    _label = "Pain Points" if only_pain else "Posts"
    st.markdown(f"""
<div style="padding-top:6px">
  <span style="font-size:18px;font-weight:700;color:#f1f5f9">{len(flt):,} {_label}</span>
  <span style="font-size:13px;color:#475569;margin-left:10px">encontrados · filtrados de {pain:,} oportunidades totales</span>
</div>
""", unsafe_allow_html=True)
with _col_dl:
    _export_cols = ["source","title","upvotes","category","niche","urgency_score","opportunity_score",
                    "market_size","competition","monetization","problem_summary","solution","url"]
    _export_cols = [c for c in _export_cols if c in flt.columns]
    st.download_button(
        "⬇️ CSV",
        flt.drop(columns=["id"], errors="ignore").to_csv(index=False),
        "painpoints.csv", "text/csv",
        use_container_width=True,
    )
with _col_refresh:
    if st.button("🔄", help="Actualizar datos", use_container_width=True):
        st.cache_data.clear()
        st.rerun()

# ── Tabs ──────────────────────────────────────────────────────────────────────
tab_all, tab_trending, tab_favorites, tab_niches = st.tabs(["🔥 Todas", "📈 Trending", "⭐ Favoritos", "🏷️ Por Nicho"])

# ── Pagination setup ──────────────────────────────────────────────────────────
PAGE_SIZE = 20
if "page" not in st.session_state:
    st.session_state.page = 0


def render_cards(df_view: pd.DataFrame, tab_key: str):
    """Render paginated cards for a given dataframe slice."""
    if df_view.empty:
        st.markdown("""
        <div style="background:#0f0f1a;border:1px solid #1e2035;border-radius:12px;padding:32px;text-align:center;color:#475569">
          No results match your filters. Try lowering the urgency score or removing some filters.
        </div>
        """, unsafe_allow_html=True)
        return

    total_pages = max(1, (len(df_view) + PAGE_SIZE - 1) // PAGE_SIZE)
    page_key = f"page_{tab_key}"
    if page_key not in st.session_state:
        st.session_state[page_key] = 0

    page = st.session_state[page_key]
    page = max(0, min(page, total_pages - 1))
    st.session_state[page_key] = page

    start = page * PAGE_SIZE
    end = start + PAGE_SIZE
    page_df = df_view.iloc[start:end]

    for _, row in page_df.iterrows():
        urg    = row.get("urgency_score") or 0
        opp    = row.get("opportunity_score") or 0
        color  = urgency_color(urg)
        niche  = row.get("niche", "")
        cat    = row.get("category", "")
        msize  = row.get("market_size", "")
        comp   = row.get("competition", "")
        mono   = row.get("monetization", "")
        who    = row.get("who", "")
        prob   = row.get("problem_summary", "")
        sol    = row.get("solution", "")
        is_trending = row.get("trending", 0)
        is_fav = row.get("favorite", 0)

        badges = ""
        if is_trending: badges += '<span class="badge b-trending">📈 TRENDING</span>'
        if cat:   badges += f'<span class="badge b-cat">📁 {cat}</span>'
        if niche: badges += f'<span class="badge b-niche">#{niche}</span>'
        if msize: badges += f'<span class="badge b-size">📊 {msize} market</span>'
        if comp:  badges += f'<span class="badge b-comp">⚔️ {comp} competition</span>'

        who_block  = f'<div class="field-block"><div class="field-title">Target User</div><div class="field-body">{who}</div></div>' if who else ""
        prob_block = f'<div class="field-block"><div class="field-title">Problem</div><div class="field-body">{prob}</div></div>' if prob else ""
        sol_block  = f'<div class="field-block"><div class="field-title">Solution Idea</div><div class="field-solution">{sol}</div></div>' if sol else ""
        mono_block = f'<div class="field-block"><div class="field-title">Monetization</div><div class="field-mono">{mono}</div></div>' if mono else ""

        score_html = f'🔥 {urg:.1f} / 10'
        if opp:
            score_html += f' &nbsp;<span style="background:#1a0a2e;color:#a78bfa;border:1px solid #4c1d95;border-radius:12px;padding:2px 8px;font-size:11px">⚡ {opp}</span>'

        st.markdown(f"""
<div class="opp-card" style="border-left: 4px solid {color}">
  <div class="opp-score" style="background:{color}18;color:{color};border:1px solid {color}40">
    {score_html}
  </div>

  <div class="opp-title">{row['title'][:140]}</div>

  <div style="margin-bottom:12px">{badges}</div>

  <div style="display:flex;align-items:center;gap:12px;margin-bottom:12px;flex-wrap:wrap">
    {source_badge(row['source'])}
    <span style="font-size:12px;color:#475569">⬆️ {int(row['upvotes'])} upvotes</span>
    <span style="font-size:12px;color:#475569">💬 {int(row['num_comments'])} comentarios</span>
  </div>

  <div style="background:#080810;border-radius:10px;padding:14px 16px;margin-bottom:4px">
    {who_block}{prob_block}{sol_block}{mono_block}
  </div>

  <div class="opp-footer">
    <div style="font-size:11px;color:#475569">
      📅 {str(row['created_at'])[:10] if row['created_at'] else 'unknown date'}
    </div>
    <a href="{row['url']}" target="_blank" class="view-link">View original post →</a>
  </div>
</div>
""", unsafe_allow_html=True)

        fav_label = "⭐ Quitar favorito" if is_fav else "☆ Favorito"
        if st.button(fav_label, key=f"fav_{tab_key}_{row['id']}", help="Toggle favorite"):
            toggle_favorite(row['id'], is_fav)
            st.rerun()

    # Pagination controls
    st.markdown("<div style='height:12px'></div>", unsafe_allow_html=True)
    col_prev, col_info, col_next = st.columns([1, 2, 1])
    with col_prev:
        if st.button("← Previous", key=f"prev_{tab_key}", disabled=(page == 0)):
            st.session_state[page_key] = page - 1
            st.rerun()
    with col_info:
        st.markdown(
            f"<div style='text-align:center;color:#475569;font-size:13px;padding-top:8px'>Page {page+1} of {total_pages}</div>",
            unsafe_allow_html=True,
        )
    with col_next:
        if st.button("Next →", key=f"next_{tab_key}", disabled=(page >= total_pages - 1)):
            st.session_state[page_key] = page + 1
            st.rerun()


with tab_all:
    render_cards(flt, "all")

with tab_trending:
    trending_df = flt[flt["trending"] == 1]
    render_cards(trending_df, "trending")

with tab_favorites:
    fav_df = flt[flt["favorite"] == 1]
    render_cards(fav_df, "favorites")

with tab_niches:
    if flt.empty:
        st.markdown("""
        <div style="background:#0f0f1a;border:1px solid #1e2035;border-radius:12px;padding:32px;text-align:center;color:#475569">
          No results match your filters.
        </div>
        """, unsafe_allow_html=True)
    else:
        niches_list = flt[flt["niche"] != ""]["niche"].value_counts()
        if niches_list.empty:
            st.markdown("<div style='color:#475569;padding:16px'>No niche data available yet.</div>", unsafe_allow_html=True)
        else:
            for niche_name in niches_list.index:
                niche_df = flt[flt["niche"] == niche_name]
                with st.expander(f"#{niche_name}  ({len(niche_df)} posts)", expanded=False):
                    render_cards(niche_df, f"niche_{niche_name[:20]}")

# ── Export ────────────────────────────────────────────────────────────────────
st.markdown("<div style='height:16px'></div>", unsafe_allow_html=True)
with st.expander("📋 Preview data"):
    cols = ["source","title","upvotes","category","niche","urgency_score","opportunity_score",
            "market_size","competition","monetization","problem_summary","solution","url"]
    export_cols = [c for c in cols if c in flt.columns]
    st.dataframe(flt[export_cols].head(200), use_container_width=True, hide_index=True)
