import os
import json
from anthropic import Anthropic

# Reuse env loader from analyzer
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
client = Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY", ""))

SYSTEM_PROMPT = """Eres un experto en negocios digitales con 20 años de experiencia identificando
modelos de negocio probados que generan ingresos estables por años.
Tu especialidad es encontrar ideas validadas — no tendencias, sino negocios con track record real.
Responde siempre en español con JSON válido."""

VALIDATION_PROMPT = """Eres un investigador de negocios. Tienes dos fuentes de información:

## FUENTE 1 — Pain points reales scrapeados de internet:
{pain_points}

## FUENTE 2 — Tu conocimiento propio de negocios que han funcionado por años globalmente.

Tu tarea: Genera exactamente 8 ideas de negocio. Distribúyelas así:
- **3 ideas** directamente inspiradas en los pain points anteriores
- **3 ideas** de tu conocimiento de modelos probados en los mismos SECTORES (aunque no estén en los pain points)
- **2 ideas** "wildcard" — negocios evergreen que casi siempre funcionan independiente del sector

Criterios obligatorios para TODAS:
1. Llevan AL MENOS 5 años generando dinero (no son tendencias nuevas)
2. Replicables con menos de $5,000 de inversión inicial
3. Hay empresas reales haciendo esto HOY y ganando dinero
4. Demanda constante, no estacional

Para cada idea devuelve este JSON exacto:
{{
  "nombre": "nombre corto y memorable",
  "descripcion": "qué hace exactamente en 1 oración clara",
  "modelo": "SaaS / Agencia / Marketplace / Info-producto / Servicio B2B / Comunidad / etc",
  "origen": "pain_point / sector_adyacente / wildcard",
  "pain_point_que_resuelve": "el problema específico que ataca (puede ser inferido aunque no esté en la lista)",
  "ejemplos_exitosos": ["Empresa real ($X ARR o revenue)", "Otra empresa (exit o fundada en año X)", "Una más"],
  "anos_en_mercado": "X años (desde cuándo existe este modelo)",
  "ingreso_mensual_estimado": "rango realista para fundador solo: $Xk-$Xk/mes en 12 meses",
  "tiempo_para_primer_ingreso": "X semanas/meses siendo realista",
  "como_empezar": "Paso 1: ... | Paso 2: ... | Paso 3: ...",
  "por_que_funciona_largo_plazo": "la razón estructural de su durabilidad (ej: switching costs, red effect, etc)",
  "riesgo_principal": "el obstáculo más probable que mata este negocio",
  "competencia": "baja / media / alta",
  "score_oportunidad": 1-10
}}

Devuelve un array JSON de 8 objetos. Solo JSON, sin texto extra."""


def generate_validated_ideas(pain_points: list[dict]) -> list[dict]:
    """Generate validated business ideas based on analyzed pain points."""
    if not pain_points:
        return []

    # Format top pain points for the prompt
    formatted = []
    for i, pp in enumerate(pain_points[:10], 1):
        formatted.append(
            f"{i}. [{pp.get('category','?')}] {pp.get('problem_summary','')}"
            f" (nicho: {pp.get('niche','?')}, urgencia: {pp.get('urgency_score',0)}/10)"
        )

    prompt = VALIDATION_PROMPT.format(pain_points="\n".join(formatted))

    try:
        response = client.messages.create(
            model="claude-sonnet-4-5",
            max_tokens=4000,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": prompt}],
        )
        text = response.content[0].text.strip()
        if "```" in text:
            text = text.split("```")[1]
            if text.startswith("json"):
                text = text[4:]
        return json.loads(text.strip())
    except Exception as e:
        print(f"Validator error: {e}")
        return []
