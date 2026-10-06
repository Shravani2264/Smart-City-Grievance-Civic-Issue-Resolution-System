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
"""
import json
import logging
import os
from typing import Any

log = logging.getLogger("civic.llm")
MODEL = os.environ.get("GROQ_MODEL", "openai/gpt-oss-120b")
VISION_MODEL = os.environ.get("GROQ_VISION_MODEL", "qwen/qwen3.8-27b")

_text_llm = None
_vision_llm = None
_disabled_reason: str | None = None


def _get_text_llm():
    """Lazily build a LangChain ChatGroq model for text-only prompts."""
    global _text_llm, _disabled_reason
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
            "reason": _disabled_reason}


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
               max_tokens: int = 2500) -> dict | None:
    """Ask the LLM for JSON matching *schema*.

    Builds a LangChain LCEL chain:  prompt_template | ChatGroq | JsonOutputParser
    Returns a validated dict, or None on any failure (caller falls back to rules).
    """
    llm = _get_vision_llm() if image_b64 else _get_text_llm()
    if llm is None:
        return None
    try:
        from langchain_core.messages import HumanMessage, SystemMessage
        from langchain_core.output_parsers import JsonOutputParser

        # The system turn tells the model to emit JSON matching the schema verbatim.
        sys_text = (f"{system}\n\nRespond ONLY with a JSON object that matches this JSON Schema exactly "
                    f"(all required keys, enum values verbatim):\n{json.dumps(schema)}")

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

        return _validate(data, schema)
    except Exception as e:
        log.warning("LangChain structured call failed (%s); falling back to rules", e)
        return None


def text(system: str, prompt: str, max_tokens: int = 3000) -> str | None:
    """Free-text generation via a LangChain LCEL chain (prompt | llm | StrOutputParser)."""
    llm = _get_text_llm()
    if llm is None:
        return None
    try:
        from langchain_core.output_parsers import StrOutputParser
        from langchain_core.prompts import ChatPromptTemplate
        template = ChatPromptTemplate.from_messages([("system", "{sys}"), ("human", "{q}")])
        chain = template | llm.bind(max_tokens=max_tokens, temperature=0.3) | StrOutputParser()
        out = chain.invoke({"sys": system, "q": prompt})
        return out or None
    except Exception as e:
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
