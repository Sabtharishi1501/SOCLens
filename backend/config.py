"""
Central configuration for the SOC Maturity Assessment tool.

Every fixed size/limit the assignment calls for lives here, in one place,
so they can be tuned later without hunting through the codebase.
"""

import os
from dotenv import load_dotenv

load_dotenv()

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")

GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-3.6-flash")
GROQ_MODEL = os.getenv("GROQ_MODEL", "openai/gpt-oss-120b")

MAX_INPUT_CHARS = 12_000
MAX_OUTPUT_TOKENS = 8_192

MAX_EVIDENCE_CHARS = 220

TEMPERATURE = 0

MOCK_LLM = os.getenv("MOCK_LLM", "false").lower() == "true"

FUZZY_MATCH_THRESHOLD = 0.85

ASSESSMENT_QUESTIONS = [
    {
        "id": "incident_response_process",
        "title": "Incident Response Process",
        "prompt": "Is there a documented and repeatable process for handling security incidents?",
    },
    {
        "id": "incident_classification",
        "title": "Incident Classification",
        "prompt": "Does the organization have a defined process for classifying and prioritizing security incidents?",
    },
    {
        "id": "incident_escalation",
        "title": "Incident Escalation",
        "prompt": "Are incident escalation procedures, roles, and responsibilities clearly defined?",
    },
    {
        "id": "incident_documentation",
        "title": "Incident Documentation",
        "prompt": "Are incident actions, evidence, and outcomes properly recorded and maintained?",
    },
]

HOST = os.getenv("HOST", "0.0.0.0")
PORT = int(os.getenv("PORT", "8000"))