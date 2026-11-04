"""Agent 3 - Department Routing: picks the accountable department, field crew and any departments to notify."""
from .. import db, policy_rag
from ..config import DEPARTMENTS, EMERGENCY_TEAM, ISSUE_TYPES
from ..config import SECONDARY_NOTIFY as SECONDARY
from .base import Agent, AgentResult

CREWS_PER_ZONE = 3


class DepartmentRoutingAgent(Agent):
    name = "Department Routing"

    def run(self, issue_type: str, signals: dict, location: dict) -> AgentResult:
        return self.timed(self._run, issue_type, signals, location)

    def _run(self, issue_type, signals, location):
        code = ISSUE_TYPES[issue_type]["dept"]
        dept = DEPARTMENTS[code]
        zone = location["zone"]
        division = zone.replace(" Zone", " Division")

        # Load-balance across the zone's crews by current open workload
        loads = []
        for i in range(1, CREWS_PER_ZONE + 1):
            crew = f"{dept['short']} Crew {zone[0]}{i}"
            n = db.scalar("SELECT COUNT(*) FROM complaints WHERE unit=? AND status NOT IN ('Resolved','Closed','Rejected')", (crew,)) or 0
            loads.append((n, crew))
        loads.sort()
        crew_load, crew = loads[0]

        notify, clauses = [], ["POL-RTE-001"]
        for (it, sig), extra in SECONDARY.items():
            if it == issue_type and (sig is None or sig in signals) and extra:
                notify += [DEPARTMENTS[c]["name"] for c in extra]
                clauses.append("POL-RTE-003")
        if issue_type in ("exposed_wire", "open_manhole") or ("safety_risk" in signals and ISSUE_TYPES[issue_type]["base"] >= 75):
            notify.append(EMERGENCY_TEAM)
            clauses.append("POL-RTE-002")
        if location.get("geo_confidence", 1) < 0.6:
            clauses.append("POL-RTE-004")
        refs, cite = policy_rag.cite(*dict.fromkeys(clauses))
        notify = list(dict.fromkeys(notify))

        out = {"dept": code, "department": dept["name"], "division": f"{dept['short']} - {division}", "unit": crew,
               "crew_open_load": crew_load, "jurisdiction": f"{location['municipality']} / Ward {location['ward']} / {division}",
               "notify": notify, "supervisor": dept["supervisor"], "district_officer": dept["officer"], "policy": refs}
        reason = (f"'{ISSUE_TYPES[issue_type]['label']}' is owned by {dept['name']}; Ward {location['ward']} falls under its {division}. "
                  f"Assigned to {crew} (lowest open load: {crew_load} of {', '.join(str(n) for n, _ in loads)}).")
        if notify:
            reason += f" Also notifying: {', '.join(notify)}."
        reason += cite
        return AgentResult(self.name, out, reason)
