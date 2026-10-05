"""Agent 8 - Workflow Tracking: owns the ticket lifecycle state machine and keeps clustered reports in sync.

Reported -> Assigned -> In Progress -> Inspection -> Resolved -> Closed   (+ Reopened, Rejected)

It also drives the *field-operations simulator* that stands in for real crews in the demo: each ticket
gets a deterministic pace factor, and as the (simulated) clock advances the crew picks it up, inspects
and resolves it. Tickets a human has touched are taken off the simulator.
"""
import hashlib

from .. import db
from ..config import DEPT_PACE, WARD_PACE
from .base import Agent, AgentResult

ALLOWED = {
    "Reported": {"Assigned", "Rejected"},
    "Assigned": {"In Progress", "Inspection", "Resolved", "Rejected"},
    "In Progress": {"Inspection", "Resolved"},
    "Inspection": {"In Progress", "Resolved"},
    "Resolved": {"Closed", "Reopened"},
    "Reopened": {"Assigned", "In Progress", "Inspection", "Resolved"},
    "Closed": {"Reopened"},
    "Rejected": set(),
}
OPEN = ("Reported", "Assigned", "In Progress", "Inspection", "Reopened")
NOTES = {
    "In Progress": "Crew dispatched; work started on site",
    "Inspection": "Work completed; inspection scheduled",
    "Resolved": "Crew marked the issue resolved",
}


def sim_factor(cid, dept, ward):
    h = int(hashlib.sha1(cid.encode()).hexdigest()[:8], 16) / 0xFFFFFFFF
    # Skewed spread: most tickets finish inside SLA, a tail breaches
    spread = 0.3 + 1.05 * h ** 2.2
    return round(spread * DEPT_PACE.get(dept, 1) * WARD_PACE.get(ward, 1), 3)


class WorkflowTrackingAgent(Agent):
    name = "Workflow Tracking"

    def create(self, cid, created_at, routing) -> AgentResult:
        def _c():
            history = [
                {"status": "Reported", "at": created_at, "actor": "Citizen", "note": "Complaint registered"},
                {"status": "Assigned", "at": created_at + 2, "actor": "Orchestrator", "note": f"Auto-assigned to {routing['unit']} ({routing['department']})"},
            ]
            return AgentResult(self.name, {"status": "Assigned", "history": history, "stages": ["Reported", "Assigned", "In Progress", "Inspection", "Resolved", "Closed"]},
                               f"Ticket {cid} opened and moved Reported -> Assigned automatically; next stage: crew starts work.")
        return self.timed(_c)

    def transition(self, c, new_status, actor, note="", at=None, cascade=True):
        at = at if at is not None else db.now()
        old = c["status"]
        if new_status == old:
            return c
        if new_status not in ALLOWED.get(old, set()):
            raise ValueError(f"Illegal transition {old} -> {new_status}")
        history = list(c["history"] or []) + [{"status": new_status, "at": at, "actor": actor, "note": note or NOTES.get(new_status, "")}]
        patch = {"status": new_status, "history": history}
        if new_status == "Resolved":
            patch["resolved_at"] = at
        if new_status == "Closed":
            patch["closed_at"] = at
        if new_status == "Reopened":
            patch.update(resolved_at=None, closed_at=None, reopen_count=(c["reopen_count"] or 0) + 1)
        db.update("complaints", c["id"], patch)
        db.log_event(self.name, f"{c['id']}: {old} -> {new_status}" + (f" ({note})" if note else ""), c["id"],
                     "success" if new_status in ("Resolved", "Closed") else "warning" if new_status == "Reopened" else "info", at=at)
        c = {**c, **patch}
        if cascade and c.get("cluster_id") and c.get("is_primary"):
            for m in db.query("SELECT * FROM complaints WHERE cluster_id=? AND is_primary=0", (c["cluster_id"],)):
                if new_status in ALLOWED.get(m["status"], set()):
                    self.transition(m, new_status, actor, f"Synced with incident {c['cluster_id']}", at, cascade=False)
            db.update("clusters", c["cluster_id"], {"status": new_status})
        return c

    def simulate_field_ops(self, now):
        """Advance simulator-controlled tickets whose milestones have passed. Returns number of transitions."""
        moved = 0
        rows = db.query(f"SELECT * FROM complaints WHERE is_primary=1 AND sim_factor IS NOT NULL AND status IN ({','.join('?' * len(OPEN))})", OPEN)
        for c in rows:
            start = c["created_at"]
            span = c["sla_hours"] * 3600 * c["sim_factor"]
            if c["status"] == "Reopened" or (c["reopen_count"] or 0):
                reopened = [h["at"] for h in c["history"] if h["status"] == "Reopened"]
                if reopened:
                    start, span = reopened[-1], span * 0.5
            milestones = [("In Progress", 0.2), ("Inspection", 0.7), ("Resolved", 1.0)]
            for status, frac in milestones:
                t = start + span * frac
                if t > now:
                    break
                order = ["Assigned", "Reopened", "In Progress", "Inspection", "Resolved"]
                if order.index(c["status"]) >= order.index(status):
                    continue
                c = self.transition(c, status, c["unit"] or "Field crew", at=t)
                moved += 1
                if status == "Resolved":
                    from .verification import ResolutionVerificationAgent
                    ResolutionVerificationAgent().open_window(c, t)
        return moved
