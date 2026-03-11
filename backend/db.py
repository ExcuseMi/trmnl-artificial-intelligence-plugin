import json
import sqlite3
from contextlib import contextmanager
from datetime import date, datetime
from pathlib import Path

DB_PATH = Path("/data/aa.db")


def init_db():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    with _conn() as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS snapshots (
                id      INTEGER PRIMARY KEY AUTOINCREMENT,
                date    TEXT NOT NULL,
                type    TEXT NOT NULL,
                data    TEXT NOT NULL,
                UNIQUE(date, type)
            );
            CREATE TABLE IF NOT EXISTS trmnl_ips (
                id          INTEGER PRIMARY KEY CHECK (id = 1),
                updated_at  TEXT NOT NULL,
                ips         TEXT NOT NULL
            );
        """)


@contextmanager
def _conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


# ---------- snapshots ----------

def get_snapshot(snapshot_type: str, snapshot_date: date | None = None) -> dict | None:
    d = (snapshot_date or date.today()).isoformat()
    with _conn() as conn:
        row = conn.execute(
            "SELECT data FROM snapshots WHERE date = ? AND type = ?", (d, snapshot_type)
        ).fetchone()
    return json.loads(row["data"]) if row else None


def save_snapshot(snapshot_type: str, data: dict, snapshot_date: date | None = None):
    d = (snapshot_date or date.today()).isoformat()
    with _conn() as conn:
        conn.execute(
            """INSERT INTO snapshots (date, type, data)
               VALUES (?, ?, ?)
               ON CONFLICT(date, type) DO UPDATE SET data = excluded.data""",
            (d, snapshot_type, json.dumps(data)),
        )


# ---------- TRMNL IPs ----------

def get_trmnl_ips() -> set[str] | None:
    with _conn() as conn:
        row = conn.execute("SELECT updated_at, ips FROM trmnl_ips WHERE id = 1").fetchone()
    if not row:
        return None
    updated = datetime.fromisoformat(row["updated_at"])
    if (datetime.utcnow() - updated).total_seconds() > 86400:
        return None  # stale
    return set(json.loads(row["ips"]))


def save_trmnl_ips(ips: list[str]):
    with _conn() as conn:
        conn.execute(
            """INSERT INTO trmnl_ips (id, updated_at, ips)
               VALUES (1, ?, ?)
               ON CONFLICT(id) DO UPDATE SET updated_at = excluded.updated_at, ips = excluded.ips""",
            (datetime.utcnow().isoformat(), json.dumps(ips)),
        )
