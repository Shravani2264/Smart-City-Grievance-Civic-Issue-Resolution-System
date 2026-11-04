"""LangChain-based LLM layer for the agent pipeline.

Every agent that uses the LLM calls through this module.  Under the hood we use the LangChain stack:

* `ChatGroq` (langchain-groq) is the chat model.
* `ChatPromptTemplate` composes the system + user turns.
* `JsonOutputParser` / `.with_structured_output()` constrain the model to a JSON schema.
* `prompt | llm | parser` is a LangChain Expression Language (LCEL) chain.

Every call has a deterministic fallback, so the system runs fully offline when no Groq key is
configured (or when CIVIC_AI_MODE=rules).  LLM failures are caught and reported as `None`, which
each agent handles by falling back to its rules engine.

Models are configurable:
  GROQ_MODEL         text model   (default openai/gpt-oss-120b)
  GROQ_VISION_MODEL  photo model  (default qwen/qwen3.8-27b)

Optimisations (from "7 ways to make an LLM faster"; the server-side ones are Groq's job, these are ours):
  * Prompt-prefix stability (KV/prefix caching): the long system+schema prefix is built once per
    (system, schema) and is byte-identical on every call; only the short user turn varies.
  * Response cache: identical requests within CIVIC_LLM_CACHE_TTL seconds are served from an in-process
    LRU, so retries, eval reruns and repeated complaint text never pay for a second model call.
  * Telemetry: call / cache-hit / failure counters and latency per model, exposed via status().
"""
import collections
import functools
import hashlib
import json
import logging
import os
import threading
import time
from typing import Any

log = logging.getLogger("civic.llm")
MODEL = os.environ.get("GROQ_MODEL", "openai/gpt-oss-120b")
VISION_MODEL = os.environ.get("GROQ_VISION_MODEL", "qwen/qwen3.8-27b")
CACHE_TTL = float(os.environ.get("CIVIC_LLM_CACHE_TTL", 3600))
CACHE_MAX = 512

_text_llm = None
_vision_llm = None
_disabled_reason: str | None = None
_extra_llms: dict = {}

_cache: "collections.OrderedDict[str, tuple[float, str]]" = collections.OrderedDict()
_cache_lock = threading.Lock()
STATS = {"calls": 0, "cache_hits": 0, "failures": 0, "by_model": {}}


def _cache_key(*parts) -> str:
    h = hashlib.sha256()
    for p in parts:
        h.update(str(p).encode("utf-8", "replace"))
        h.update(b"\x1f")
    return h.hexdigest()


def _cache_get(key):
    if CACHE_TTL <= 0:
        return None
    with _cache_lock:
        hit = _cache.get(key)
        if hit and time.time() - hit[0] < CACHE_TTL:
            _cache.move_to_end(key)
            STATS["cache_hits"] += 1
            return json.loads(hit[1])  # fresh copy: callers may mutate the result
        if hit:
            del _cache[key]
    return None


def _cache_put(key, value):
    if CACHE_TTL <= 0 or value is None:
        return
    with _cache_lock:
        _cache[key] = (time.time(), json.dumps(value))
        _cache.move_to_end(key)
        while len(_cache) > CACHE_MAX:
            _cache.popitem(last=False)


def _record(model: str, ms: float, ok: bool):
    with _cache_lock:
        STATS["calls"] += 1
        STATS["failures"] += (not ok)
        m = STATS["by_model"].setdefault(model, {"calls": 0, "failures": 0, "total_ms": 0.0})
        m["calls"] += 1
        m["failures"] += (not ok)
        m["total_ms"] += ms


def reset_stats():
    with _cache_lock:
        STATS.update(calls=0, cache_hits=0, failures=0, by_model={})


def clear_cache():
    with _cache_lock:
        _cache.clear()


@functools.lru_cache(maxsize=64)
def _system_text(system: str, schema_json: str) -> str:
    """Stable prefix: identical bytes for every call with the same agent prompt -> provider prefix-cache hits."""
    return (f"{system}\n\nRespond ONLY with a JSON object that matches this JSON Schema exactly "
            f"(all required keys, enum values verbatim):\n{schema_json}")


def _get_text_llm(model: str | None = None):
    """Lazily build a LangChain ChatGroq model for text prompts (the default model unless *model* is given)."""
    global _text_llm, _disabled_reason
    if model and model != MODEL:
        if _get_text_llm() is None:
            return None
        if model not in _extra_llms:
            try:
                from langchain_groq import ChatGroq
                kw = {"model": model, "temperature": 0.1, "max_retries": 1, "timeout": 30}
                if "gpt-oss" in model:
                    kw["reasoning_effort"] = "low"
                _extra_llms[model] = ChatGroq(**kw)
            except Exception as e:
                log.warning("could not init %s: %s", model, e)
                _extra_llms[model] = None
        return _extra_llms[model]
    if _text_llm is not None or _disabled_reason:
        return _text_llm
    if os.environ.get("CIVIC_AI_MODE", "auto").lower() == "rules":
        _disabled_reason = "CIVIC_AI_MODE=rules"
        return None
    if not os.environ.get("GROQ_API_KEY"):
        _disabled_reason = "no GROQ_API_KEY"
        return None
    try:
        from langchain_groq import ChatGroq
        kwargs = {"model": MODEL, "temperature": 0.1, "max_retries": 1, "timeout": 30}
        # gpt-oss reasoning models: keep reasoning short so latency and token use stay low.
        if "gpt-oss" in MODEL:
            kwargs["reasoning_effort"] = "low"
        _text_llm = ChatGroq(**kwargs)
    except Exception as e:
        _disabled_reason = f"LangChain ChatGroq init failed: {e}"
    return _text_llm


def _get_vision_llm():
    global _vision_llm, _disabled_reason
    if _vision_llm is not None:
        return _vision_llm
    if _get_text_llm() is None:
        return None
    try:
        from langchain_groq import ChatGroq
        _vision_llm = ChatGroq(model=VISION_MODEL, temperature=0.1, max_retries=1, timeout=30)
    except Exception as e:
        _disabled_reason = f"vision model init failed: {e}"
    return _vision_llm


def available() -> bool:
    return _get_text_llm() is not None


def status():
    _get_text_llm()
    return {"enabled": _text_llm is not None, "provider": "groq (via langchain-groq)",
            "model": MODEL if _text_llm else None,
            "vision_model": VISION_MODEL if _text_llm else None,
            "framework": "langchain",
            "reason": _disabled_reason,
            "stats": {"calls": STATS["calls"], "cache_hits": STATS["cache_hits"], "failures": STATS["failures"],
                      "cache_entries": len(_cache), "cache_ttl_s": CACHE_TTL,
                      "by_model": {k: {"calls": v["calls"], "failures": v["failures"],
                                       "mean_ms": round(v["total_ms"] / v["calls"], 1) if v["calls"] else 0}
                                   for k, v in STATS["by_model"].items()}}}


def _validate(data: dict, schema: dict) -> dict:
    """Belt-and-braces: even after the parser, re-check required keys and enum membership."""
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


def structured(system: str, prompt: str, schema: dict,
               image_b64: str | None = None, image_type: str | None = None,
               max_tokens: int = 2500, model: str | None = None) -> dict | None:
    """Ask the LLM for JSON matching *schema*.

    Builds a LangChain LCEL chain:  prompt_template | ChatGroq | JsonOutputParser
    Returns a validated dict, or None on any failure (caller falls back to rules).
    """
    llm = _get_vision_llm() if image_b64 else _get_text_llm(model)
    if llm is None:
        return None
    model_name = VISION_MODEL if image_b64 else (model or MODEL)
    schema_json = json.dumps(schema, sort_keys=True)
    key = _cache_key("structured", model_name, system, schema_json, prompt, max_tokens,
                     hashlib.sha256(image_b64.encode()).hexdigest() if image_b64 else "")
    cached = _cache_get(key)
    if cached is not None:
        return cached
    t0 = time.perf_counter()
    try:
        from langchain_core.messages import HumanMessage, SystemMessage
        from langchain_core.output_parsers import JsonOutputParser

        # The system turn tells the model to emit JSON matching the schema verbatim.
        sys_text = _system_text(system, schema_json)

        if image_b64:
            # Multimodal: HumanMessage with image_url block
            user_content = [{"type": "text", "text": prompt},
                            {"type": "image_url",
                             "image_url": {"url": f"data:{image_type or 'image/jpeg'};base64,{image_b64}"}}]
            messages = [SystemMessage(content=sys_text), HumanMessage(content=user_content)]
            # Bind JSON response_format so Groq enforces structured output
            bound = llm.bind(response_format={"type": "json_object"}, max_tokens=max_tokens)
            resp = bound.invoke(messages)
            data = JsonOutputParser().invoke(resp)
        else:
            # LCEL chain: prompt | llm | parser
            from langchain_core.prompts import ChatPromptTemplate
            template = ChatPromptTemplate.from_messages([("system", "{sys}"), ("human", "{q}")])
            bound = llm.bind(response_format={"type": "json_object"}, max_tokens=max_tokens)
            chain = template | bound | JsonOutputParser()
            data = chain.invoke({"sys": sys_text, "q": prompt})

        data = _validate(data, schema)
        _record(model_name, (time.perf_counter() - t0) * 1000, True)
        _cache_put(key, data)
        return data
    except Exception as e:
        _record(model_name, (time.perf_counter() - t0) * 1000, False)
        log.warning("LangChain structured call failed (%s); falling back to rules", e)
        return None


def text(system: str, prompt: str, max_tokens: int = 3000) -> str | None:
    """Free-text generation via a LangChain LCEL chain (prompt | llm | StrOutputParser)."""
    llm = _get_text_llm()
    if llm is None:
        return None
    key = _cache_key("text", MODEL, system, prompt, max_tokens)
    cached = _cache_get(key)
    if cached is not None:
        return cached
    t0 = time.perf_counter()
    try:
        from langchain_core.output_parsers import StrOutputParser
        from langchain_core.prompts import ChatPromptTemplate
        template = ChatPromptTemplate.from_messages([("system", "{sys}"), ("human", "{q}")])
        chain = template | llm.bind(max_tokens=max_tokens, temperature=0.3) | StrOutputParser()
        out = chain.invoke({"sys": system, "q": prompt}) or None
        _record(MODEL, (time.perf_counter() - t0) * 1000, out is not None)
        _cache_put(key, out)
        return out
    except Exception as e:
        _record(MODEL, (time.perf_counter() - t0) * 1000, False)
        log.warning("LangChain text call failed (%s)", e)
        return None


# ---- Convenience: Pydantic-schema-based structured output ---------------------
# Used by agents that prefer a typed Pydantic model over a raw JSON schema dict.

def structured_pydantic(system: str, prompt: str, model_cls: type) -> Any | None:
    """Return an instance of *model_cls* (a Pydantic BaseModel) parsed from the LLM.

    Uses LangChain's `.with_structured_output()` to constrain the model and parse in one step.
    """
    llm = _get_text_llm()
    if llm is None:
        return None
    try:
        from langchain_core.prompts import ChatPromptTemplate
        template = ChatPromptTemplate.from_messages([("system", "{sys}"), ("human", "{q}")])
        structured_llm = llm.with_structured_output(model_cls)
        chain = template | structured_llm
        return chain.invoke({"sys": system, "q": prompt})
    except Exception as e:
        log.warning("LangChain structured_pydantic call failed (%s)", e)
        return None
