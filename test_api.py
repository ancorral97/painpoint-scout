import os, json
from dotenv import load_dotenv
from anthropic import Anthropic

load_dotenv()
client = Anthropic()

# Test 1: basic API call
resp = client.messages.create(
    model="claude-haiku-4-5-20251001",
    max_tokens=400,
    messages=[{"role": "user", "content": 'Respond with only this JSON, no extra text: {"is_pain_point": true, "category": "tech", "urgency_score": 7.5, "problem_summary": "test", "solution_suggestion": "test"}'}]
)
raw = resp.content[0].text
print("RAW RESPONSE:", repr(raw))

# Test 2: parse it
try:
    data = json.loads(raw)
    print("PARSED OK:", data)
except Exception as e:
    print("PARSE ERROR:", e)

# Test 3: real post analysis
from analyzer import analyze_post
from database import Session, PainPoint, init_db
init_db()
s = Session()
pp = s.query(PainPoint).first()
if pp:
    print("\nTesting with real post:", pp.title[:60])
    result = analyze_post(pp)
    print("RESULT:", result)
s.close()
