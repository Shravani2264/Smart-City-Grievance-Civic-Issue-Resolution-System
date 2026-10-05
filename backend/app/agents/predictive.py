"""Predictive Civic Intelligence (supporting agent).

* Waterlogging forecast: rainfall forecast vs each ward's drainage capacity, elevation, current open
  drain/sewer blockages and recent waterlogging history.
* Emerging hotspots: ward x category pairs whose last-72h report rate is well above their baseline.
"""
from collections import Counter

from .. import db
from ..config import WARDS

DAY = 86400


class PredictiveAgent:
    name = "Predictive Intelligence"

    def waterlogging(self, rain_mm_hr: float, hours: float = 3):
        now = db.now()
        blocked = Counter(r["ward"] for r in db.query(
            "SELECT ward FROM complaints WHERE issue_type IN ('drain_blockage','sewage_overflow') AND status IN ('Reported','Assigned','In Progress','Inspection','Reopened')"))
        history = Counter(r["ward"] for r in db.query(
            "SELECT ward FROM complaints WHERE issue_type='waterlogging' AND created_at>=?", (now - 60 * DAY,)))
        out = []
        for w, m in WARDS.items():
            load = rain_mm_hr / m["drain"]                       # >1 means drains are overwhelmed
            low = max(0.0, (30 - m["elev"]) / 30)                # low-lying wards collect runoff
            dur = min(1.4, 0.6 + hours / 7.5)
            score = 100 * min(1.0, (0.55 * min(load, 1.8) / 1.8 * dur + 0.25 * low) * (1 + 0.12 * blocked[w] + 0.04 * history[w]))
            score = round(score)
            level = "SEVERE" if score >= 75 else "HIGH" if score >= 55 else "MODERATE" if score >= 35 else "LOW"
            drivers = []
            if load >= 1:
                drivers.append(f"rain {rain_mm_hr:g} mm/h exceeds drain capacity {m['drain']} mm/h")
            if low > 0.4:
                drivers.append(f"low-lying ({m['elev']} m)")
            if blocked[w]:
                drivers.append(f"{blocked[w]} open drain/sewer blockages")
            if history[w]:
                drivers.append(f"{history[w]} waterlogging reports in 60 days")
            action = {"SEVERE": "Pre-deploy pumps + desilting crew; issue citizen advisory; divert traffic",
                      "HIGH": "Clear open blockages within 6 h; stage a pump",
                      "MODERATE": "Inspect known choke points before rainfall",
                      "LOW": "Routine monitoring"}[level]
            out.append({"ward": w, "name": m["name"], "risk": score, "level": level, "drivers": drivers or ["adequate drainage"], "action": action})
        return sorted(out, key=lambda r: -r["risk"])

    def hotspots(self):
        now = db.now()
        recent = Counter((r["ward"], r["category"]) for r in db.query("SELECT ward, category FROM complaints WHERE created_at>=?", (now - 3 * DAY,)))
        base = Counter((r["ward"], r["category"]) for r in db.query(
            "SELECT ward, category FROM complaints WHERE created_at>=? AND created_at<?", (now - 17 * DAY, now - 3 * DAY)))
        out = []
        for (w, cat), n in recent.items():
            expected = base[(w, cat)] / 14 * 3
            ratio = n / max(expected, 0.75)
            if n >= 3 and ratio >= 1.6:
                out.append({"ward": w, "name": WARDS[w]["name"], "category": cat, "last_72h": n, "expected": round(expected, 1),
                            "surge": round(ratio, 1), "projection_7d": round(n / 3 * 7)})
        return sorted(out, key=lambda r: -r["surge"])[:8]
