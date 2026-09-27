# SOCLens — AI-Based SOC Maturity Assessment

SOCLens is a small full-stack tool that takes an organization's Incident Response SOP (Standard Operating Procedure) document and scores it against 4 SOC-CMM–aligned maturity questions, using an LLM constrained to only use evidence that is actually present in the document.

It was built for the **Technical Assignment II – Intern (Full Stack + AI)** brief — Task #2 (AI-Based SOC Maturity Assessment).

> This is an assessment aid based on documentary evidence, not a technical audit or vulnerability assessment. The AI is instructed never to assume or invent evidence — every score must be traceable to text that actually appears in the uploaded SOP.

## What it does

1. You upload a `.pdf`, `.docx`, or `.txt` SOP/evidence document.
2. The backend extracts and cleans the text from the file.
3. The text is sent to an LLM with a strict, rubric-based prompt covering 4 questions:
   - **Incident Response Process** — is there a documented, repeatable process for handling incidents?
   - **Incident Classification** — is there a defined process for classifying/prioritizing incidents?
   - **Incident Escalation** — are escalation procedures, roles, and responsibilities clearly defined?
   - **Incident Documentation** — are incident actions, evidence, and outcomes properly recorded?
4. Each question is scored **0–5** on the SOC-CMM maturity scale (Not Present → Initial → Defined → Managed → Measured → Optimized), using a concrete, per-level rubric so the model isn't making a vague judgment call.
5. For every score, the response includes: **Score → Evidence → Explanation → Gap**.
6. The backend independently re-checks every "evidence" quote against the original document text (exact match, with fuzzy matching to tolerate whitespace/OCR-style noise). Results are only marked `verified: true` if the quote is actually grounded in the source — the app never simply trusts the model's own claim.

## Why the scoring can be trusted (grounding)

The main risk with an LLM-based assessment is hallucinated evidence — the model inferring that a process "probably" exists because it's common practice. SOCLens addresses this in two layers:

- **Prompting (`prompt_template.py`)**: the model is required to return an exact, verbatim quote (max 220 characters) as evidence, is told explicitly to score `0` and return `"None found"` when nothing relevant exists, and is given a concrete per-level rubric for each of the 4 questions so scores are reproducible rather than vibes-based.
- **Validation (`validator.py`)**: after the model responds, the backend normalizes both the quote and the source document and checks that the quote genuinely appears in the source (exact match, or a close fuzzy match via `difflib`). If the model claims "no evidence" but scores above 0, or a quote can't be found in the document, that result is flagged as unverified rather than silently accepted.

## Tech stack

**Backend** — FastAPI (Python)
- `pdfplumber` / `python-docx` for text extraction from PDF/DOCX
- `groq` (primary) and `google-generativeai` (Gemini, fallback) for the LLM call
- Forced JSON-mode output from both providers, parsed and validated server-side

**Frontend** — plain HTML/CSS/JavaScript (no framework), served as static files by the same FastAPI app
- Drag-and-drop upload, loading state, and a results view showing each question's score/evidence/explanation/gap

## Project structure

```
SOCLens/
├── backend/
│   ├── main.py              # FastAPI app: /api/health, /api/assess, serves the frontend
│   ├── config.py            # All fixed settings: models, limits, the 4 assessment questions
│   ├── extractor.py         # Reads/cleans text from .pdf, .docx, .txt uploads
│   ├── prompt_template.py   # Builds the grounding-strict prompt + per-question rubric
│   ├── llm_client.py        # Calls Groq first, falls back to Gemini on failure
│   ├── validator.py         # Parses LLM JSON output and verifies evidence against the source
│   └── requirements.txt
└── frontend/
    ├── index.html
    ├── app.js
    └── style.css
```

## How it works end to end (`/api/assess`)

1. Client uploads a file via `multipart/form-data`.
2. `extractor.py` extracts and cleans the text. If the document is longer than the configured limit (12,000 characters), it's truncated and the response tells the model — and the user — that it happened, rather than silently scoring a partial document.
3. `prompt_template.py` builds one prompt containing the grounding rules, the rubric for all 4 questions, and the SOP text.
4. `llm_client.py` calls **Groq** first; if that fails for any reason (missing key, quota, network error), it automatically retries with **Gemini** as a fallback, and reports which provider actually produced the result.
5. `validator.py` parses the JSON response, checks it contains all 4 expected question IDs, clamps scores to the 0–5 range, and verifies each evidence quote against the source document.
6. If the response fails validation, `main.py` retries the whole LLM call up to 3 times before returning an error.
7. The final JSON — filename, provider used, truncation info, and the 4 scored results — is returned to the frontend and rendered.

## Setup

### Requirements
- Python 3.10+
- A [Groq](https://console.groq.com/) API key (primary) and/or a [Google AI Studio](https://aistudio.google.com/) Gemini API key (fallback) — at least one is required

### 1. Clone and install
```bash
git clone https://github.com/Sabtharishi1501/SOCLens.git
cd SOCLens/backend
pip install -r requirements.txt
```

### 2. Configure environment variables
Create a `.env` file inside `backend/`:
```env
GROQ_API_KEY=your_groq_key_here
GEMINI_API_KEY=your_gemini_key_here

# Optional overrides
GROQ_MODEL=openai/gpt-oss-120b
GEMINI_MODEL=gemini-3.6-flash
HOST=0.0.0.0
PORT=8000

# Optional: run without calling any real LLM (returns a canned response)
MOCK_LLM=false
```

### 3. Run it
```bash
python main.py
```
The FastAPI app serves both the API and the static frontend from the same process — open **http://localhost:8000** in your browser and upload an SOP document.

## API

**`GET /api/health`** — health check, returns `{"status": "ok"}`

**`POST /api/assess`** — multipart form upload with a single `file` field (`.pdf`, `.docx`, or `.txt`)

Response shape:
```json
{
  "filename": "sop.pdf",
  "provider_used": "groq",
  "truncated": false,
  "original_chars": 8421,
  "used_chars": 8421,
  "results": [
    {
      "question_id": "incident_response_process",
      "title": "Incident Response Process",
      "score": 3,
      "evidence": "The SOC analyst follows the documented triage workflow for every reported incident.",
      "explanation": "...",
      "gap": "...",
      "verified": true
    }
    // ...3 more questions
  ]
}
```

## Known limitations

- No OCR — scanned/image-based PDFs with no extractable text layer aren't supported.
- Input is capped at 12,000 characters; longer documents are truncated (and the response flags this) rather than chunked/summarized.
- This tool scores what is *documented*, not what is actually practiced — it cannot verify that a written process is followed in reality.
- Not a substitute for a full SOC-CMM assessment or a professional security audit.

## License

MIT — see [LICENSE](LICENSE).