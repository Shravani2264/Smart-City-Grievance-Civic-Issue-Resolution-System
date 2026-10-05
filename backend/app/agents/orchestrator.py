"""Agent 11 - Master Orchestrator.

intake():  citizen input -> understand -> locate -> route -> dedupe -> prioritise -> SLA -> escalation plan
           -> workflow -> verification plan -> reporting, recording every agent's decision in an auditable trace.
tick():    the continuous control loop - field progress, resolution verification, SLA escalation.
"""
import hashlib
import time

from .. import db
from ..config import ISSUE_TYPES
from .base import AgentResult
from .duplicate import DuplicateDetectionAgent
from .escalation import EscalationAgent
from .location import LocationIntelligenceAgent
from .priority import PrioritySeverityAgent, band
from .reputation import ReputationAgent
from .routing import DepartmentRoutingAgent
from .sla import SLAAgent
from .understanding import ComplaintUnderstandingAgent
from .verification import ResolutionVerificationAgent
from .workflow import WorkflowTrackingAgent, sim_factor


class Orchestrator:
    name = "Master Orchestrator"

    def __init__(self):
        self.understanding = ComplaintUnderstandingAgent()
        self.location = LocationIntelligenceAgent()
        self.routing = DepartmentRoutingAgent()
        self.priority = PrioritySeverityAgent()
        self.duplicate = DuplicateDetectionAgent()
        self.sla = SLAAgent()
        self.escalation = EscalationAgent()
        self.workflow = WorkflowTrackingAgent()
        self.verification = ResolutionVerificationAgent()
        self.reputation = ReputationAgent()

    def intake(self, text, location_text="", citizen_name="", citizen_id=None, channel="web", image_b64=None, image_type=None,
               lat=None, lng=None, at=None, use_ai=True, simulate=False):
        t_start = time.perf_counter()
        now = at if at is not None else db.now()
        cid = db.next_complaint_id()
        citizen_id = citizen_id or "CIT-" + hashlib.md5((citizen_name or cid).lower().encode()).hexdigest()[:6].upper()
        citizen = self.reputation.ensure(citizen_id, citizen_name)
        trace: list[AgentResult] = []

        u = self.understanding.run(text, image_b64, image_type, use_ai=use_ai)
        trace.append(u)
        uo = u.output
        loc = self.location.run(location_text or uo["location"], text, lat, lng, seed=cid)
        trace.append(loc)
        lo = loc.output
        route = self.routing.run(uo["issue_type"], uo["urgency_signals"], lo)
        trace.append(route)
        ro = route.output
        dup = self.duplicate.run(text, uo["issue_type"], lo, now)
        do = dup.output
        prio = self.priority.run(uo["issue_type"], uo["urgency_signals"], uo["duration_days"], lo["ward"], do["cluster_size"], citizen["reputation"])
        trace.append(prio)
        trace.append(dup)
        po = prio.output
        sla = self.sla.run(uo["issue_type"], po["priority"], now)
        trace.append(sla)
        so = sla.output
        esc = self.escalation.plan(po["priority"], ro, so)
        trace.append(esc)
        wf = self.workflow.create(cid, now, ro)
        trace.append(wf)

        record = {
            "id": cid, "created_at": now, "text": text, "location_text": location_text, "citizen_id": citizen_id,
            "citizen_name": citizen["name"], "channel": channel, "has_image": 1 if image_b64 else 0,
            "image_analysis": {"findings": uo["image_findings"]} if image_b64 else None,
            "issue_type": uo["issue_type"], "issue_label": uo["issue_label"], "category": uo["category"], "title": uo["title"],
            "duration_days": uo["duration_days"], "lat": lo["lat"], "lng": lo["lng"], "ward": lo["ward"], "sector": lo["sector"],
            "landmark": lo["landmark"], "location_meta": lo, "dept": ro["dept"], "department": ro["department"], "unit": ro["unit"],
            "severity_score": po["severity_score"], "priority": po["priority"], "urgency_signals": uo["urgency_signals"],
            "severity_factors": {"factors": po["factors"], "trend": po["risk_trend"], "routing": ro, "duplicate": do},
            "sla_hours": so["sla_hours"], "due_at": so["due_at"], "status": wf.output["status"], "escalation_level": 0,
            "escalations": [], "cluster_id": None, "is_primary": 1, "assigned_at": now, "history": wf.output["history"],
            "reopen_count": 0, "sim_factor": sim_factor(cid, ro["dept"], lo["ward"]) if simulate else None,
            "ai_mode": "ai" if any(r.mode != "rules" for r in trace) else "rules",
        }

        # ---- incident clustering ----
        verif_note = "Closure requires citizen confirmation, no follow-up complaints, and a 48 h quiet period."
        primary = None
        if do["is_duplicate"]:
            match = db.get("complaints", do["match_id"])
            cluster_id = match["cluster_id"]
            primary = db.get("complaints", db.get("clusters", cluster_id)["primary_id"]) if cluster_id else match
            if not cluster_id:
                cluster_id = "INC-" + match["id"].split("-")[1]
                db.insert("clusters", {"id": cluster_id, "issue_type": match["issue_type"], "category": match["category"], "ward": match["ward"],
                                       "lat": match["lat"], "lng": match["lng"], "count": 1, "first_at": match["created_at"],
                                       "last_at": match["created_at"], "primary_id": match["id"], "title": match["title"], "status": match["status"]})
                db.update("complaints", match["id"], {"cluster_id": cluster_id, "is_primary": 1})
                primary = {**primary, "cluster_id": cluster_id, "is_primary": 1}
            cl = db.get("clusters", cluster_id)
            db.update("clusters", cluster_id, {"count": cl["count"] + 1, "last_at": now})
            record.update(cluster_id=cluster_id, is_primary=0, due_at=primary["due_at"], sla_hours=primary["sla_hours"],
                          unit=primary["unit"], sim_factor=None)
            record["history"].append({"status": record["status"], "at": now + 3, "actor": "Duplicate Detection",
                                      "note": f"Merged into incident {cluster_id} (lead ticket {primary['id']})"})
            if cl["count"] + 1 == 3:
                self.reputation.adjust(primary["citizen_id"], +2, "helpful")
            # Cluster growth raises the incident's severity
            if po["severity_score"] > (primary["severity_score"] or 0):
                db.update("complaints", primary["id"], {"severity_score": po["severity_score"], "priority": band(po["severity_score"])})
            if do["follow_up_on_resolved"] and primary["status"] in ("Resolved", "Closed"):
                verif_note = f"Follow-up on {primary['id']} which was marked {primary['status'].lower()} - reopening the incident for re-work."
            else:
                record["status"] = primary["status"]
        trace.append(AgentResult(self.verification.name, {"plan": "citizen feedback + follow-up scan + 48 h confirmation"}, verif_note))

        db.insert("complaints", record)
        self.reputation.record_report(citizen_id)
        if primary is not None and do["follow_up_on_resolved"] and primary["status"] in ("Resolved", "Closed"):
            self.verification.follow_up(db.get("complaints", primary["id"]), cid, now)
            db.update("complaints", cid, {"status": db.get("complaints", primary["id"])["status"]})

        open_in_ward = db.scalar("SELECT COUNT(*) FROM complaints WHERE ward=? AND category=? AND status NOT IN ('Resolved','Closed','Rejected')",
                                 (lo["ward"], uo["category"])) or 0
        trace.append(AgentResult("Transparency Reporting", {"ward_open_same_category": open_in_ward},
                                 f"Dashboards updated: Ward {lo['ward']} now has {open_in_ward} open {uo['category'].lower()} tickets; "
                                 f"counted toward {ro['department']} performance."))
        total_ms = (time.perf_counter() - t_start) * 1000
        summary = (f"{cid}: {uo['issue_label']} in Ward {lo['ward']} -> {ro['department']} ({ro['unit']}), {record['priority'] if primary is None else po['priority']} "
                   f"{po['severity_score']}/100, SLA {so['sla_hours']:g} h" + (f", merged into {record['cluster_id']}" if record["cluster_id"] else ""))
        trace.append(AgentResult(self.name, {"ticket": cid, "agents_run": len(trace) + 1, "total_ms": round(total_ms, 1)}, summary, ms=total_ms))
        steps = [r.as_trace(i + 1) for i, r in enumerate(trace)]
        db.update("complaints", cid, {"trace": steps})
        if not simulate:
            db.log_event(self.name, summary, cid, "critical" if po["priority"] == "CRITICAL" else "info", at=now)
            if po["priority"] == "CRITICAL":
                db.log_event("Escalation", f"{cid}: CRITICAL hazard - {ro['supervisor']} and emergency cell alerted immediately", cid, "critical", at=now)
        return db.get("complaints", cid)

    def tick(self, now=None):
        now = now if now is not None else db.now()
        moved = self.workflow.simulate_field_ops(now)
        closed, reopened = self.verification.sweep(now)
        fired = self.escalation.sweep(now)
        return {"progressed": moved, "verified_closed": closed, "reopened": reopened, "escalations": len(fired)}

    def update_status(self, cid, status, actor="Operator", note=""):
        c = db.get("complaints", cid)
        if not c:
            raise KeyError(cid)
        if c["cluster_id"] and not c["is_primary"]:
            c = db.get("complaints", db.get("clusters", c["cluster_id"])["primary_id"])
        db.update("complaints", c["id"], {"sim_factor": None})  # a human now owns this ticket
        c = {**c, "sim_factor": None}
        now = db.now()
        if status == "Rejected":
            self.reputation.adjust(c["citizen_id"], -15, "rejected")
        c = self.workflow.transition(c, status, actor, note, now)
        if status == "Resolved":
            self.verification.open_window(c, now)
        return db.get("complaints", cid)
