"""CivicPulse API - Autonomous Civic Grievance & Urban Operations System."""
import asyncio
import base64
import csv
import io
import logging
import os
from collections import Counter
from contextlib import asynccontextmanager

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from . import db, llm
from .agents.orchestrator import Orchestrator
from .agents.predictive import PredictiveAgent
from .agents.reporting import TransparencyReportAgent, efficiency
from .agents.sla import sla_state
from .agents.workflow import ALLOWED
from .config import CATEGORY_COLORS, CITY, DEPARTMENTS, GRID_COLS, GRID_ROWS, LAT_MAX, LAT_MIN, LNG_MAX, LNG_MIN, WARDS

logging.basicConfig(level=logging.INFO)


@asynccontextmanager
async def lifespan(_app):
    db.init()
    if not db.scalar("SELECT COUNT(*) FROM complaints"):
        from .seed import seed
        await asyncio.to_thread(seed)

    async def loop():
        while True:
            await asyncio.sleep(TICK_SECONDS)
            try:
                await asyncio.to_thread(orch.tick)
            except Exception:
                logging.exception("tick failed")
    task = asyncio.create_task(loop())
    yield
    task.cancel()


app = FastAPI(title="CivicPulse API", version="2.0", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])
orch = Orchestrator()
OPEN = ("Reported", "Assigned", "In Progress", "Inspection", "Reopened")
TICK_SECONDS = 20

AGENTS = [
    ("Complaint Understanding", "Extracts issue type, urgency signals, duration and location phrase from text or photo"),
    ("Location Intelligence", "Geotags vague places; maps to ward, zone, municipality and jurisdiction"),
    ("Department Routing", "Assigns the accountable department and least-loaded crew; notifies co-owners"),
    ("Priority & Severity", "Explainable 0-100 risk score from hazard, signals, persistence, exposure, cluster size"),
    ("Duplicate Detection", "Geo + text + time similarity clusters repeat reports into one civic incident"),
    ("SLA Management", "Sets resolution deadlines and tracks breach risk"),
    ("Escalation", "Climbs Supervisor -> District Officer -> Commissioner/Emergency on delay"),
    ("Workflow Tracking", "Lifecycle state machine; keeps clustered reports in sync"),
    ("Resolution Verification", "Citizen feedback, follow-up reports and time-based confirmation before closure"),
    ("Transparency Reporting", "Public metrics, ward/department efficiency scores and narrative reports"),
    ("Master Orchestrator", "Coordinates intake, routing, tracking, escalation and reporting"),
]


def view(c, now=None, full=False):
    now = now or db.now()
    out = {k: c[k] for k in ("id", "created_at", "text", "location_text", "citizen_name", "citizen_id", "has_image", "issue_type", "issue_label",
                             "category", "title", "lat", "lng", "ward", "sector", "landmark", "dept", "department", "unit", "severity_score",
                             "priority", "sla_hours", "due_at", "status", "escalation_level", "cluster_id", "is_primary", "resolved_at",
                             "closed_at", "feedback_rating", "reopen_count", "ai_mode", "duration_days")}
    out["ward_name"] = WARDS[c["ward"]]["name"]
    out["color"] = CATEGORY_COLORS.get(c["category"], "blue")
    out["sla"] = sla_state(c, now)
    out["signals"] = list((c["urgency_signals"] or {}).keys())
    if c["cluster_id"]:
        cl = db.get("clusters", c["cluster_id"])
        out["cluster_size"] = cl["count"] if cl else 1
    else:
        out["cluster_size"] = 1
    if full:
        for k in ("urgency_signals", "severity_factors", "location_meta", "escalations", "history", "trace", "verification", "image_analysis"):
            out[k] = c[k]
        out["allowed_next"] = sorted(ALLOWED.get(c["status"], []))
    return out


@app.get("/api/health")
def health():
    return {"ok": True, "ai": llm.status(), "clock": db.now(), "clock_offset_hours": db.get_setting("clock_offset_hours", 0),
            "agents": len(AGENTS)}


@app.get("/api/agents")
def agents():
    now = db.now()
    day = db.query("SELECT agent, COUNT(*) n FROM events WHERE at>=? GROUP BY agent", (now - 86400,))
    counts = {r["agent"]: r["n"] for r in day}
    processed = db.scalar("SELECT COUNT(*) FROM complaints WHERE created_at>=?", (now - 86400,)) or 0
    return [{"name": n, "role": r, "actions_24h": counts.get(n, processed)} for n, r in AGENTS]


@app.get("/api/dashboard")
def dashboard():
    now = db.now()
    open_rows = db.query(f"SELECT * FROM complaints WHERE status IN ({','.join('?' * len(OPEN))})", OPEN)
    primaries = [c for c in open_rows if c["is_primary"]]
    states = Counter(sla_state(c, now)["state"] for c in primaries)
    today = db.query("SELECT * FROM complaints WHERE created_at>=?", (now - 86400,))
    resolved_today = db.scalar("SELECT COUNT(*) FROM complaints WHERE resolved_at>=?", (now - 86400,)) or 0
    week = db.query("SELECT * FROM complaints WHERE created_at>=?", (now - 7 * 86400,))
    res_h = [(c["resolved_at"] - c["created_at"]) / 3600 for c in week if c["resolved_at"]]
    met = [c for c in week if c["resolved_at"]]

    def risk_key(c):
        st = sla_state(c, now)
        return (-{"breached": 3, "at_risk": 2, "on_track": 0}[st["state"]] - c["severity_score"] / 50, st["remaining_h"])
    queue = [view(c, now) for c in sorted(primaries, key=risk_key)[:8]]

    cat = Counter(c["category"] for c in week)
    by_dept = {}
    for c in db.query("SELECT * FROM complaints WHERE created_at>=?", (now - 30 * 86400,)):
        by_dept.setdefault(c["dept"], []).append(c)
    depts = []
    for code, lst in by_dept.items():
        e = efficiency(lst, now)
        depts.append({"code": code, "name": DEPARTMENTS[code]["name"], "short": DEPARTMENTS[code]["short"], "color": DEPARTMENTS[code]["color"], **e})
    depts.sort(key=lambda d: -d["open"])

    ward_open = Counter(c["ward"] for c in open_rows)
    hot_ward = max(WARDS, key=lambda w: ward_open[w])
    clusters = db.query("SELECT * FROM clusters WHERE status NOT IN ('Closed','Rejected') ORDER BY count DESC LIMIT 5")
    events = db.query("SELECT * FROM events ORDER BY at DESC, id DESC LIMIT 14")
    return {
        "now": now,
        "kpis": {"open": len(primaries), "open_reports": len(open_rows), "at_risk": states["at_risk"], "breached": states["breached"],
                 "reported_today": len(today), "resolved_today": resolved_today,
                 "avg_resolution_h": round(sum(res_h) / len(res_h), 1) if res_h else None,
                 "sla_met_pct": round(100 * sum(1 for c in met if c["resolved_at"] <= c["due_at"]) / len(met), 1) if met else None,
                 "escalated_open": sum(1 for c in primaries if (c["escalation_level"] or 0) >= 1),
                 "critical_open": sum(1 for c in primaries if c["priority"] == "CRITICAL"),
                 "duplicates_merged_7d": sum(1 for c in week if not c["is_primary"])},
        "queue": queue,
        "categories": [{"category": k, "count": v, "color": CATEGORY_COLORS.get(k, "blue")} for k, v in cat.most_common(6)],
        "departments": depts[:6],
        "hot_ward": {"ward": hot_ward, "name": WARDS[hot_ward]["name"], "open": ward_open[hot_ward]},
        "clusters": clusters,
        "events": events,
    }


@app.get("/api/complaints")
def complaints(status: str = "", ward: int = 0, category: str = "", priority: str = "", q: str = "", scope: str = "all", limit: int = 300):
    sql, params = "SELECT * FROM complaints WHERE 1=1", []
    if status == "Open":
        sql += f" AND status IN ({','.join('?' * len(OPEN))})"
        params += OPEN
    elif status:
        sql += " AND status=?"
        params.append(status)
    if ward:
        sql += " AND ward=?"
        params.append(ward)
    if category:
        sql += " AND category=?"
        params.append(category)
    if priority:
        sql += " AND priority=?"
        params.append(priority)
    if scope == "incidents":
        sql += " AND is_primary=1"
    if q:
        sql += " AND (id LIKE ? OR text LIKE ? OR title LIKE ? OR department LIKE ? OR landmark LIKE ? OR cluster_id LIKE ?)"
        params += [f"%{q}%"] * 6
    sql += " ORDER BY created_at DESC LIMIT ?"
    params.append(limit)
    now = db.now()
    return [view(c, now) for c in db.query(sql, params)]


@app.get("/api/complaints/{cid}")
def complaint(cid: str):
    c = db.get("complaints", cid)
    if not c:
        raise HTTPException(404, "Complaint not found")
    out = view(c, full=True)
    out["sla_start"] = c["created_at"]
    if c["cluster_id"]:
        out["cluster"] = db.get("clusters", c["cluster_id"])
        if not c["is_primary"] and out["cluster"]:
            # A merged report shares the incident's SLA clock and escalation ladder
            lead = db.get("complaints", out["cluster"]["primary_id"])
            out.update(sla_start=lead["created_at"], escalations=lead["escalations"], escalation_level=lead["escalation_level"],
                       lead_id=lead["id"])
        out["cluster_members"] = [{"id": m["id"], "created_at": m["created_at"], "citizen_name": m["citizen_name"], "text": m["text"], "is_primary": m["is_primary"]}
                                  for m in db.query("SELECT id, created_at, citizen_name, text, is_primary FROM complaints WHERE cluster_id=? ORDER BY created_at", (c["cluster_id"],))]
    out["citizen"] = db.get("citizens", c["citizen_id"])
    out["events"] = db.query("SELECT * FROM events WHERE complaint_id=? ORDER BY at", (cid,))
    return out


@app.post("/api/complaints")
async def create_complaint(text: str = Form(""), location: str = Form(""), name: str = Form(""), channel: str = Form("web"),
                           lat: float | None = Form(None), lng: float | None = Form(None), image: UploadFile | None = File(None)):
    img_b64 = img_type = None
    if image is not None and image.filename:
        data = await image.read()
        if len(data) > 5 * 1024 * 1024:
            raise HTTPException(413, "Image too large (max 5 MB)")
        img_type = image.content_type if image.content_type in ("image/jpeg", "image/png", "image/webp", "image/gif") else "image/jpeg"
        img_b64 = base64.standard_b64encode(data).decode()
    if len(text.strip()) < 6 and not img_b64:
        raise HTTPException(400, "Describe the issue (at least a few words) or attach a photo")
    c = await asyncio.to_thread(orch.intake, text.strip(), location.strip(), name.strip(), None, channel, img_b64, img_type, lat, lng)
    return view(c, full=True)


class StatusBody(BaseModel):
    status: str
    note: str = ""
    actor: str = "City Operator"


@app.post("/api/complaints/{cid}/status")
def set_status(cid: str, body: StatusBody):
    try:
        c = orch.update_status(cid, body.status, body.actor, body.note)
    except KeyError:
        raise HTTPException(404, "Complaint not found")
    except ValueError as e:
        raise HTTPException(409, str(e))
    return view(c, full=True)


class FeedbackBody(BaseModel):
    rating: int
    comment: str = ""


@app.post("/api/complaints/{cid}/feedback")
def feedback(cid: str, body: FeedbackBody):
    c = db.get("complaints", cid)
    if not c:
        raise HTTPException(404, "Complaint not found")
    if c["cluster_id"] and not c["is_primary"]:
        c = db.get("complaints", db.get("clusters", c["cluster_id"])["primary_id"])
    _, msg = orch.verification.feedback(c, max(1, min(5, body.rating)), body.comment)
    return {"message": msg, "complaint": view(db.get("complaints", cid), full=True)}


@app.get("/api/map")
def city_map(days: int = 14, category: str = ""):
    now = db.now()
    sql = "SELECT * FROM complaints WHERE (created_at>=? OR status IN ('Assigned','In Progress','Inspection','Reopened'))"
    params = [now - days * 86400]
    if category:
        sql += " AND category=?"
        params.append(category)
    rows = db.query(sql, params)
    month = db.query("SELECT * FROM complaints WHERE created_at>=?", (now - 30 * 86400,))
    wards = []
    for w, m in WARDS.items():
        lst = [c for c in month if c["ward"] == w]
        e = efficiency(lst, now) or {}
        top = Counter(c["category"] for c in lst if c["created_at"] >= now - days * 86400).most_common(1)
        wards.append({"ward": w, "name": m["name"], "code": m.get("code", ""), "row": m.get("row", (w - 1) // GRID_COLS), "col": m.get("col", (w - 1) % GRID_COLS), "pop": m["pop"],
                      "open": sum(1 for c in rows if c["ward"] == w and c["status"] in OPEN),
                      "recent": sum(1 for c in rows if c["ward"] == w), "efficiency": e.get("score"),
                      "overdue": e.get("overdue", 0), "top_issue": top[0][0] if top else None})
    pts = [{"id": c["id"], "lat": c["lat"], "lng": c["lng"], "category": c["category"], "color": CATEGORY_COLORS.get(c["category"], "blue"),
            "status": c["status"], "priority": c["priority"], "title": c["title"], "open": c["status"] in OPEN, "ward": c["ward"]} for c in rows]
    return {"bounds": {"lat_min": LAT_MIN, "lat_max": LAT_MAX, "lng_min": LNG_MIN, "lng_max": LNG_MAX, "cols": GRID_COLS, "rows": GRID_ROWS},
            "wards": wards, "points": pts, "categories": sorted(CATEGORY_COLORS)}


@app.get("/api/clusters")
def clusters():
    return db.query("SELECT * FROM clusters ORDER BY last_at DESC LIMIT 50")


@app.get("/api/escalations")
def escalations():
    now = db.now()
    rows = db.query(f"SELECT * FROM complaints WHERE is_primary=1 AND status IN ({','.join('?' * len(OPEN))})", OPEN)
    tickets = []
    for c in rows:
        st = sla_state(c, now)
        if (c["escalation_level"] or 0) >= 1 or st["state"] in ("at_risk", "breached"):
            v = view(c, now)
            v["escalations"] = c["escalations"]
            tickets.append(v)
    tickets.sort(key=lambda v: (-(v["escalation_level"] or 0), v["sla"]["remaining_h"]))
    feed = db.query("SELECT * FROM events WHERE agent='Escalation' ORDER BY at DESC LIMIT 30")
    ladder = Counter(c["escalation_level"] for c in db.query("SELECT escalation_level FROM complaints WHERE created_at>=?", (now - 30 * 86400,)))
    return {"tickets": tickets, "feed": feed, "ladder_30d": {str(k): v for k, v in ladder.items()}}


@app.get("/api/report")
def report(days: int = 30, narrative: bool = False):
    return TransparencyReportAgent().build(days, narrative)


@app.get("/api/report.csv")
def report_csv(days: int = 30):
    r = TransparencyReportAgent().build(days)
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow([f"{r['city']} transparency report - last {days} days"])
    for k in ("total_complaints", "unique_incidents", "duplicates_merged", "resolved", "resolution_rate", "avg_resolution_h", "sla_compliance",
              "escalations", "satisfaction", "city_efficiency"):
        w.writerow([k, r[k]])
    w.writerow([])
    w.writerow(["Department", "Efficiency", "SLA %", "Total", "Resolved", "Open", "Overdue", "Avg resolution h"])
    for d in r["departments"]:
        w.writerow([d["name"], d["score"], d["sla_compliance"], d["total"], d["resolved"], d["open"], d["overdue"], d["avg_resolution_h"]])
    w.writerow([])
    w.writerow(["Ward", "Name", "Efficiency", "Total", "Open", "Overdue", "Top issue"])
    for x in r["wards"]:
        w.writerow([x["ward"], x["name"], x["score"], x["total"], x["open"], x["overdue"], x["top_issue"]])
    return StreamingResponse(iter([buf.getvalue()]), media_type="text/csv",
                             headers={"Content-Disposition": f"attachment; filename=transparency-report-{days}d.csv"})


@app.get("/api/predict")
def predict(rain: float | None = None, hours: float = 3):
    rain = rain if rain is not None else db.get_setting("rain_mm_hr", 24)
    p = PredictiveAgent()
    return {"rain_mm_hr": rain, "hours": hours, "waterlogging": p.waterlogging(rain, hours), "hotspots": p.hotspots()}


@app.get("/api/citizens")
def citizens():
    top = db.query("SELECT * FROM citizens ORDER BY reputation DESC, reports DESC LIMIT 8")
    flagged = db.query("SELECT * FROM citizens WHERE rejected>0 ORDER BY reputation LIMIT 8")
    return {"top": top, "flagged": flagged, "total": db.scalar("SELECT COUNT(*) FROM citizens")}


@app.get("/api/events")
def events(limit: int = 40):
    return db.query("SELECT * FROM events ORDER BY at DESC, id DESC LIMIT ?", (limit,))


class AdvanceBody(BaseModel):
    hours: float


@app.post("/api/sim/advance")
def advance(body: AdvanceBody):
    """Time-warp the simulated clock so SLA breaches, escalations and verifications can be demoed live."""
    hours = max(0.0, min(72.0, body.hours))
    before = db.now()
    db.set_setting("clock_offset_hours", float(db.get_setting("clock_offset_hours", 0)) + hours)
    # Tick in 1 h steps so intermediate milestones fire with correct timestamps
    totals = Counter()
    t, target = before, db.now()
    while t < target:
        t = min(target, t + 3600)
        totals.update(orch.tick(t))
    db.log_event("Master Orchestrator", f"Clock advanced {hours:g} h: {totals['progressed']} field updates, {totals['escalations']} escalations, "
                 f"{totals['verified_closed']} verified closures, {totals['reopened']} reopened", level="info")
    return {"clock": db.now(), **totals}


@app.post("/api/sim/rain")
def set_rain(body: AdvanceBody):
    db.set_setting("rain_mm_hr", max(0.0, min(150.0, body.hours)))
    return {"rain_mm_hr": db.get_setting("rain_mm_hr")}


@app.post("/api/sim/reset")
def reset():
    from .seed import seed
    n = seed()
    return {"seeded": n}


# Serve the built frontend if present (npm run build -> ../dist)
DIST = os.path.join(os.path.dirname(__file__), "..", "..", "dist")
if os.path.isdir(DIST):
    app.mount("/assets", StaticFiles(directory=os.path.join(DIST, "assets")), name="assets")

    @app.get("/{path:path}")
    def spa(path: str):
        return FileResponse(os.path.join(DIST, "index.html"))
