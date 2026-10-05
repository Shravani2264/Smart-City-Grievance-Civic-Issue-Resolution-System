"""Agent 1 - Complaint Understanding: turns free citizen text (and an optional photo) into a structured issue."""
import re

from .. import llm
from ..config import ISSUE_TYPES, URGENCY_SIGNALS
from .base import Agent, AgentResult

NUM_WORDS = {"one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10,
             "a": 1, "an": 1, "few": 3, "several": 4}

SYSTEM = (
    "You are the intake analyst for a municipal grievance system. Classify a citizen complaint into exactly one "
    "issue_type from the allowed list, pull out the location phrase the citizen used, estimate how long the problem "
    "has persisted, and flag urgency signals that are actually supported by the text or photo. Be conservative: do "
    "not invent signals. Citizens may write in Indian English or mix in Hindi/Marathi words (e.g. kachra = garbage, "
    "nala = drain, paani = water)."
)

SCHEMA = {
    "type": "object",
    "properties": {
        "issue_type": {"type": "string", "enum": list(ISSUE_TYPES)},
        "title": {"type": "string", "description": "Short neutral ticket title, max 8 words"},
        "location_mention": {"type": "string", "description": "Location phrase from the complaint, or empty string"},
        "duration_days": {"type": "number", "description": "How long the issue has persisted in days; 0 if not stated"},
        "urgency_signals": {"type": "array", "items": {"type": "string", "enum": list(URGENCY_SIGNALS)}},
        "priority_hint": {"type": "string", "enum": ["low", "medium", "high", "critical"]},
        "confidence": {"type": "number", "description": "0-1 confidence in issue_type"},
        "image_findings": {"type": "string", "description": "What the photo shows, or empty string if no photo"},
        "reasoning": {"type": "string", "description": "One sentence explaining the classification"},
    },
    "required": ["issue_type", "title", "location_mention", "duration_days", "urgency_signals", "priority_hint",
                 "confidence", "image_findings", "reasoning"],
    "additionalProperties": False,
}


def _kw_hit(kw: str, t: str, words: set) -> float:
    """Exact phrase scores fully; a multi-word keyword whose words all appear (any order) scores 80%."""
    if kw in t:
        return 1.0
    parts = kw.split()
    if len(parts) > 1 and all(any(w.startswith(p) for w in words) for p in parts):
        return 0.8
    return 0.0


def classify_rules(text: str):
    t = text.lower()
    words = set(re.findall(r"[a-z]+", t))
    scores = {}
    for key, meta in ISSUE_TYPES.items():
        s = 0.0
        for kw in meta["kw"]:
            hit = _kw_hit(kw, t, words)
            if hit:
                s += hit * (1 + len(kw) / 12)  # longer, more specific phrases weigh more
        if s:
            scores[key] = s + meta["base"] / 500  # tiny tie-break toward more serious types
    if not scores:
        return "other", 0.3, {}
    best = max(scores, key=scores.get)
    total = sum(scores.values())
    return best, round(min(0.97, 0.55 + 0.42 * scores[best] / total), 2), scores


def detect_signals(text: str):
    t = text.lower()
    found = {}
    for sig, (kws, _) in URGENCY_SIGNALS.items():
        hits = [k for k in kws if k in t]
        if hits:
            found[sig] = hits[:3]
    return found


def extract_duration(text: str) -> float:
    t = text.lower()
    m = re.search(r"(\d+|" + "|".join(NUM_WORDS) + r")\s*(hours?|hrs?|days?|weeks?|months?)", t)
    if m:
        n = float(m.group(1)) if m.group(1).isdigit() else NUM_WORDS[m.group(1)]
        unit = m.group(2)
        return round(n / 24 if unit.startswith("h") else n * 7 if unit.startswith("w") else n * 30 if unit.startswith("m") else n, 2)
    if "since yesterday" in t or "last night" in t:
        return 1
    if "since morning" in t or "today" in t:
        return 0.3
    if "for a week" in t or "last week" in t:
        return 7
    return 0


def extract_location_phrase(text: str) -> str:
    m = re.search(r"\b(?:near|opposite|behind|beside|next to|in front of|at|in|on)\s+((?:the\s+)?[A-Za-z0-9][\w\s\-]{2,40}?)(?=[,.!?]|$| for | since | and | because )", text, re.I)
    sector = re.search(r"sector[\s\-]*\d{1,2}", text, re.I)
    parts = [p for p in [m.group(1).strip() if m else "", sector.group(0) if sector else ""] if p]
    return ", ".join(dict.fromkeys(parts))


class ComplaintUnderstandingAgent(Agent):
    name = "Complaint Understanding"

    def run(self, text: str, image_b64: str | None = None, image_type: str | None = None, use_ai: bool = True) -> AgentResult:
        return self.timed(self._run, text, image_b64, image_type, use_ai)

    def _run(self, text, image_b64, image_type, use_ai):
        issue, conf, scores = classify_rules(text)
        signals = detect_signals(text)
        duration = extract_duration(text)
        loc = extract_location_phrase(text)
        title = ISSUE_TYPES[issue]["label"]
        mode, reasoning, image_findings = "rules", "", ""

        ai = None
        if use_ai and llm.available():
            prompt = f"Citizen complaint:\n{text or '(no text, photo only - classify from the image)'}"
            ai = llm.structured(SYSTEM, prompt, SCHEMA, image_b64=image_b64, image_type=image_type)

        if ai:
            mode = "ai+rules"
            issue, conf = ai["issue_type"], round(float(ai["confidence"]), 2)
            title = ai["title"] or ISSUE_TYPES[issue]["label"]
            loc = ai["location_mention"] or loc
            duration = float(ai["duration_days"]) or duration
            for s in ai["urgency_signals"]:
                signals.setdefault(s, ["model-detected"])
            image_findings = ai["image_findings"]
            reasoning = ai["reasoning"]
        else:
            top = sorted(scores.items(), key=lambda kv: -kv[1])[:3]
            reasoning = (f"Keyword evidence favoured '{issue}'" + (f" over {', '.join(k for k, _ in top[1:])}" if len(top) > 1 else "")
                         + ("." if issue != "other" else " (no known pattern matched; routed to the service cell)."))
            if image_b64:
                image_findings = "Photo attached and stored as evidence. Vision classification runs when AI mode is enabled."

        meta = ISSUE_TYPES[issue]
        hint = "critical" if meta["base"] >= 80 else "high" if meta["base"] >= 60 or len(signals) >= 2 else "medium" if meta["base"] >= 35 else "low"
        if ai:
            hint = ai["priority_hint"]
        output = {
            "issue_type": issue, "issue_label": meta["label"], "category": meta["category"], "title": title,
            "location": loc, "duration_days": duration, "priority_hint": hint, "confidence": conf,
            "urgency_signals": signals, "image_findings": image_findings,
        }
        sig_txt = ", ".join(s.replace("_", " ") for s in signals) or "none"
        return AgentResult(self.name, output, f"{reasoning} Urgency signals: {sig_txt}." + (f" Persisting ~{duration:g} days." if duration else ""), mode)
