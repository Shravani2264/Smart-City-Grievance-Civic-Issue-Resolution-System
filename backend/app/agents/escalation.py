"""Agent 7 - Escalation: watches every open ticket against its SLA and climbs the escalation ladder on delay."""
from .. import db
from ..config import COMMISSIONER, DEPARTMENTS, EMERGENCY_TEAM, ESCALATION_LEVELS
from .base import Agent, AgentResult
from .sla import sla_state

OPEN = ("Reported", "Assigned", "In Progress", "Inspection", "Reopened")


def target_for(c, level):
    dept = DEPARTMENTS[c["dept"]]
    if level == 1:
        return f"{dept['supervisor']} ({dept['short']})"
    if level == 2:
        return f"{dept['officer']}"
    return EMERGENCY_TEAM if c["priority"] == "CRITICAL" else COMMISSIONER


class EscalationAgent(Agent):
    name = "Escalation"

    def plan(self, priority, routing, sla) -> AgentResult:
        def _plan():
            immediate = priority == "CRITICAL"
            out = {"immediate_alert": immediate,
                   "ladder": [{"level": p["level"], "role": p["label"], "after_h": p["after_h"]} for p in sla["escalation_plan"]]}
            first = sla["escalation_plan"][0]
            reason = (f"If unresolved after {first['after_h']:g} h -> {routing['supervisor']}; at SLA breach ({sla['sla_hours']:g} h) -> "
                      f"{routing['district_officer']}; at 150% -> {'emergency team' if immediate else 'Commissioner'}.")
            if immediate:
                reason = "CRITICAL hazard: supervisor and emergency cell alerted immediately. " + reason
            return AgentResult(self.name, out, reason)
        return self.timed(_plan)

    def sweep(self, now):
        """Escalate every open ticket whose elapsed SLA fraction crossed a new rung. Returns new escalation records."""
        fired = []
        rows = db.query(f"SELECT * FROM complaints WHERE status IN ({','.join('?' * len(OPEN))}) AND is_primary=1", OPEN)
        for c in rows:
            st = sla_state(c, now)
            frac = st["elapsed_frac"]
            esc = list(c["escalations"] or [])
            level = c["escalation_level"] or 0
            new_level = level
            for rung in ESCALATION_LEVELS:
                if frac >= rung["at"] and rung["level"] > new_level:
                    new_level = rung["level"]
                    target = target_for(c, rung["level"])
                    reason = ("SLA breached" if rung["at"] >= 1 else f"{int(rung['at'] * 100)}% of SLA elapsed") + f" with status '{c['status']}'"
                    at = c["created_at"] + c["sla_hours"] * rung["at"] * 3600
                    rec = {"level": rung["level"], "role": rung["label"], "target": target, "reason": reason, "at": min(at, now)}
                    esc.append(rec)
                    fired.append({**rec, "complaint_id": c["id"]})
                    db.log_event(self.name, f"{c['id']} escalated to L{rung['level']} {target}: {reason}", c["id"],
                                 "critical" if rung["level"] >= 2 else "warning", at=rec["at"])
            if not any(e.get("level") == 0 for e in esc) and st["state"] == "at_risk" and new_level < 2:
                rec = {"level": 0, "role": "Breach-risk alert", "target": c["unit"], "reason": f"SLA breach risk in {st['remaining_h']:.1f} h", "at": now}
                esc.append(rec)
                db.log_event(self.name, f"{c['id']}: SLA breach risk in {st['remaining_h']:.1f} h - crew {c['unit']} alerted", c["id"], "warning", at=now)
            if new_level != level or len(esc) != len(c["escalations"] or []):
                db.update("complaints", c["id"], {"escalation_level": new_level, "escalations": esc})
        return fired
