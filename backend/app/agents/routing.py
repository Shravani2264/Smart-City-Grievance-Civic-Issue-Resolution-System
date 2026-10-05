"""Agent 3 - Department Routing: picks the accountable department, field crew and any departments to notify."""
from .. import db
from ..config import DEPARTMENTS, EMERGENCY_TEAM, ISSUE_TYPES
from .base import Agent, AgentResult

CREWS_PER_ZONE = 3

# (issue_type, signal or None) -> extra department codes to notify
SECONDARY = {
    ("open_manhole", None): ["TRF"], ("waterlogging", "traffic_impact"): ["TRF"], ("fallen_tree", "traffic_impact"): ["TRF"],
    ("contaminated_water", None): ["PHD"], ("sewage_overflow", None): ["PHD"], ("garbage_uncollected", "public_health_risk"): ["PHD"],
    ("drain_blockage", None): [], ("exposed_wire", None): ["ELE"], ("pothole", "traffic_impact"): ["TRF"],
    ("mosquito_breeding", None): ["SWD"],
}


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

        notify = []
        for (it, sig), extra in SECONDARY.items():
            if it == issue_type and (sig is None or sig in signals):
                notify += [DEPARTMENTS[c]["name"] for c in extra]
        if issue_type in ("exposed_wire", "open_manhole") or ("safety_risk" in signals and ISSUE_TYPES[issue_type]["base"] >= 75):
            notify.append(EMERGENCY_TEAM)
        notify = list(dict.fromkeys(notify))

        out = {"dept": code, "department": dept["name"], "division": f"{dept['short']} - {division}", "unit": crew,
               "crew_open_load": crew_load, "jurisdiction": f"{location['municipality']} / Ward {location['ward']} / {division}",
               "notify": notify, "supervisor": dept["supervisor"], "district_officer": dept["officer"]}
        reason = (f"'{ISSUE_TYPES[issue_type]['label']}' is owned by {dept['name']}; Ward {location['ward']} falls under its {division}. "
                  f"Assigned to {crew} (lowest open load: {crew_load} of {', '.join(str(n) for n, _ in loads)}).")
        if notify:
            reason += f" Also notifying: {', '.join(notify)}."
        return AgentResult(self.name, out, reason)
