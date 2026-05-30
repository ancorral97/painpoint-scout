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

VALIDATION_PROMPT = """Basado en estos pain points reales encontrados en internet:

{pain_points}

Genera 5 ideas de negocio VALIDADAS que:
1. Llevan AL MENOS 5 años generando dinero en el mercado
2. Son replicables con bajo presupuesto inicial (<$5,000)
3. Tienen demanda probada y constante (no son tendencias)
4. Al menos una empresa exitosa ya lo está haciendo

Para cada idea devuelve este JSON (array de 5 objetos):
[
  {{
    "nombre": "nombre corto del negocio",
    "descripcion": "qué hace exactamente en 1 oración",
    "modelo": "SaaS / Agencia / Marketplace / Info-producto / Servicio / etc",
    "pain_point_que_resuelve": "cuál de los pain points anteriores resuelve",
    "ejemplos_exitosos": ["Empresa1 ($XM ARR)", "Empresa2 (adquirida por $X)", "Empresa3"],
    "anos_en_mercado": "cuántos años lleva este modelo funcionando",
    "ingreso_mensual_estimado": "rango realista para un solo fundador: ej $2k-$8k/mes",
    "tiempo_para_primer_ingreso": "ej: 2-4 semanas",
    "como_empezar": "3 pasos concretos para arrancar esta semana",
    "por_que_funciona_largo_plazo": "razón fundamental de su durabilidad",
    "riesgo_principal": "el mayor riesgo o desafío",
    "score_oportunidad": 1-10
  }}
]

Solo JSON, sin texto extra."""


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
