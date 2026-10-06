"""End-to-end checks of the agent pipeline against a throwaway database (rules mode, no network).

Run:  cd backend && python -m pytest -q tests
"""
import os
import tempfile

os.environ["CIVIC_DB"] = os.path.join(tempfile.mkdtemp(), "test.db")
os.environ["CIVIC_AI_MODE"] = "rules"

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app import db  # noqa: E402
from app.main import app  # noqa: E402


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:  # lifespan seeds the city history
        yield c


def submit(client, text, location="", name="Test Citizen"):
    r = client.post("/api/complaints", data={"text": text, "location": location, "name": name})
    assert r.status_code == 200, r.text
    return r.json()


def test_problem_statement_scenario(client):
    c = submit(client, "Garbage not collected in my street for 5 days near Dharavi.")
    assert c["category"] == "Solid Waste Management"
    assert c["department"] == "BMC Solid Waste Management Dept"
    # Seeded history has a Dharavi garbage cluster -> this report should merge
    assert c["cluster_id"] and c["cluster_size"] >= 5
    agents = [s["agent"] for s in c["trace"]]
    assert len(agents) == 11 and agents[-1] == "Master Orchestrator"


def test_critical_hazard_routing_and_sla(client):
    c = submit(client, "Open manhole on the road right outside the school gate, children walk here", "near Dadar station")
    assert c["issue_type"] == "open_manhole"
    assert c["priority"] == "CRITICAL" and c["sla_hours"] <= 6
    routing = c["severity_factors"]["routing"]
    assert "NDRF Mumbai / BMC Disaster Management Cell" in routing["notify"]


def test_location_landmark_and_jurisdiction(client):
    c = submit(client, "Water leaking from the pipeline near Sion hospital, flowing across the road", "Sion")
    assert c["department"] == "BMC Hydraulic Engineering Dept" and c["sla_hours"] <= 24


def test_lifecycle_verification_and_reopen(client):
    c = submit(client, "Streetlight not working for 3 days, dark at night", "Malad")
    cid = c["id"]
    assert client.post(f"/api/complaints/{cid}/status", json={"status": "Closed"}).status_code == 409  # illegal jump
    for s in ("In Progress", "Inspection", "Resolved"):
        r = client.post(f"/api/complaints/{cid}/status", json={"status": s})
        assert r.status_code == 200, r.text
    assert r.json()["verification"]["status"] == "pending"
    r = client.post(f"/api/complaints/{cid}/feedback", json={"rating": 1, "comment": "still dark"})
    assert r.json()["complaint"]["status"] == "Reopened"
    for s in ("In Progress", "Resolved"):
        client.post(f"/api/complaints/{cid}/status", json={"status": s})
    r = client.post(f"/api/complaints/{cid}/feedback", json={"rating": 5})
    assert r.json()["complaint"]["status"] == "Closed"


def test_escalation_fires_after_time_warp(client):
    c = submit(client, "Live wire hanging and sparking near Andheri station", "near Andheri station")
    assert c["priority"] == "CRITICAL"
    client.post(f"/api/complaints/{c['id']}/status", json={"status": "In Progress"})  # operator-owned: simulator won't resolve it
    r = client.post("/api/sim/advance", json={"hours": c["sla_hours"] * 1.6})
    assert r.status_code == 200
    d = client.get(f"/api/complaints/{c['id']}").json()
    assert d["escalation_level"] == 3
    assert any("NDRF" in e["target"] or "Emergency" in e["target"] or "Commissioner" in e["target"] for e in d["escalations"])


def test_reports_and_predictions(client):
    r = client.get("/api/report?days=30&narrative=true").json()
    assert r["total_complaints"] > 300 and 0 < r["city_efficiency"] <= 100
    assert r["narrative_mode"] == "template" and "###" in r["narrative"]
    assert len(r["wards"]) == 24 and r["departments"]
    p = client.get("/api/predict?rain=80").json()
    assert p["waterlogging"][0]["risk"] >= p["waterlogging"][-1]["risk"]
    assert client.get("/api/report.csv").status_code == 200


def test_rules_classifier_paraphrases():
    from app.agents.understanding import classify_rules
    assert classify_rules("Exposed electric wire on the pole")[0] == "exposed_wire"
    assert classify_rules("Road surface cracked and damaged after rains")[0] == "road_damage"
    assert classify_rules("kachra pile not collected")[0] == "garbage_uncollected"
    assert db.scalar("SELECT COUNT(*) FROM complaints") > 0
