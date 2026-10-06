"""SQLite persistence plus a simulation clock.

All timestamps are epoch seconds on the *simulated* clock: real time plus an offset that the
operations console can advance ("time warp") so SLA breaches and escalations can be demoed live.

Durability: WAL journalling means committed writes survive a crash. Multi-step writes that must be
all-or-nothing (e.g. merging a report into an incident) run inside `with db.transaction():` so a
crash mid-merge can never leave a half-updated cluster. On startup `recover()` re-syncs any state
that a crash could have left inconsistent, which makes the agent pipeline safe to resume.
"""
import contextlib
import json
import os
import sqlite3
import threading
import time

DB_PATH = os.environ.get("CIVIC_DB", os.path.join(os.path.dirname(__file__), "..", "civic.db"))

_lock = threading.RLock()
_conn = sqlite3.connect(DB_PATH, check_same_thread=False)
_conn.row_factory = sqlite3.Row
_conn.execute("PRAGMA journal_mode=WAL")
_conn.execute("PRAGMA synchronous=NORMAL")

# When inside a transaction() block, individual writes defer their commit so the whole block is atomic.
_txn_depth = 0


@contextlib.contextmanager
def transaction():
    """Group several writes into one atomic unit. Commits on success, rolls back on any exception."""
    global _txn_depth
    with _lock:
        _txn_depth += 1
        try:
            yield
            _txn_depth -= 1
            if _txn_depth == 0:
                _conn.commit()
        except Exception:
            _txn_depth -= 1
            _conn.rollback()
            raise


def _commit():
    if _txn_depth == 0:
        _conn.commit()

JSON_COLS = {"urgency_signals", "trace", "history", "verification", "severity_factors", "location_meta", "image_analysis", "escalations"}

SCHEMA = """
CREATE TABLE IF NOT EXISTS complaints (
  id TEXT PRIMARY KEY, created_at REAL, text TEXT, location_text TEXT, citizen_id TEXT, citizen_name TEXT,
  channel TEXT, has_image INTEGER DEFAULT 0, image_analysis TEXT,
  issue_type TEXT, issue_label TEXT, category TEXT, title TEXT, duration_days REAL,
  lat REAL, lng REAL, ward INTEGER, sector INTEGER, landmark TEXT, location_meta TEXT,
  dept TEXT, department TEXT, unit TEXT,
  severity_score INTEGER, priority TEXT, urgency_signals TEXT, severity_factors TEXT,
  sla_hours REAL, due_at REAL, status TEXT, escalation_level INTEGER DEFAULT 0, escalations TEXT,
  cluster_id TEXT, is_primary INTEGER DEFAULT 1,
  assigned_at REAL, resolved_at REAL, closed_at REAL, verification TEXT, feedback_rating INTEGER,
  reopen_count INTEGER DEFAULT 0, sim_factor REAL, trace TEXT, history TEXT, ai_mode TEXT
);
CREATE INDEX IF NOT EXISTS ix_c_status ON complaints(status);
CREATE INDEX IF NOT EXISTS ix_c_cluster ON complaints(cluster_id);
CREATE TABLE IF NOT EXISTS clusters (
  id TEXT PRIMARY KEY, issue_type TEXT, category TEXT, ward INTEGER, lat REAL, lng REAL,
  count INTEGER, first_at REAL, last_at REAL, primary_id TEXT, title TEXT, status TEXT
);
CREATE TABLE IF NOT EXISTS citizens (
  id TEXT PRIMARY KEY, name TEXT, reputation REAL, reports INTEGER, verified INTEGER, rejected INTEGER, helpful INTEGER
);
CREATE TABLE IF NOT EXISTS events (
  id INTEGER PRIMARY KEY AUTOINCREMENT, at REAL, agent TEXT, complaint_id TEXT, level TEXT, message TEXT
);
CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT);
"""


def init():
    with _lock:
        _conn.executescript(SCHEMA)
        _conn.commit()


def reset():
    with _lock:
        for t in ("complaints", "clusters", "citizens", "events", "settings"):
            _conn.execute(f"DROP TABLE IF EXISTS {t}")
        _conn.commit()
    init()


# ---------- settings & clock ----------
def get_setting(key, default=None):
    with _lock:
        row = _conn.execute("SELECT value FROM settings WHERE key=?", (key,)).fetchone()
    return json.loads(row["value"]) if row else default


def set_setting(key, value):
    with _lock:
        _conn.execute("INSERT OR REPLACE INTO settings(key, value) VALUES (?, ?)", (key, json.dumps(value)))
        _commit()


def now() -> float:
    return time.time() + float(get_setting("clock_offset_hours", 0)) * 3600


# ---------- generic helpers ----------
def _decode(row):
    if row is None:
        return None
    d = dict(row)
    for k in JSON_COLS & d.keys():
        if d[k] is not None:
            d[k] = json.loads(d[k])
    return d


def _encode(d):
    return {k: (json.dumps(v) if k in JSON_COLS and v is not None else v) for k, v in d.items()}


def insert(table, d):
    d = _encode(d)
    cols = ",".join(d)
    with _lock:
        _conn.execute(f"INSERT INTO {table} ({cols}) VALUES ({','.join('?' * len(d))})", tuple(d.values()))
        _commit()


def update(table, key, d):
    if not d:
        return
    d = _encode(d)
    with _lock:
        _conn.execute(f"UPDATE {table} SET {','.join(f'{k}=?' for k in d)} WHERE id=?", (*d.values(), key))
        _commit()


def get(table, key):
    with _lock:
        return _decode(_conn.execute(f"SELECT * FROM {table} WHERE id=?", (key,)).fetchone())


def query(sql, params=()):
    with _lock:
        return [_decode(r) for r in _conn.execute(sql, params).fetchall()]


def scalar(sql, params=()):
    with _lock:
        row = _conn.execute(sql, params).fetchone()
    return row[0] if row else None


def log_event(agent, message, complaint_id=None, level="info", at=None):
    with _lock:
        _conn.execute("INSERT INTO events(at, agent, complaint_id, level, message) VALUES (?,?,?,?,?)",
                      (at if at is not None else now(), agent, complaint_id, level, message))
        _commit()


def next_complaint_id():
    n = scalar("SELECT COUNT(*) FROM complaints") or 0
    return f"CMP-{24001 + n}"


def recover() -> dict:
    """Startup crash-recovery: re-sync anything a mid-pipeline crash could have left inconsistent.

    Idempotent and safe to run on every boot. Returns a summary of what it fixed.
      * cluster counts re-derived from their members (a crash during a merge could skew them)
      * cluster primary/status re-pointed if the recorded primary vanished
    This is what lets the durable agent pipeline resume cleanly after an unclean shutdown.
    """
    fixed_counts = 0
    with transaction():
        for cl in query("SELECT id, count, primary_id FROM clusters"):
            members = query("SELECT id, status, is_primary FROM complaints WHERE cluster_id=?", (cl["id"],))
            real = len(members)
            if real and real != cl["count"]:
                update("clusters", cl["id"], {"count": real})
                fixed_counts += 1
            if members and not any(m["is_primary"] for m in members):
                # lost primary -> promote the earliest member
                lead = query("SELECT id, status FROM complaints WHERE cluster_id=? ORDER BY created_at LIMIT 1", (cl["id"],))[0]
                update("complaints", lead["id"], {"is_primary": 1})
                update("clusters", cl["id"], {"primary_id": lead["id"], "status": lead["status"]})
    if fixed_counts:
        log_event("Master Orchestrator", f"Crash recovery: re-synced {fixed_counts} incident cluster counts", level="warning")
    return {"clusters_resynced": fixed_counts}
