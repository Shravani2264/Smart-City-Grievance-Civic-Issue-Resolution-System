"""Agent 6 - SLA & Deadline: assigns the resolution timeline and tracks breach risk."""
from ..config import ESCALATION_LEVELS, ISSUE_TYPES
from .base import Agent, AgentResult

PRIORITY_FACTOR = {"CRITICAL": 0.5, "HIGH": 0.75, "MEDIUM": 1.0, "LOW": 1.25}


def sla_state(c, now):
    """Live SLA view for a complaint dict."""
    if c["status"] in ("Resolved", "Closed", "Rejected"):
        end = c.get("resolved_at") or c.get("closed_at") or now
        met = end <= c["due_at"]
        return {"state": "met" if met else "breached_resolved", "remaining_h": None, "elapsed_frac": None}
    remaining = (c["due_at"] - now) / 3600
    elapsed = (now - c["created_at"]) / (c["sla_hours"] * 3600)
    state = "breached" if remaining < 0 else "at_risk" if remaining <= max(2, 0.25 * c["sla_hours"]) else "on_track"
    return {"state": state, "remaining_h": round(remaining, 2), "elapsed_frac": round(elapsed, 3)}


class SLAAgent(Agent):
    name = "SLA Management"

    def run(self, issue_type, priority, created_at) -> AgentResult:
        return self.timed(self._run, issue_type, priority, created_at)

    def _run(self, issue_type, priority, created_at):
        base = ISSUE_TYPES[issue_type]["sla"]
        hours = max(2, round(base * PRIORITY_FACTOR[priority], 1))
        due = created_at + hours * 3600
        plan = [{"level": e["level"], "label": e["label"], "after_h": round(hours * e["at"], 1), "at": created_at + hours * e["at"] * 3600}
                for e in ESCALATION_LEVELS]
        out = {"sla_hours": hours, "base_sla_hours": base, "due_at": due, "escalation_plan": plan}
        reason = (f"Service standard for {ISSUE_TYPES[issue_type]['label'].lower()} is {base} h; {priority} priority applies x{PRIORITY_FACTOR[priority]} "
                  f"-> {hours:g} h. Escalation checkpoints at " + ", ".join(f"{p['after_h']:g} h ({p['label']})" for p in plan) + ".")
        return AgentResult(self.name, out, reason)
