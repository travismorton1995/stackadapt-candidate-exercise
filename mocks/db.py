import json
import logging
import sqlite3
import uuid
from contextlib import contextmanager
from datetime import date, datetime
from pathlib import Path

logger = logging.getLogger("mocks.db")

DB_PATH = Path(__file__).parent / "audit.db"


@contextmanager
def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db():
    with get_conn() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS audit_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                run_id TEXT,
                trigger TEXT,
                customer_id TEXT,
                state_snapshot TEXT,
                llm_verdict TEXT,
                action_taken TEXT,
                timestamp TEXT NOT NULL
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS nudges (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                nudge_id TEXT NOT NULL,
                customer_id TEXT NOT NULL,
                nudge_date TEXT NOT NULL,
                message TEXT,
                created_at TEXT NOT NULL,
                UNIQUE(customer_id, nudge_date)
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS slack_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                channel TEXT,
                text TEXT,
                created_at TEXT NOT NULL
            )
            """
        )
    logger.info("database initialized at %s", DB_PATH)


def insert_audit(run_id, trigger, customer_id, state_snapshot, llm_verdict, action_taken):
    timestamp = datetime.utcnow().isoformat()
    with get_conn() as conn:
        conn.execute(
            """
            INSERT INTO audit_log (run_id, trigger, customer_id, state_snapshot, llm_verdict, action_taken, timestamp)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                run_id,
                trigger,
                customer_id,
                json.dumps(state_snapshot) if state_snapshot is not None else None,
                json.dumps(llm_verdict) if llm_verdict is not None else None,
                action_taken,
                timestamp,
            ),
        )
    logger.info(
        "audit recorded run_id=%s trigger=%s customer_id=%s action_taken=%s",
        run_id,
        trigger,
        customer_id,
        action_taken,
    )
    return timestamp


def list_audit():
    with get_conn() as conn:
        rows = conn.execute("SELECT * FROM audit_log ORDER BY id DESC").fetchall()
    result = []
    for row in rows:
        entry = dict(row)
        for field in ("state_snapshot", "llm_verdict"):
            if entry[field]:
                entry[field] = json.loads(entry[field])
        result.append(entry)
    return result


def get_or_create_nudge(customer_id, message):
    today = date.today().isoformat()
    with get_conn() as conn:
        existing = conn.execute(
            "SELECT nudge_id FROM nudges WHERE customer_id = ? AND nudge_date = ?",
            (customer_id, today),
        ).fetchone()
        if existing:
            logger.info("nudge already sent today for customer_id=%s", customer_id)
            return existing["nudge_id"], False

        nudge_id = str(uuid.uuid4())
        conn.execute(
            """
            INSERT INTO nudges (nudge_id, customer_id, nudge_date, message, created_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (nudge_id, customer_id, today, message, datetime.utcnow().isoformat()),
        )
    logger.info("new nudge created customer_id=%s nudge_id=%s", customer_id, nudge_id)
    return nudge_id, True


def log_slack_message(channel, text):
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO slack_log (channel, text, created_at) VALUES (?, ?, ?)",
            (channel, text, datetime.utcnow().isoformat()),
        )
    logger.info("slack message logged channel=%s", channel)


def list_slack_log():
    with get_conn() as conn:
        rows = conn.execute("SELECT * FROM slack_log ORDER BY id DESC").fetchall()
    return [dict(row) for row in rows]
