"""Policy RAG: retrieval-augmented grounding over the CivicPulse policy corpus.

Corpus
  * Hand-written clauses in ``backend/policies/*.md`` (escalation, routing, closure, monsoon, AI governance).
  * Clauses generated from ``config.py`` at index time: one service standard per issue type (POL-SLA-*) and
    the co-notification table (POL-RTE-003). Because they are generated from the same tables the agents
    use, a cited SLA can never drift from the SLA that was actually applied.

Index
  SQLite FTS5 with BM25 ranking and Porter stemming, built in memory at first use (well under 50 ms for
  this corpus). No vector DB, no extra dependency, nothing written next to the OneDrive-synced project.

Uses
  * ``cite(ids)``         - deterministic lookup: agents attach the clause that justified each decision.
  * ``search(query)``     - BM25 retrieval.
  * ``ask(question)``     - retrieve -> LLM answers *only* from the retrieved clauses -> citations validated
                           against what was retrieved. Without an LLM, an extractive answer is returned.
  * ``context_block()``   - formats clauses for an LLM prompt (used by the transparency narrative).
"""
import os
import re
import sqlite3
import threading
import time
from dataclasses import dataclass

from . import guard, llm
from .config import DEPARTMENTS, EMERGENCY_TEAM, ISSUE_TYPES, PRIORITY_FACTOR, SECONDARY_NOTIFY, SLA_FLOOR_H

POLICY_DIR = os.environ.get("CIVIC_POLICY_DIR", os.path.join(os.path.dirname(__file__), "..", "policies"))
VERSION = "2026.11"
_ID_RE = re.compile(r"\bPOL-[A-Z]+-[A-Z0-9_]+\b")
_STOP = set("a an the is are was were be of to in on at for and or what when who how why which does do did can "
            "will should would my our this that it its with by from about there their any i we you".split())


@dataclass(frozen=True)
class Clause:
    id: str
    title: str
    body: str
    tags: tuple
    version: str
    source: str

    @property
    def tag(self) -> str:
        return f"[{self.id} v{self.version}]"

    def ref(self, score: float | None = None) -> dict:
        r = {"id": self.id, "title": self.title, "version": self.version, "source": self.source}
        if score is not None:
            r["score"] = round(score, 3)
        return r


# ---- corpus loading -----------------------------------------------------------------------------

def _parse_markdown(path: str) -> list[Clause]:
    """`## POL-X-001 | Title` starts a clause; `tags:` / `version:` lines follow; the rest is the body."""
    with open(path, encoding="utf-8") as f:
        text = f.read()
    out = []
    for block in re.split(r"(?m)^## ", text)[1:]:
        head, _, rest = block.partition("\n")
        cid, _, title = head.partition("|")
        tags, version, body = (), VERSION, []
        for line in rest.splitlines():
            if line.startswith("tags:") and not body:
                tags = tuple(t.strip() for t in line[5:].split(",") if t.strip())
            elif line.startswith("version:") and not body:
                version = line[8:].strip()
            elif line.strip() or body:
                body.append(line)
        out.append(Clause(cid.strip(), title.strip(), "\n".join(body).strip(), tags, version, os.path.basename(path)))
    return out


def _generated() -> list[Clause]:
    mult = ", ".join(f"{p} x{f:g}" for p, f in PRIORITY_FACTOR.items())
    out = []
    for key, m in ISSUE_TYPES.items():
        dept = DEPARTMENTS[m["dept"]]
        body = (f"Complaints classified as '{m['label']}' ({m['category']}) are owned by {dept['name']}. The base service "
                f"standard is {m['sla']} hours from the time of the report. The standard is adjusted by priority band "
                f"({mult}) with a floor of {SLA_FLOOR_H} hours. First escalation goes to the {dept['supervisor']}, "
                f"breach escalation to the {dept['officer']}. Typical wording: {', '.join(m['kw'][:8]) or 'any other civic issue'}.")
        out.append(Clause(f"POL-SLA-{key.upper()}", f"Service standard: {m['label']}", body,
                          ("sla", "service standard", "deadline", m["category"].lower(), m["label"].lower()), VERSION, "config.py"))
    lines = []
    for (it, sig), extra in SECONDARY_NOTIFY.items():
        if extra:
            cond = f" when the complaint carries a {sig.replace('_', ' ')} signal" if sig else ""
            lines.append(f"- {ISSUE_TYPES[it]['label']}{cond}: also notify {', '.join(DEPARTMENTS[c]['name'] for c in extra)}.")
    out.append(Clause("POL-RTE-003", "Co-notification of other departments",
                      "Besides the owning department, these departments are notified so they can act in parallel:\n" + "\n".join(lines)
                      + f"\nThe {EMERGENCY_TEAM} is notified under POL-RTE-002.",
                      ("routing", "notify", "co-notification", "traffic police", "public health"), VERSION, "config.py"))
    return out


# ---- index ----------------------------------------------------------------------------------------

class PolicyIndex:
    def __init__(self, policy_dir: str = POLICY_DIR):
        self.policy_dir = policy_dir
        self._lock = threading.Lock()
        self._conn: sqlite3.Connection | None = None
        self.clauses: dict[str, Clause] = {}
        self.build_ms = 0.0

    def _build(self):
        t0 = time.perf_counter()
        clauses = []
        if os.path.isdir(self.policy_dir):
            for name in sorted(os.listdir(self.policy_dir)):
                if name.endswith(".md"):
                    clauses += _parse_markdown(os.path.join(self.policy_dir, name))
        clauses += _generated()
        conn = sqlite3.connect(":memory:", check_same_thread=False)
        conn.execute("CREATE VIRTUAL TABLE p USING fts5(id UNINDEXED, title, tags, body, tokenize='porter unicode61')")
        conn.executemany("INSERT INTO p VALUES (?,?,?,?)", [(c.id, c.title, " ".join(c.tags), c.body) for c in clauses])
        self.clauses = {c.id: c for c in clauses}
        self._conn = conn
        self.build_ms = (time.perf_counter() - t0) * 1000

    def _ready(self):
        if self._conn is None:
            with self._lock:
                if self._conn is None:
                    self._build()

    def get(self, cid: str) -> Clause | None:
        self._ready()
        return self.clauses.get(cid)

    def search(self, query: str, k: int = 4, prefix: str = "") -> list[tuple[Clause, float]]:
        """BM25 search (title x5, tags x3, body x1). Returns [(clause, relevance)], best first."""
        self._ready()
        terms = [t for t in re.findall(r"[a-z0-9]+", (query or "").lower()) if t not in _STOP and len(t) > 1]
        if not terms:
            return []
        match = " OR ".join(f'"{t}"' for t in dict.fromkeys(terms))
        sql = "SELECT id, bm25(p, 0.0, 5.0, 3.0, 1.0) AS s FROM p WHERE p MATCH ?"
        args: list = [match]
        if prefix:
            sql += " AND id LIKE ?"
            args.append(prefix + "%")
        sql += " ORDER BY s LIMIT ?"
        args.append(k)
        with self._lock:
            rows = self._conn.execute(sql, args).fetchall()
        return [(self.clauses[r[0]], -r[1]) for r in rows]  # bm25() is lower-is-better; flip to a relevance

    def stats(self) -> dict:
        self._ready()
        return {"clauses": len(self.clauses), "generated": sum(c.source == "config.py" for c in self.clauses.values()),
                "version": VERSION, "index": "sqlite-fts5 bm25 (porter)", "build_ms": round(self.build_ms, 1)}


INDEX = PolicyIndex()


# ---- helpers used by agents ------------------------------------------------------------------------

def cite(*ids: str) -> tuple[list[dict], str]:
    """Deterministic citation for a decision already made by rules: (refs, ' Policy: [ID vX], ...')."""
    found = [c for c in (INDEX.get(i) for i in ids if i) if c]
    return [c.ref() for c in found], (" Policy: " + ", ".join(c.tag for c in found) + "." if found else "")


def sla_clause_id(issue_type: str) -> str:
    return f"POL-SLA-{issue_type.upper()}"


def context_block(clauses: list[Clause]) -> str:
    """Trusted policy text for an LLM prompt, clearly delimited and individually tagged."""
    parts = [f"{c.tag} {c.title}\n{c.body}" for c in clauses]
    return "<policy_context>\n" + "\n\n".join(parts) + "\n</policy_context>"


_DASHES = re.compile("[‐‑‒–—―−﹣－]")


def normalise_ids(text: str) -> str:
    """Models often emit IDs with typographic hyphens (e.g. U+2011 'POL‑ESC‑001'); fold them to ASCII '-'."""
    return _DASHES.sub("-", text or "")


def strip_unknown_citations(text: str, allowed: set[str]) -> str:
    """Remove any POL-* id the model produced that was not in the retrieved context (no invented policy)."""
    return _ID_RE.sub(lambda m: m.group(0) if m.group(0) in allowed else "(uncited)", normalise_ids(text))


# ---- RAG question answering ------------------------------------------------------------------------

ASK_SYSTEM = (
    "You answer questions about the CivicPulse municipal grievance policy. Use ONLY the clauses inside "
    "<policy_context>. Quote numbers exactly as written. Cite every clause you rely on by its ID in square "
    "brackets, e.g. [POL-ESC-001]. If the clauses do not answer the question, say that no policy clause covers "
    "it; do not guess. Keep the answer under 120 words.\n\n" + guard.ISOLATION_CLAUSE
)
ASK_SCHEMA = {
    "type": "object",
    "properties": {
        "answer": {"type": "string"},
        "cited_ids": {"type": "array", "items": {"type": "string"}},
        "covered": {"type": "boolean", "description": "false if the clauses do not answer the question"},
    },
    "required": ["answer", "cited_ids", "covered"],
    "additionalProperties": False,
}


def _first_sentences(text: str, n: int = 2) -> str:
    flat = re.sub(r"\s+", " ", text.replace("\n- ", "; ")).strip()
    return " ".join(re.split(r"(?<=[.!?])\s+", flat)[:n])


def ask(question: str, k: int = 4) -> dict:
    t0 = time.perf_counter()
    clean, gr = guard.sanitise(question)
    hits = INDEX.search(clean, k=k)
    retrieved = [c.ref(s) for c, s in hits]
    base = {"question": clean, "retrieved": retrieved, "security": gr}
    if not hits:
        return {**base, "answer": "No policy clause matches this question.", "citations": [], "mode": "none",
                "ms": round((time.perf_counter() - t0) * 1000, 1)}

    clauses = [c for c, _ in hits]
    allowed = {c.id for c in clauses}
    ai = llm.structured(ASK_SYSTEM, f"{context_block(clauses)}\n\nQuestion:\n{guard.wrap_untrusted(clean)}", ASK_SCHEMA, max_tokens=900) \
        if llm.available() else None
    if ai:
        raw_ids = _ID_RE.findall(normalise_ids(" ".join(map(str, ai["cited_ids"])) + " " + ai["answer"]))
        cited = [i for i in dict.fromkeys(raw_ids) if i in allowed]   # citation grounding check
        answer = strip_unknown_citations(ai["answer"], allowed)
        if ai["covered"] and cited:
            return {**base, "answer": answer, "citations": [INDEX.get(i).ref() for i in cited], "mode": "rag+llm",
                    "ms": round((time.perf_counter() - t0) * 1000, 1)}
        if not ai["covered"]:
            return {**base, "answer": answer or "No policy clause covers this question.", "citations": [], "mode": "rag+llm",
                    "ms": round((time.perf_counter() - t0) * 1000, 1)}
        # covered but uncited -> not trustworthy; fall through to the extractive answer

    top = clauses[:2]
    answer = " ".join(f"{_first_sentences(c.body)} {c.tag}" for c in top)
    return {**base, "answer": answer, "citations": [c.ref() for c in top], "mode": "rag-extractive",
            "ms": round((time.perf_counter() - t0) * 1000, 1)}
