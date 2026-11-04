"""Policy RAG, MCP client and LLM-cascade checks. Fully offline: rules mode, and a local fake MCP server.

Run:  cd backend && python -m pytest -q tests
"""
import os
import sys
import tempfile

os.environ.setdefault("CIVIC_DB", os.path.join(tempfile.mkdtemp(), "test.db"))
os.environ["CIVIC_AI_MODE"] = "rules"
os.environ["CIVIC_MCP_WARM"] = "off"

import pytest  # noqa: E402

from app import db, llm, policy_rag  # noqa: E402
from app.config import ISSUE_TYPES, PRIORITY_FACTOR  # noqa: E402
from app.mcp_client import BACKEND_DIR, MCPHub  # noqa: E402

FAKE = {"rainfall": {"command": sys.executable, "args": ["-m", "tests.fake_rainfall_server"], "cwd": BACKEND_DIR}}


# ---------------------------------------------------------------- policy RAG

def test_policy_index_covers_every_issue_type():
    st = policy_rag.INDEX.stats()
    assert st["clauses"] >= len(ISSUE_TYPES) + 15
    for key, meta in ISSUE_TYPES.items():
        c = policy_rag.INDEX.get(policy_rag.sla_clause_id(key))
        assert c is not None and f"{meta['sla']} hours" in c.body   # generated from config: cannot drift


@pytest.mark.parametrize("query,expected", [
    ("when does an overdue ticket reach the commissioner", "POL-ESC-001"),
    ("SLA for an open manhole", "POL-SLA-OPEN_MANHOLE"),
    ("low rating reopen closed ticket", "POL-VER-002"),
    ("pumps advisory heavy rain flooding", "POL-MON-001"),
    ("can the AI decide which department gets the ticket", "POL-AI-001"),
    ("kachra not collected deadline", "POL-SLA-GARBAGE_UNCOLLECTED"),
])
def test_policy_retrieval_hits_top3(query, expected):
    ids = [c.id for c, _ in policy_rag.INDEX.search(query, k=3)]
    assert expected in ids, ids


def test_policy_ask_offline_is_extractive_and_cited():
    r = policy_rag.ask("What happens when the SLA is breached?")
    assert r["mode"] == "rag-extractive" and r["citations"]
    assert all(c["id"] in {x["id"] for x in r["retrieved"]} for c in r["citations"])
    assert "[POL-" in r["answer"]


def test_policy_ask_rejects_invented_citations(monkeypatch):
    monkeypatch.setattr(llm, "available", lambda: True)
    monkeypatch.setattr(llm, "structured", lambda *a, **k: {"answer": "Per [POL-FAKE-999] tickets close in 1 h.",
                                                            "cited_ids": ["POL-FAKE-999"], "covered": True})
    r = policy_rag.ask("How fast are tickets closed?")
    assert "POL-FAKE-999" not in r["answer"] and r["mode"] == "rag-extractive"   # uncited -> fall back


def test_sla_agent_cites_policy():
    from app.agents.sla import SLAAgent
    out = SLAAgent().run("pothole", "HIGH", 0).output
    assert out["sla_hours"] == ISSUE_TYPES["pothole"]["sla"] * PRIORITY_FACTOR["HIGH"]
    assert {p["id"] for p in out["policy"]} == {"POL-SLA-POTHOLE", "POL-ESC-001"}


def test_policy_endpoints():
    from fastapi.testclient import TestClient
    from app.main import app
    with TestClient(app) as c:
        assert c.get("/api/policies").json()["stats"]["clauses"] > 20
        assert c.get("/api/policies/POL-ESC-001").json()["title"] == "Escalation ladder"
        assert c.get("/api/policies/NOPE").status_code == 404
        a = c.post("/api/policies/ask", json={"question": "Who is notified for an exposed live wire?"}).json()
        assert "POL-RTE-002" in {x["id"] for x in a["retrieved"]}
        # A routed ticket carries the policy clauses that justified it
        t = c.post("/api/complaints", data={"text": "Open manhole outside the school gate", "location": "Dadar"}).json()
        cited = {p["id"] for s in t["trace"] for p in (s["output"].get("policy") or [])}
        assert {"POL-SLA-OPEN_MANHOLE", "POL-RTE-002", "POL-ESC-003"} <= cited


# ---------------------------------------------------------------- MCP client

@pytest.fixture(scope="module")
def hub():
    h = MCPHub(servers=FAKE, enabled=True)
    yield h
    h.close()


def test_mcp_call_and_session_reuse(hub):
    r = hub.call("rainfall", "get_rainfall_forecast", {"hours": 3})
    assert r["source"] == "fake" and r["peak_mm_hr"] == 64
    hub.call("rainfall", "get_rainfall_forecast", {"hours": 2})
    st = hub.status()
    assert st["servers"][0]["connected"] and st["stats"]["connects"] == 1      # one process, many calls
    assert st["servers"][0]["tools"][0]["name"] == "get_rainfall_forecast"


def test_mcp_ttl_cache(hub):
    before = hub.stats["cache_hits"]
    hub.call("rainfall", "get_rainfall_forecast", {"hours": 1}, ttl=60)
    hub.call("rainfall", "get_rainfall_forecast", {"hours": 1}, ttl=60)
    assert hub.stats["cache_hits"] == before + 1


def test_predictive_agent_uses_mcp_and_validates(hub):
    from app.agents.predictive import PredictiveAgent
    live = PredictiveAgent().live_rainfall(3, hub=hub)
    assert live["ok"] and live["rain_mm_hr"] == 64 and live["source"].startswith("mcp:rainfall")


def test_mcp_failure_falls_back():
    broken = MCPHub(servers={"rainfall": {"command": sys.executable, "args": ["-c", "import sys; sys.exit(1)"]}}, enabled=True)
    from app.agents.predictive import PredictiveAgent
    try:
        live = PredictiveAgent().live_rainfall(3, hub=broken)
        assert not live["ok"] and live["reason"]
        assert broken.call("rainfall", "get_rainfall_forecast") is None   # backoff: no respawn storm
    finally:
        broken.close()
    assert MCPHub(servers=FAKE, enabled=False).call("rainfall", "get_rainfall_forecast") is None


# ---------------------------------------------------------------- LLM cascade + cache

def test_cascade_skips_llm_when_rules_confident(monkeypatch):
    from app.agents import understanding as u
    calls = []
    monkeypatch.setattr(llm, "available", lambda: True)
    monkeypatch.setattr(llm, "structured", lambda *a, **k: calls.append(1) or None)
    confident = u.ComplaintUnderstandingAgent().run("Huge pothole on the main road").output
    assert confident["cascade"]["tier"] == "rules-accepted" and not calls
    vague = u.ComplaintUnderstandingAgent().run("A huge branch snapped and is blocking half the lane").output
    assert len(calls) == 1 and vague["cascade"]["tier"] == "rules"   # uncertain -> LLM consulted (stub returned None)


def test_llm_response_cache_roundtrip():
    llm.clear_cache()
    k = llm._cache_key("x", 1)
    llm._cache_put(k, {"a": [1]})
    got = llm._cache_get(k)
    got["a"].append(2)                       # callers may mutate; cache must stay intact
    assert llm._cache_get(k) == {"a": [1]}
    assert db.now() > 0


def test_typographic_hyphens_in_citations_are_normalised(monkeypatch):
    monkeypatch.setattr(llm, "available", lambda: True)
    monkeypatch.setattr(llm, "structured", lambda *a, **k: {"answer": "Level 3 at 150% [POL\u2011ESC\u2011001]. Also [POL\u2011FAKE\u2011001].",
                                                            "cited_ids": ["POL\u2011ESC\u2011001"], "covered": True})
    r = policy_rag.ask("When does an overdue ticket reach the commissioner?")
    assert r["mode"] == "rag+llm" and [c["id"] for c in r["citations"]] == ["POL-ESC-001"]
    assert "POL-ESC-001" in r["answer"] and "FAKE" not in r["answer"]
