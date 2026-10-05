"""Thin wrapper around the Groq LLM API for the agents that benefit from language understanding.

Every caller has a deterministic fallback, so the system runs fully offline when no Groq key is
configured (or when CIVIC_AI_MODE=rules). Set GROQ_API_KEY to enable AI mode.

Models are configurable:
  GROQ_MODEL         text model   (default llama-3.3-70b-versatile)
  GROQ_VISION_MODEL  photo model  (default meta-llama/llama-4-scout-17b-16e-instruct)
"""
import json
import logging
import os

log = logging.getLogger("civic.llm")
MODEL = os.environ.get("GROQ_MODEL", "llama-3.3-70b-versatile")
VISION_MODEL = os.environ.get("GROQ_VISION_MODEL", "meta-llama/llama-4-scout-17b-16e-instruct")

_client = None
_disabled_reason = None


def _get_client():
    global _client, _disabled_reason
    if _client is not None or _disabled_reason:
        return _client
    if os.environ.get("CIVIC_AI_MODE", "auto").lower() == "rules":
        _disabled_reason = "CIVIC_AI_MODE=rules"
        return None
    if not os.environ.get("GROQ_API_KEY"):
        _disabled_reason = "no GROQ_API_KEY"
        return None
    try:
        from groq import Groq
        _client = Groq(timeout=30.0, max_retries=1)
    except Exception as e:  # SDK missing or misconfigured
        _disabled_reason = f"client init failed: {e}"
    return _client


def available() -> bool:
    return _get_client() is not None


def status():
    _get_client()
    return {"enabled": _client is not None, "provider": "groq", "model": MODEL if _client else None,
            "vision_model": VISION_MODEL if _client else None, "reason": _disabled_reason}


def _validate(data, schema):
    """Minimal schema check: required keys present, enums respected. Raises ValueError on mismatch."""
    if not isinstance(data, dict):
        raise ValueError("not an object")
    for key in schema.get("required", []):
        if key not in data:
            raise ValueError(f"missing '{key}'")
    for key, spec in schema.get("properties", {}).items():
        val = data.get(key)
        if "enum" in spec and val not in spec["enum"]:
            raise ValueError(f"'{key}'={val!r} not in enum")
        if spec.get("type") == "array" and "enum" in spec.get("items", {}):
            data[key] = [v for v in (val or []) if v in spec["items"]["enum"]]
        if spec.get("type") == "number" and not isinstance(val, (int, float)):
            data[key] = float(val) if str(val).replace(".", "", 1).isdigit() else 0.0
    return data


def structured(system: str, prompt: str, schema: dict, image_b64: str | None = None, image_type: str | None = None, max_tokens: int = 1200):
    """Ask Groq for JSON matching `schema`. Returns a dict, or None on any failure (caller falls back to rules)."""
    client = _get_client()
    if client is None:
        return None
    import groq
    sys_prompt = (f"{system}\n\nRespond ONLY with a JSON object that matches this JSON Schema exactly "
                  f"(all required keys, enum values verbatim):\n{json.dumps(schema)}")
    if image_b64:
        user_content = [{"type": "text", "text": prompt},
                        {"type": "image_url", "image_url": {"url": f"data:{image_type or 'image/jpeg'};base64,{image_b64}"}}]
        model = VISION_MODEL
    else:
        user_content = prompt
        model = MODEL
    try:
        resp = client.chat.completions.create(
            model=model,
            messages=[{"role": "system", "content": sys_prompt}, {"role": "user", "content": user_content}],
            response_format={"type": "json_object"},
            temperature=0.1,
            max_completion_tokens=max_tokens,
        )
        choice = resp.choices[0]
        if choice.finish_reason == "length":
            log.warning("Groq output truncated; using rule fallback")
            return None
        return _validate(json.loads(choice.message.content), schema)
    except (groq.APIStatusError, groq.APIConnectionError) as e:
        log.warning("Groq call failed (%s); using rule fallback", e)
    except (json.JSONDecodeError, ValueError, TypeError) as e:
        log.warning("Groq returned unusable JSON (%s); using rule fallback", e)
    return None


def text(system: str, prompt: str, max_tokens: int = 1500):
    client = _get_client()
    if client is None:
        return None
    import groq
    try:
        resp = client.chat.completions.create(
            model=MODEL,
            messages=[{"role": "system", "content": system}, {"role": "user", "content": prompt}],
            temperature=0.3,
            max_completion_tokens=max_tokens,
        )
        return resp.choices[0].message.content or None
    except (groq.APIStatusError, groq.APIConnectionError) as e:
        log.warning("Groq call failed (%s)", e)
        return None
