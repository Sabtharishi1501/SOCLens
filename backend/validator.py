"""
Parses the raw LLM response into the expected shape, and runs the grounding
check: does each "evidence" quote actually appear in the source document?

This is the module that catches hallucinated evidence. A result is marked
"verified": True only if its evidence string is found in the source text
(exact match after normalization, or a close fuzzy match to tolerate minor
whitespace/OCR-style noise) -- never based on trusting the model's own claim.
"""

import difflib
import json
import re

from config import ASSESSMENT_QUESTIONS, FUZZY_MATCH_THRESHOLD, MAX_EVIDENCE_CHARS

EXPECTED_IDS = [q["id"] for q in ASSESSMENT_QUESTIONS]
TITLES_BY_ID = {q["id"]: q["title"] for q in ASSESSMENT_QUESTIONS}

NO_EVIDENCE_MARKERS = {"none found", "none", "n/a", "not found", "no evidence found"}


class ValidationError(Exception):
    """Raised when the LLM response can't be parsed into the expected shape."""


def parse_llm_response(raw_text: str, source_text: str) -> list:
    """
    Returns a list of 4 dicts (one per question, in ASSESSMENT_QUESTIONS
    order), each with: question_id, title, score, evidence, explanation,
    gap, verified.
    Raises ValidationError if the JSON is malformed or missing questions.
    """
    data = _parse_json(raw_text)

    if "results" not in data or not isinstance(data["results"], list):
        raise ValidationError('Response JSON is missing a "results" list.')

    by_id = {}
    for item in data["results"]:
        if not isinstance(item, dict) or "question_id" not in item:
            continue
        by_id[item["question_id"]] = item

    missing = [qid for qid in EXPECTED_IDS if qid not in by_id]
    if missing:
        raise ValidationError(f"Response is missing results for: {missing}")

    source_norm = _normalize(source_text)
    output = []

    for qid in EXPECTED_IDS:
        item = by_id[qid]
        score = _coerce_score(item.get("score"))
        evidence = str(item.get("evidence", "")).strip()[:MAX_EVIDENCE_CHARS]
        explanation = str(item.get("explanation", "")).strip()
        gap = str(item.get("gap", "")).strip()

        verified = _check_grounding(evidence, score, source_norm)

        output.append(
            {
                "question_id": qid,
                "title": TITLES_BY_ID[qid],
                "score": score,
                "evidence": evidence,
                "explanation": explanation,
                "gap": gap,
                "verified": verified,
            }
        )

    return output


def _parse_json(raw_text: str) -> dict:
    text = raw_text.strip()

    fence_match = re.search(r"```(?:json)?\s*(\{.*\})\s*```", text, re.DOTALL)
    if fence_match:
        text = fence_match.group(1)

    try:
        return json.loads(text)
    except json.JSONDecodeError as e:
        raise ValidationError(f"Could not parse LLM response as JSON: {e}")


def _coerce_score(raw_score) -> int:
    try:
        score = int(raw_score)
    except (TypeError, ValueError):
        raise ValidationError(f"Score '{raw_score}' is not a valid integer.")
    return max(0, min(5, score))  # clamp defensively into the valid 0-5 range


def _normalize(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip().lower()


def _check_grounding(evidence: str, score: int, source_norm: str) -> bool:
    """
    True if the evidence is legitimately grounded in the source text:
      - if the model claims no evidence, that's only "grounded" when the
        score is also 0 (consistent);
      - otherwise, the evidence string must appear in the source, exactly
        or via a close fuzzy match.
    """
    evidence_norm = _normalize(evidence)

    is_no_evidence_claim = evidence_norm in NO_EVIDENCE_MARKERS or evidence_norm == ""
    if is_no_evidence_claim:
        return score == 0

    if evidence_norm in source_norm:
        return True

    return _fuzzy_found(evidence_norm, source_norm)


def _fuzzy_found(needle: str, haystack: str) -> bool:
    """
    Slides a window the length of `needle` across `haystack` looking for a
    close match, to tolerate trivial differences (e.g. a stray space) without
    accepting a paraphrase. Uses difflib's ratio, which is O(n) per
    comparison; step size keeps this fast enough for a single request.
    """
    window = len(needle)
    if window == 0:
        return False

    step = max(1, window // 4)
    best_ratio = 0.0

    for i in range(0, max(1, len(haystack) - window + 1), step):
        chunk = haystack[i : i + window]
        ratio = difflib.SequenceMatcher(None, needle, chunk).ratio()
        if ratio > best_ratio:
            best_ratio = ratio
        if best_ratio >= FUZZY_MATCH_THRESHOLD:
            return True

    return False