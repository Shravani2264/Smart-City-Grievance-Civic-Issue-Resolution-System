"""Agent 9 - Resolution Verification: a ticket is only Closed once the fix is confirmed.

Three independent checks after a crew marks a ticket Resolved:
  1. citizen feedback  - rating <= 2 reopens the ticket
  2. follow-up reports  - a new report clustered onto the incident during the window reopens it
  3. time-based confirmation - no negative signal for 48 h => auto-close
"""
import hashlib

from .. import db
from .base import Agent
from .reputation import ReputationAgent

WINDOW_H = 48


class ResolutionVerificationAgent(Agent):
    name = "Resolution Verification"

    def open_window(self, c, at):
        v = {"status": "pending", "opened_at": at, "window_until": at + WINDOW_H * 3600,
             "checks": {"citizen_feedback": "awaiting", "follow_up_reports": "none so far", "time_window": f"{WINDOW_H} h quiet period running"}}
        db.update("complaints", c["id"], {"verification": v})
        db.log_event(self.name, f"{c['id']}: resolution claimed - verification window open ({WINDOW_H} h, citizen asked to confirm)", c["id"], at=at)

    def _close(self, c, why, at):
        from .workflow import WorkflowTrackingAgent
        v = dict(c["verification"] or {})
        v["status"] = "verified"
        v["verified_by"] = why
        db.update("complaints", c["id"], {"verification": v})
        c = {**c, "verification": v}
        WorkflowTrackingAgent().transition(c, "Closed", self.name, f"Verified: {why}", at)
        for r in db.query("SELECT citizen_id FROM complaints WHERE id=? OR (cluster_id IS NOT NULL AND cluster_id=?)", (c["id"], c["cluster_id"])):
            ReputationAgent().adjust(r["citizen_id"], +3, "verified")

    def _reopen(self, c, why, at):
        from .workflow import WorkflowTrackingAgent
        v = dict(c["verification"] or {})
        v["status"] = "failed"
        v["failed_reason"] = why
        db.update("complaints", c["id"], {"verification": v})
        c = {**c, "verification": v}
        WorkflowTrackingAgent().transition(c, "Reopened", self.name, why, at)
        db.log_event(self.name, f"{c['id']}: verification FAILED - {why}. Ticket reopened and crew re-dispatched", c["id"], "critical", at=at)

    def feedback(self, c, rating: int, comment: str = ""):
        now = db.now()
        v = dict(c["verification"] or {})
        v.setdefault("checks", {})["citizen_feedback"] = f"{rating}/5" + (f" - {comment}" if comment else "")
        db.update("complaints", c["id"], {"feedback_rating": rating, "verification": v})
        c = {**c, "feedback_rating": rating, "verification": v}
        if c["status"] not in ("Resolved", "Closed"):
            return c, "Feedback recorded"
        if rating <= 2:
            if c["status"] == "Closed":
                from .workflow import WorkflowTrackingAgent
                WorkflowTrackingAgent().transition(c, "Reopened", "Citizen", f"Citizen rated {rating}/5: {comment or 'not fixed'}", now)
                return db.get("complaints", c["id"]), "Ticket reopened from citizen feedback"
            self._reopen(c, f"citizen rated the fix {rating}/5" + (f" ('{comment}')" if comment else ""), now)
            return db.get("complaints", c["id"]), "Verification failed - ticket reopened"
        if c["status"] == "Resolved":
            self._close(c, f"citizen confirmed ({rating}/5)", now)
        return db.get("complaints", c["id"]), "Resolution verified by citizen"

    def follow_up(self, primary, new_id, at):
        """A new report landed on an incident that was marked resolved."""
        if primary["status"] == "Resolved":
            self._reopen(primary, f"follow-up complaint {new_id} filed during the verification window", at)
        elif primary["status"] == "Closed":
            from .workflow import WorkflowTrackingAgent
            WorkflowTrackingAgent().transition(primary, "Reopened", self.name, f"Recurrence reported in {new_id}", at)

    def sweep(self, now):
        closed = reopened = 0
        for c in db.query("SELECT * FROM complaints WHERE status='Resolved' AND is_primary=1"):
            v = c["verification"] or {}
            opened = v.get("opened_at") or c["resolved_at"] or now
            # Simulated citizen response for simulator-driven tickets (deterministic per ticket)
            if c["sim_factor"] is not None and c["feedback_rating"] is None:
                h = int(hashlib.sha1((c["id"] + str(c["reopen_count"])).encode()).hexdigest()[:8], 16) / 0xFFFFFFFF
                reply_at = opened + (6 + 30 * h) * 3600
                if h < 0.55 and reply_at <= now:
                    rating = 1 if h < 0.05 and not c["reopen_count"] else 2 if h < 0.08 and not c["reopen_count"] else 3 + int(h * 10) % 3
                    db.update("complaints", c["id"], {"feedback_rating": rating})
                    v.setdefault("checks", {})["citizen_feedback"] = f"{rating}/5"
                    c = {**c, "feedback_rating": rating, "verification": v}
                    if rating <= 2:
                        self._reopen(c, f"citizen rated the fix {rating}/5 - issue persists", reply_at)
                        reopened += 1
                    else:
                        self._close(c, f"citizen confirmed ({rating}/5)", reply_at)
                        closed += 1
                    continue
            if now >= opened + WINDOW_H * 3600:
                v.setdefault("checks", {})["time_window"] = f"{WINDOW_H} h passed with no follow-up complaints"
                c = {**c, "verification": v}
                self._close(c, f"time-based confirmation ({WINDOW_H} h, no recurrence)", opened + WINDOW_H * 3600)
                closed += 1
        return closed, reopened
