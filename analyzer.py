import os
import json
from anthropic import Anthropic
from database import Session, PainPoint

# Load .env manually — avoids Windows BOM/encoding issues with python-dotenv
def _load_env():
    for candidate in [
        os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env"),
        os.path.join(os.getcwd(), ".env"),
    ]:
        if os.path.exists(candidate):
            with open(candidate, "rb") as f:
                content = f.read().decode("utf-8-sig")
            for line in content.splitlines():
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, v = line.split("=", 1)
                    os.environ[k.strip()] = v.strip()
            return

_load_env()

_api_key = os.environ.get("ANTHROPIC_API_KEY", "")
if not _api_key:
    raise RuntimeError("ANTHROPIC_API_KEY not found. Check your .env file.")

client = Anthropic(api_key=_api_key)

SYSTEM_PROMPT = """Eres un experto en investigación de productos y emprendimiento. Tu trabajo es identificar
oportunidades de negocio reales escondidas en quejas, frustraciones y necesidades no satisfechas en internet.
Analizas posts con alta precisión — solo marcas algo como pain point real si hay un problema claro,
específico y recurrente que un producto o servicio podría resolver.
IMPORTANTE: Responde SIEMPRE en español. Todos los campos de texto deben estar en español.
Responde solo con JSON válido, sin markdown, sin texto extra."""

ANALYSIS_PROMPT = """Analyze this post and return a JSON object. Be precise and critical.

Post title: {title}
Post body: {body}
Source: {source}
Upvotes/score: {upvotes}
Comments: {num_comments}

Devuelve SOLO esta estructura JSON (todos los textos en español):
{{
  "is_pain_point": <true si hay una necesidad no satisfecha o frustración recurrente clara, false si no>,
  "category": <uno de: "productivity", "finance", "health", "tech", "social", "education", "ecommerce", "hr", "legal", "marketing", "other">,
  "niche": <sub-nicho específico en español, ej: "gestión de facturas", "onboarding remoto", máx 4 palabras>,
  "urgency_score": <1-10, donde 10 = la gente está desesperada y pagando por malas soluciones ahora mismo>,
  "market_size": <"small", "medium", "large">,
  "problem_summary": <1 oración clara en español describiendo el problema central>,
  "who_has_this_problem": <descripción breve en español del usuario objetivo>,
  "solution_suggestion": <1-2 oraciones en español: producto/servicio/feature específico que resolvería el problema>,
  "monetization_idea": <cómo cobrarías por la solución en español, ej: "SaaS $29/mes", "marketplace comisión 5%">,
  "competition_level": <"none", "low", "medium", "high">
}}"""


def analyze_post(pp: PainPoint) -> dict | None:
    prompt = ANALYSIS_PROMPT.format(
        title=pp.title,
        body=(pp.body or "")[:1000],
        source=pp.source,
        upvotes=pp.upvotes,
        num_comments=pp.num_comments,
    )

    try:
        response = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=600,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": prompt}],
        )
        text = response.content[0].text.strip()
        # Strip markdown fences if model adds them
        if "```" in text:
            text = text.split("```")[1]
            if text.startswith("json"):
                text = text[4:]
        return json.loads(text.strip())
    except json.JSONDecodeError as e:
        print(f"    JSON parse error for {pp.id}: {e}")
        return None
    except Exception as e:
        print(f"    Analysis error for {pp.id}: {e}")
        return None


def reset_failed_analyses():
    """Re-queue posts that were 'analyzed' but got no data (e.g. due to bad API key)."""
    session = Session()
    failed = (
        session.query(PainPoint)
        .filter(PainPoint.analyzed == 1, PainPoint.category == None)  # noqa
        .all()
    )
    count = len(failed)
    for pp in failed:
        pp.analyzed = 0
    session.commit()
    session.close()
    if count:
        print(f"  Re-queued {count} failed analyses")
    return count


def run_analyzer(batch_size: int = 30, progress_callback=None) -> int:
    # Auto-fix posts that failed analysis previously
    reset_failed_analyses()

    session = Session()
    analyzed_count = 0

    try:
        pending = (
            session.query(PainPoint)
            .filter(PainPoint.analyzed == 0)
            .order_by(PainPoint.upvotes.desc())
            .limit(batch_size)
            .all()
        )

        total = len(pending)
        print(f"  Analyzing {total} posts...")

        for i, pp in enumerate(pending):
            result = analyze_post(pp)
            if result:
                pp.is_pain_point = 1 if result.get("is_pain_point") else 0
                pp.category = result.get("category", "other")
                pp.urgency_score = float(result.get("urgency_score", 0))
                pp.problem_summary = result.get("problem_summary", "")
                extra = {
                    "niche": result.get("niche", ""),
                    "market_size": result.get("market_size", ""),
                    "who": result.get("who_has_this_problem", ""),
                    "monetization": result.get("monetization_idea", ""),
                    "competition": result.get("competition_level", ""),
                }
                pp.solution_suggestion = (result.get("solution_suggestion", "")) + f"|||{json.dumps(extra)}"

                # Compute opportunity_score
                market_map = {"large": 3, "medium": 2, "small": 1}
                comp_map = {"none": 4, "low": 3, "medium": 2, "high": 1}
                market_num = market_map.get(result.get("market_size", ""), 1)
                comp_num = comp_map.get(result.get("competition_level", ""), 2)
                import math
                upvote_bonus = min(math.log(max(pp.upvotes or 1, 1) + 1) / 10, 1)
                pp.opportunity_score = round(
                    (float(result.get("urgency_score", 0)) * 0.45) +
                    (market_num * 0.9) +
                    (comp_num * 0.7) +
                    (upvote_bonus * 0.5), 2
                )

                analyzed_count += 1

            pp.analyzed = 1

            # Save every 5 posts so results appear incrementally
            if (i + 1) % 5 == 0:
                session.commit()

            # Report progress if callback provided
            if progress_callback:
                progress_callback(i + 1, total, pp.title[:60])

        session.commit()
        print(f"  -> {analyzed_count} pain points out of {total} posts")

    except Exception as e:
        session.rollback()
        print(f"  Analyzer error: {e}")
    finally:
        session.close()

    return analyzed_count


if __name__ == "__main__":
    run_analyzer()
