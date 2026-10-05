"""Agent 4 - Priority & Severity: explainable 0-100 risk score from hazard, exposure, persistence and scale."""
import math

from ..config import ISSUE_TYPES, URGENCY_SIGNALS, WARDS
from .base import Agent, AgentResult

# Problems that get worse the longer they sit (health risk grows with time)
DECAYING = {"garbage_uncollected", "illegal_dumping", "drain_blockage", "sewage_overflow", "water_leakage", "mosquito_breeding",
            "waterlogging", "no_water_supply", "contaminated_water"}
MAX_POP = max(w["pop"] for w in WARDS.values())


def band(score):
    return "CRITICAL" if score >= 85 else "HIGH" if score >= 65 else "MEDIUM" if score >= 40 else "LOW"


class PrioritySeverityAgent(Agent):
    name = "Priority & Severity"

    def run(self, issue_type, signals, duration_days, ward, cluster_size, reputation) -> AgentResult:
        return self.timed(self._run, issue_type, signals, duration_days, ward, cluster_size, reputation)

    def _run(self, issue_type, signals, duration_days, ward, cluster_size, reputation):
        meta = ISSUE_TYPES[issue_type]
        factors = [{"factor": f"Base hazard: {meta['label']}", "points": meta["base"]}]
        # Strongest signal counts fully; each additional one adds half (signals overlap)
        for i, sig in enumerate(sorted(signals, key=lambda s: -URGENCY_SIGNALS[s][1])):
            pts = URGENCY_SIGNALS[sig][1] if i == 0 else round(URGENCY_SIGNALS[sig][1] / 2)
            factors.append({"factor": f"Signal: {sig.replace('_', ' ')}", "points": pts})
        if issue_type in DECAYING and duration_days:
            factors.append({"factor": f"Persisting {duration_days:g} days (risk grows over time)", "points": round(min(14, 2.2 * duration_days))})
        pop_pts = round(6 * WARDS[ward]["pop"] / MAX_POP)
        factors.append({"factor": f"Population exposure (Ward {ward}: {WARDS[ward]['pop']}k residents)", "points": pop_pts})
        if cluster_size > 1:
            factors.append({"factor": f"{cluster_size} citizens reporting the same incident", "points": round(min(14, 4 * math.log2(cluster_size)))})
        if reputation is not None and reputation < 30:
            factors.append({"factor": "Reporter credibility low (past false reports)", "points": -8})
        elif reputation is not None and reputation >= 80:
            factors.append({"factor": "Trusted reporter", "points": 2})

        score = max(5, min(100, sum(f["points"] for f in factors)))
        priority = band(score)
        trend = "rising - health risk increases the longer it stays" if issue_type in DECAYING else "stable"
        out = {"severity_score": score, "priority": priority, "factors": factors, "risk_trend": trend}
        top = sorted(factors[1:], key=lambda f: -f["points"])[:2]
        reason = f"Severity {score}/100 -> {priority}. Base {meta['base']}" + "".join(f", {f['factor'].lower()} ({f['points']:+d})" for f in top) + "."
        return AgentResult(self.name, out, reason)
