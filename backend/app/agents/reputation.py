"""Citizen reputation (supporting agent): rewards verified/helpful reports, penalises false ones.

Reputation feeds back into the Priority agent as a light credibility weight - it never blocks a report.
"""
from .. import db


class ReputationAgent:
    name = "Citizen Reputation"

    def ensure(self, cid, name):
        c = db.get("citizens", cid)
        if not c:
            c = {"id": cid, "name": name or "Anonymous citizen", "reputation": 60.0, "reports": 0, "verified": 0, "rejected": 0, "helpful": 0}
            db.insert("citizens", c)
        return c

    def record_report(self, cid):
        c = db.get("citizens", cid)
        if c:
            db.update("citizens", cid, {"reports": c["reports"] + 1})

    def adjust(self, cid, delta, kind):
        c = db.get("citizens", cid)
        if not c:
            return
        patch = {"reputation": max(0.0, min(100.0, c["reputation"] + delta))}
        if kind in ("verified", "rejected", "helpful"):
            patch[kind] = c[kind] + 1
        db.update("citizens", cid, patch)
