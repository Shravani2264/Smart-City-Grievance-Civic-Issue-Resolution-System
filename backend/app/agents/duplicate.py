"""Agent 5 - Duplicate Detection: clusters repeated reports of the same problem into one civic incident."""
import re

from .. import db
from ..config import ISSUE_TYPES
from .base import Agent, AgentResult
from .location import haversine_m

RADIUS_M = 400
WINDOW_H = 7 * 24
THRESHOLD = 0.62
STOP = set("the a an is are was were in on at near of to and for my our this that it has have been not no from there street road area".split())


def tokens(text):
    return {w for w in re.findall(r"[a-z]+", (text or "").lower()) if w not in STOP and len(w) > 2}


def jaccard(a, b):
    return len(a & b) / len(a | b) if a and b else 0.0


class DuplicateDetectionAgent(Agent):
    name = "Duplicate Detection"

    def run(self, text, issue_type, location, now) -> AgentResult:
        return self.timed(self._run, text, issue_type, location, now)

    def _run(self, text, issue_type, location, now):
        category = ISSUE_TYPES[issue_type]["category"]
        lat, lng = location["lat"], location["lng"]
        # Open or recently resolved reports - a new report against a resolved incident is a follow-up signal
        cands = db.query(
            "SELECT id, text, issue_type, category, lat, lng, sector, landmark, created_at, status, cluster_id, resolved_at FROM complaints "
            "WHERE category=? AND created_at>=? AND status NOT IN ('Rejected') AND (status!='Closed' OR closed_at>=?)",
            (category, now - WINDOW_H * 3600, now - 72 * 3600))
        mine = tokens(text)
        best, best_score, best_detail = None, 0.0, None
        for c in cands:
            d = haversine_m(lat, lng, c["lat"], c["lng"])
            if d > RADIUS_M:
                continue
            geo = 1 - d / RADIUS_M
            # Citizens naming the same sector / landmark is strong co-location evidence even if geocodes drift
            if (location.get("sector") and c["sector"] == location["sector"]) or (location.get("landmark") and c["landmark"] == location["landmark"]):
                geo = max(geo, 0.85)
            typ = 1.0 if c["issue_type"] == issue_type else 0.45
            txt = jaccard(mine, tokens(c["text"]))
            recency = 1 - (now - c["created_at"]) / (WINDOW_H * 3600)
            score = 0.38 * geo + 0.34 * typ + 0.18 * txt + 0.10 * recency
            if score > best_score:
                best, best_score, best_detail = c, score, {"distance_m": round(d), "text_similarity": round(txt, 2), "same_type": c["issue_type"] == issue_type}

        similar_3d = db.scalar(
            "SELECT COUNT(*) FROM complaints WHERE category=? AND ward=? AND created_at>=?", (category, location["ward"], now - 72 * 3600)) or 0

        if best and best_score >= THRESHOLD:
            cluster_id = best["cluster_id"]
            cluster = db.get("clusters", cluster_id) if cluster_id else None
            size = (cluster["count"] if cluster else 1) + 1
            follow_up = best["status"] in ("Resolved", "Closed")
            out = {"is_duplicate": True, "match_id": best["id"], "cluster_id": cluster_id, "cluster_size": size,
                   "match_score": round(best_score, 2), **best_detail, "similar_last_3_days": similar_3d,
                   "follow_up_on_resolved": follow_up}
            reason = (f"Matches {best['id']} ({best_detail['distance_m']} m away, text similarity {best_detail['text_similarity']}, "
                      f"score {best_score:.2f} >= {THRESHOLD}). Merged into incident {cluster_id or '(new)'} - now {size} reports.")
            if follow_up:
                reason += " The matched incident was marked resolved: treating this as a follow-up complaint for verification."
        else:
            out = {"is_duplicate": False, "cluster_size": 1, "match_score": round(best_score, 2), "similar_last_3_days": similar_3d,
                   "follow_up_on_resolved": False}
            reason = (f"No existing incident within {RADIUS_M} m scored above {THRESHOLD} (best {best_score:.2f}). Opened a new incident. "
                      f"{similar_3d} {category.lower()} reports in Ward {location['ward']} in the last 3 days.")
        return AgentResult(self.name, out, reason)
