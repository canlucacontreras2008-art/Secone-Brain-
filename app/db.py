import sqlite3
from contextlib import contextmanager

from . import config

SCHEMA = """
CREATE TABLE IF NOT EXISTS memories (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    kind TEXT NOT NULL,
    content TEXT NOT NULL,
    tags TEXT NOT NULL DEFAULT '',
    topic TEXT NOT NULL DEFAULT '',
    category TEXT NOT NULL DEFAULT '',
    source TEXT NOT NULL,
    task_id INTEGER REFERENCES task_log(id),
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS task_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    description TEXT NOT NULL,
    result TEXT NOT NULL,
    reflection TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS research_queue (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    topic TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending',
    result TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    completed_at TEXT
);
"""


@contextmanager
def get_conn():
    conn = sqlite3.connect(config.DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db() -> None:
    with get_conn() as conn:
        conn.executescript(SCHEMA)
        # Dev-time migrations for DBs created before these columns existed.
        columns = {row["name"] for row in conn.execute("PRAGMA table_info(memories)")}
        if "task_id" not in columns:
            conn.execute("ALTER TABLE memories ADD COLUMN task_id INTEGER REFERENCES task_log(id)")
        if "topic" not in columns:
            conn.execute("ALTER TABLE memories ADD COLUMN topic TEXT NOT NULL DEFAULT ''")
        if "category" not in columns:
            conn.execute("ALTER TABLE memories ADD COLUMN category TEXT NOT NULL DEFAULT ''")
