"""
Handles the actual LLM calls. Groq is primary; if it fails for any reason
(quota exceeded, network error, missing key), we fall back to Gemini
automatically. Both are called with the same prompt and the same fixed
sizing constants from config.py, and both are asked for raw JSON back.

Groq is primary (not Gemini) because in practice it has reliably produced
complete, correctly-grounded results, while Gemini has hit a deprecated
model alias, free-tier quota exhaustion, and an unexplained early
truncation on verbatim-quote content. Gemini stays as a real fallback
rather than being removed, in case Groq itself is ever down.

Note: this module can only be exercised with real API keys in .env. If a
key is missing, that provider is skipped (not silently retried forever).
"""

import json
import re
import time

import google.generativeai as genai
from groq import Groq

import config

MAX_GEMINI_RATE_LIMIT_RETRIES = 1
DEFAULT_RETRY_DELAY_SECONDS = 15


class LLMError(Exception):
    """Raised when both Groq and Gemini fail (or neither key is configured)."""


def _build_mock_response() -> str:
    results = [
        {
            "question_id": q["id"],
            "score": 0,
            "evidence": "None found",
            "explanation": "Mock response - MOCK_LLM is enabled, no real API call was made.",
            "gap": "This is not a real assessment. Set MOCK_LLM=false in .env for real results.",
        }
        for q in config.ASSESSMENT_QUESTIONS
    ]
    return json.dumps({"results": results})


def _is_rate_limit_error(error: Exception) -> bool:
    text = str(error).lower()
    return "429" in text or "quota" in text or "rate limit" in text


def _extract_retry_delay(error: Exception) -> int:
    text = str(error)
    match = re.search(r"retry in (\d+(?:\.\d+)?)s", text, re.IGNORECASE)
    if match:
        return int(float(match.group(1))) + 1
    match = re.search(r"seconds:\s*(\d+)", text)
    if match:
        return int(match.group(1)) + 1
    return DEFAULT_RETRY_DELAY_SECONDS


def call_gemini(prompt: str) -> str:
    if not config.GEMINI_API_KEY:
        raise RuntimeError("GEMINI_API_KEY is not set in .env")

    genai.configure(api_key=config.GEMINI_API_KEY)
    model = genai.GenerativeModel(config.GEMINI_MODEL)

    attempts = MAX_GEMINI_RATE_LIMIT_RETRIES + 1
    last_error = None

    for attempt in range(attempts):
        try:
            response = model.generate_content(
                prompt,
                generation_config=genai.types.GenerationConfig(
                    temperature=config.TEMPERATURE,
                    max_output_tokens=config.MAX_OUTPUT_TOKENS,
                    response_mime_type="application/json",
                ),
            )

            try:
                candidate = response.candidates[0]
                finish_reason = candidate.finish_reason
                print(f"[SOCLens] gemini finish_reason: {finish_reason}")
                if getattr(candidate, "safety_ratings", None):
                    flagged = [
                        r for r in candidate.safety_ratings
                        if getattr(r, "probability", None) and str(r.probability) != "NEGLIGIBLE"
                    ]
                    if flagged:
                        print(f"[SOCLens] gemini safety_ratings (non-negligible): {flagged}")
            except Exception as diag_error:
                print(f"[SOCLens] (could not read finish_reason: {diag_error})")

            if not response.text:
                raise RuntimeError("Gemini returned an empty response")

            return response.text

        except Exception as e:
            last_error = e
            is_last_attempt = attempt == attempts - 1
            if _is_rate_limit_error(e) and not is_last_attempt:
                delay = _extract_retry_delay(e)
                time.sleep(delay)
                continue
            raise

    raise last_error


def call_groq(prompt: str) -> str:
    if not config.GROQ_API_KEY:
        raise RuntimeError("GROQ_API_KEY is not set in .env")

    client = Groq(api_key=config.GROQ_API_KEY)

    completion = client.chat.completions.create(
        model=config.GROQ_MODEL,
        messages=[{"role": "user", "content": prompt}],
        temperature=config.TEMPERATURE,
        max_tokens=config.MAX_OUTPUT_TOKENS,
        response_format={"type": "json_object"},
    )

    content = completion.choices[0].message.content
    if not content:
        raise RuntimeError("Groq returned an empty response")

    return content


def get_llm_response(prompt: str) -> dict:
    """
    Tries Groq first, falls back to Gemini on any failure. Returns:
        {"raw_text": <str>, "provider": "groq" | "gemini (fallback)" | "mock"}
    Raises LLMError only if BOTH real providers fail.
    """
    if config.MOCK_LLM:
        print("[SOCLens] MOCK_LLM is enabled - returning canned response, no API call made")
        return {"raw_text": _build_mock_response(), "provider": "mock"}

    try:
        raw_text = call_groq(prompt)
        print(f"[SOCLens] groq responded: {len(raw_text)} chars")
        return {"raw_text": raw_text, "provider": "groq"}
    except Exception as groq_error:
        print(f"[SOCLens] groq failed: {groq_error}")
        try:
            raw_text = call_gemini(prompt)
            print(f"[SOCLens] gemini (fallback) responded: {len(raw_text)} chars")
            return {
                "raw_text": raw_text,
                "provider": "gemini (fallback)",
                "fallback_reason": str(groq_error),
            }
        except Exception as gemini_error:
            raise LLMError(
                f"Groq failed: {groq_error} | Gemini fallback also failed: {gemini_error}"
            )
        