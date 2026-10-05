"""Agent 10 - Transparency Reporting: public accountability metrics, ward efficiency scores, and a narrative report."""
import statistics
from collections import Counter, defaultdict

from .. import db, llm
from ..config import CATEGORY_COLORS, CITY, DEPARTMENTS, WARDS
from .sla import sla_state

DAY = 86400


def _res_hours(c):
    return (c["resolved_at"] - c["created_at"]) / 3600 if c["resolved_at"] else None


def efficiency(rows, now):
    """Government Efficiency Score (0-100):
    40% SLA compliance, 30% speed (actual vs SLA time), 20% backlog health, 10% citizen satisfaction."""
    if not rows:
        return None
    done = [c for c in rows if c["resolved_at"]]
    open_ = [c for c in rows if c["status"] in ("Reported", "Assigned", "In Progress", "Inspection", "Reopened")]
    compliance = sum(1 for c in done if c["resolved_at"] <= c["due_at"]) / len(done) if done else 0.5
    speed = statistics.mean(min(1.0, max(0.0, 1.5 - _res_hours(c) / c["sla_hours"])) for c in done) if done else 0.5
    overdue = sum(1 for c in open_ if sla_state(c, now)["state"] == "breached")
    backlog = 1 - min(1.0, (len(open_) / len(rows)) * 0.6 + (overdue / max(1, len(open_))) * 0.6)
    rated = [c["feedback_rating"] for c in rows if c["feedback_rating"]]
    sat = (statistics.mean(rated) - 1) / 4 if rated else 0.6
    score = round(100 * (0.4 * compliance + 0.3 * speed + 0.2 * backlog + 0.1 * sat))
    return {"score": score, "sla_compliance": round(compliance * 100, 1), "speed": round(speed * 100), "backlog_health": round(backlog * 100),
            "satisfaction": round(sat * 100), "open": len(open_), "overdue": overdue, "total": len(rows), "resolved": len(done)}


class TransparencyReportAgent:
    name = "Transparency Reporting"

    def build(self, days=30, narrative=False):
        now = db.now()
        start = now - days * DAY
        rows = db.query("SELECT * FROM complaints WHERE created_at>=?", (start,))
        prev = db.query("SELECT * FROM complaints WHERE created_at>=? AND created_at<?", (start - days * DAY, start))
        resolved = [c for c in rows if c["resolved_at"]]
        res_h = [_res_hours(c) for c in resolved]
        incidents = len({c["cluster_id"] or c["id"] for c in rows})
        within = sum(1 for c in resolved if c["resolved_at"] <= c["due_at"])
        rated = [c["feedback_rating"] for c in rows if c["feedback_rating"]]
        esc_count = sum(len([e for e in (c["escalations"] or []) if e["level"] >= 1]) for c in rows)
        prev_res = [_res_hours(c) for c in prev if c["resolved_at"]]

        cats = Counter(c["category"] for c in rows)
        top_issues = [{"category": k, "count": v, "color": CATEGORY_COLORS.get(k, "blue"),
                       "resolved": sum(1 for c in rows if c["category"] == k and c["resolved_at"])} for k, v in cats.most_common()]

        by_dept = defaultdict(list)
        for c in rows:
            by_dept[c["dept"]].append(c)
        depts = []
        for code, meta in DEPARTMENTS.items():
            lst = by_dept.get(code, [])
            if not lst:
                continue
            e = efficiency(lst, now)
            done = [c for c in lst if c["resolved_at"]]
            depts.append({"code": code, "name": meta["name"], "short": meta["short"], "color": meta["color"], **e,
                          "avg_resolution_h": round(statistics.mean(_res_hours(c) for c in done), 1) if done else None,
                          "escalations": sum(len([x for x in (c["escalations"] or []) if x["level"] >= 1]) for c in lst)})
        depts.sort(key=lambda d: -d["score"])

        wards = []
        for w, meta in WARDS.items():
            lst = [c for c in rows if c["ward"] == w]
            e = efficiency(lst, now) or {"score": None, "total": 0, "open": 0, "overdue": 0}
            top = Counter(c["category"] for c in lst).most_common(1)
            wards.append({"ward": w, "name": meta["name"], **e, "top_issue": top[0][0] if top else None})

        daily = []
        for i in range(days - 1, -1, -1):
            d0 = now - (i + 1) * DAY
            daily.append({"day": d0 + DAY, "reported": sum(1 for c in rows if d0 <= c["created_at"] < d0 + DAY),
                          "resolved": sum(1 for c in resolved if d0 <= c["resolved_at"] < d0 + DAY)})

        report = {
            "city": CITY, "period_days": days, "generated_at": now,
            "total_complaints": len(rows), "unique_incidents": incidents, "duplicates_merged": len(rows) - incidents,
            "resolved": len(resolved), "closed_verified": sum(1 for c in rows if c["status"] == "Closed"),
            "open": sum(1 for c in rows if c["status"] in ("Reported", "Assigned", "In Progress", "Inspection", "Reopened")),
            "reopened": sum(1 for c in rows if (c["reopen_count"] or 0) > 0),
            "resolution_rate": round(100 * len(resolved) / len(rows), 1) if rows else 0,
            "avg_resolution_h": round(statistics.mean(res_h), 1) if res_h else None,
            "median_resolution_h": round(statistics.median(res_h), 1) if res_h else None,
            "prev_avg_resolution_h": round(statistics.mean(prev_res), 1) if prev_res else None,
            "sla_compliance": round(100 * within / len(resolved), 1) if resolved else None,
            "escalations": esc_count, "satisfaction": round(statistics.mean(rated), 2) if rated else None,
            "city_efficiency": (efficiency(rows, now) or {}).get("score"),
            "top_issues": top_issues, "departments": depts, "wards": wards, "daily": daily,
        }
        if narrative:
            report["narrative"], report["narrative_mode"] = self.narrative(report)
        return report

    def narrative(self, r):
        summary = {k: r[k] for k in ("period_days", "total_complaints", "unique_incidents", "duplicates_merged", "resolved", "resolution_rate",
                                     "avg_resolution_h", "prev_avg_resolution_h", "sla_compliance", "escalations", "satisfaction", "city_efficiency", "reopened")}
        summary["top_issues"] = r["top_issues"][:5]
        summary["departments"] = [{k: d[k] for k in ("name", "score", "sla_compliance", "avg_resolution_h", "open", "overdue")} for d in r["departments"]]
        summary["wards"] = [{k: w[k] for k in ("ward", "name", "score", "open", "overdue", "top_issue")} for w in r["wards"]]
        txt = llm.text(
            "You write the monthly public transparency report for a city's grievance redressal system. Audience: residents and "
            "councillors. Plain language, factual, no hype; cite the numbers given and never invent any. Structure: a 2-sentence "
            "headline summary, then 'What went well', 'Where we fell short' (name the weakest departments/wards), and 'Commitments "
            "for next month' (3 concrete, measurable actions). Under 300 words. Markdown headings with ###.",
            f"Data for {r['city']}:\n{summary}")
        if txt:
            return txt, "ai"
        best, worst = r["departments"][0], r["departments"][-1]
        wards = sorted([w for w in r["wards"] if w["score"] is not None], key=lambda w: w["score"])
        prev = r["prev_avg_resolution_h"]
        delta = f" ({'down' if prev and r['avg_resolution_h'] < prev else 'up'} from {prev} h the previous period)" if prev else ""
        top = ", ".join(t["category"].lower() for t in r["top_issues"][:3])
        weak = ", ".join(f"Ward {w['ward']} {w['name']} ({w['score']})" for w in wards[:2])
        return (
            f"### Summary\n{r['city']} received **{r['total_complaints']:,} complaints** in the last {r['period_days']} days, which the "
            f"system consolidated into {r['unique_incidents']:,} distinct incidents ({r['duplicates_merged']} duplicates merged). "
            f"{r['resolved']:,} were resolved ({r['resolution_rate']}%), with an average resolution time of {r['avg_resolution_h']} h{delta}.\n\n"
            f"### What went well\n- {best['name']} led departments with an efficiency score of {best['score']}/100 and "
            f"{best['sla_compliance']}% of tickets inside SLA.\n- {r['sla_compliance']}% of all resolved complaints met their service deadline.\n"
            f"- Citizen satisfaction averaged {r['satisfaction']}/5 on verified fixes.\n\n"
            f"### Where we fell short\n- {worst['name']} scored {worst['score']}/100 with {worst['overdue']} tickets currently overdue.\n"
            f"- Lowest-performing wards: {weak}.\n"
            f"- {r['escalations']} escalations were triggered and {r['reopened']} fixes failed verification and were reopened.\n\n"
            f"### Commitments for next month\n- Cut {worst['short']} overdue backlog by half with additional crew allocation.\n"
            f"- Pre-emptive drives on the top issues ({top}) in the weakest wards.\n- Raise citywide SLA compliance above "
            f"{min(98, round((r['sla_compliance'] or 80) + 4))}%."
        ), "template"
