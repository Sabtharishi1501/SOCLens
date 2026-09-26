"""
Central configuration for the SOC Maturity Assessment tool.

Every fixed size/limit the assignment calls for lives here, in one place,
so they can be tuned later without hunting through the codebase.
"""

import os
from dotenv import load_dotenv

load_dotenv()

# ---------------------------------------------------------------------------
# API keys (loaded from .env — see .env.example)
# ---------------------------------------------------------------------------
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")

# ---------------------------------------------------------------------------
# Model selection
# ---------------------------------------------------------------------------
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-3.6-flash")
GROQ_MODEL = os.getenv("GROQ_MODEL", "openai/gpt-oss-120b")

# ---------------------------------------------------------------------------
# Fixed input / output sizing (agreed with the user)
# ---------------------------------------------------------------------------

# Max characters of SOP text sent to the LLM (~3,000 tokens). Anything beyond
# this is truncated, and the response is flagged with "truncated": true so
# it's visible rather than silently losing content.
MAX_INPUT_CHARS = 12_000

# Max tokens the LLM is allowed to generate. Raised from an initial 1,200 to
# 2,048 after observing real responses get cut off mid-string (an
# "Unterminated string" JSON parse error) on some documents - 4 structured
# objects with evidence/explanation/gap text needs more headroom than the
# original estimate assumed.
MAX_OUTPUT_TOKENS = 2_048

# Max length of a single "evidence" quote per question. Forces the model to
# point at a specific sentence/fragment rather than dumping a paragraph,
# and keeps the grounding (substring) check fast and reliable.
MAX_EVIDENCE_CHARS = 220

# Deterministic, literal scoring — no creative variation across runs.
TEMPERATURE = 0

# When true, get_llm_response() returns a canned response instantly with no
# real API call to either provider. Use this while testing the upload ->
# extraction -> validation -> UI pipeline so you don't burn real quota
# (Gemini's free tier daily cap is easy to exhaust during development).
# Set MOCK_LLM=true in .env. Always confirm this is false/unset before a
# real demo - the UI shows "Scored by Mock" when it's active, precisely so
# it can't be mistaken for a real result.
MOCK_LLM = os.getenv("MOCK_LLM", "false").lower() == "true"

# ---------------------------------------------------------------------------
# Grounding check
# ---------------------------------------------------------------------------

# How closely an "evidence" string must match the source text to count as
# verified. 1.0 = exact substring. We allow a little slack (see validator.py)
# for minor whitespace/punctuation differences without allowing paraphrase.
FUZZY_MATCH_THRESHOLD = 0.85

# ---------------------------------------------------------------------------
# The 4 fixed assessment questions (SOC-CMM aligned, per the assignment)
# ---------------------------------------------------------------------------
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

# ---------------------------------------------------------------------------
# Server
# ---------------------------------------------------------------------------
HOST = os.getenv("HOST", "0.0.0.0")
PORT = int(os.getenv("PORT", "8000"))