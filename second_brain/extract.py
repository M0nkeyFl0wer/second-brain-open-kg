"""
Triplet extraction from text — entity-relationship-entity with evidence.

Uses LLM (Ollama) to extract triplets from note chunks.
Evidence is REQUIRED on every edge — verbatim quote from source text.

Returns:
    {
        "entities": [{"label": "...", "type": "...", "meta": {...}}, ...],
        "edges": [{"source": "...", "target": "...", "type": "...", "evidence": "...", "confidence": 0.5}, ...]
    }
"""

import json
import urllib.request
from typing import Any


DEFAULT_MODEL = "qwen3:14b"
DEFAULT_HOST = "http://localhost:11434"
TIMEOUT_SECONDS = 60


def extract_triplets_from_text(
    text: str,
    edge_types: list[str],
    model: str = DEFAULT_MODEL,
    host: str = DEFAULT_HOST,
    max_tokens: int = 2048,
) -> dict[str, Any]:
    """
    Extract triplets from a text chunk using Ollama LLM.

    Args:
        text: the note chunk text to analyze
        edge_types: list of edge types to extract (from config)
        model: Ollama model name
        host: Ollama host URL
        max_tokens: max tokens for LLM response

    Returns:
        dict with "entities" and "edges" lists
    """
    if not text or len(text.strip()) < 20:
        return {"entities": [], "edges": []}

    prompt = f"""Extract triplets (subject, relationship, object) from the following text.

For each relationship found, return:
- source entity label
- target entity label
- edge type (one of: {", ".join(edge_types)})
- verbatim evidence quote from the text (min 10 characters)
- confidence: 0.9 deterministic / 0.7 NLP / 0.5 LLM

Entity types: concept, person, source, project, insight, question, practice, place, method, tool

Respond ONLY with valid JSON (no markdown, no explanation):
{{
  "entities": [
    {{"label": "entity name", "type": "entity_type", "meta": {{}}}}
  ],
  "edges": [
    {{
      "source": "source entity label",
      "target": "target entity label",
      "type": "EDGE_TYPE",
      "evidence": "exact quote from text",
      "confidence": 0.5
    }}
  ]
}}

Text to analyze:
---
{text[:4000]}
---

JSON response:"""

    payload = {
        "model": model,
        "prompt": prompt,
        "stream": False,
        "options": {
            "temperature": 0.1,
            "num_predict": max_tokens,
        },
    }

    try:
        req = urllib.request.Request(
            f"{host}/api/generate",
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )

        with urllib.request.urlopen(req, timeout=TIMEOUT_SECONDS) as resp:
            result = json.loads(resp.read().decode("utf-8"))
            response_text = result.get("response", "").strip()

        # Parse JSON from response
        return _parse_json_response(response_text)

    except Exception as ex:
        # Log and return empty on failure
        print(f"[extract_triplets] Error: {ex}")
        return {"entities": [], "edges": []}


def _parse_json_response(response_text: str) -> dict[str, Any]:
    """
    Parse JSON from LLM response, handling trailing prose or malformed JSON.

    Strategy:
    1. Try raw JSON parse
    2. Strip markdown code blocks if present
    3. Find first { and last } and try again
    4. Fall back to empty result
    """
    if not response_text:
        return {"entities": [], "edges": []}

    # Try direct parse
    try:
        return json.loads(response_text)
    except json.JSONDecodeError:
        pass

    # Strip markdown code blocks
    cleaned = response_text.strip()
    if cleaned.startswith("```"):
        lines = cleaned.split("\n")
        cleaned = "\n".join(lines[1:])  # Remove first line (```json)
        if cleaned.endswith("```"):
            cleaned = cleaned[:-3]
    cleaned = cleaned.strip()

    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        pass

    # Find JSON bounds
    first_brace = cleaned.find("{")
    last_brace = cleaned.rfind("}")
    if first_brace != -1 and last_brace > first_brace:
        try:
            return json.loads(cleaned[first_brace:last_brace + 1])
        except json.JSONDecodeError:
            pass

    # Failed to parse
    print(f"[extract_triplets] Failed to parse JSON response: {cleaned[:200]}...")
    return {"entities": [], "edges": []}


def extract_triplets_batch(
    texts: list[str],
    edge_types: list[str],
    model: str = DEFAULT_MODEL,
    host: str = DEFAULT_HOST,
) -> list[dict[str, Any]]:
    """
    Extract triplets from multiple texts in sequence.

    For parallel extraction, run this function concurrently with thread pool.
    Ollama handles concurrency via its internal thread management.
    """
    results = []
    for text in texts:
        result = extract_triplets_from_text(text, edge_types, model, host)
        results.append(result)
    return results