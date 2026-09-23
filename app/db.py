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

CREATE TABLE IF NOT EXISTS task_queue (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    description TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending',
    result TEXT NOT NULL DEFAULT '',
    task_id INTEGER REFERENCES task_log(id),
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    completed_at TEXT
);
"""

# recall() used to score every single memory in Python on every call - fine
# at dozens of rows, a real cost once Wikipedia scans and the research queue
# have built up hundreds or thousands. This "external content" FTS5 index
# lets SQLite do the candidate lookup (which rows share any query word at
# all) so Python only has to tokenize and score the rows that could
# possibly match, not the whole table. Triggers keep it in sync with
# `memories` automatically - they fire on the underlying table regardless
# of which Python function (or future one) writes to it, so there's no
# separate cache-invalidation logic to keep correct by hand.
FTS_SCHEMA = """
CREATE VIRTUAL TABLE IF NOT EXISTS memories_fts USING fts5(
    content, tags, topic, category, content=memories, content_rowid=id
);

CREATE TRIGGER IF NOT EXISTS memories_fts_ai AFTER INSERT ON memories BEGIN
    INSERT INTO memories_fts(rowid, content, tags, topic, category)
    VALUES (new.id, new.content, new.tags, new.topic, new.category);
END;

CREATE TRIGGER IF NOT EXISTS memories_fts_ad AFTER DELETE ON memories BEGIN
    INSERT INTO memories_fts(memories_fts, rowid, content, tags, topic, category)
    VALUES ('delete', old.id, old.content, old.tags, old.topic, old.category);
END;

CREATE TRIGGER IF NOT EXISTS memories_fts_au AFTER UPDATE ON memories BEGIN
    INSERT INTO memories_fts(memories_fts, rowid, content, tags, topic, category)
    VALUES ('delete', old.id, old.content, old.tags, old.topic, old.category);
    INSERT INTO memories_fts(rowid, content, tags, topic, category)
    VALUES (new.id, new.content, new.tags, new.topic, new.category);
END;
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

        # Only after topic/category are guaranteed to exist - the FTS5 table
        # mirrors them by name. Check whether it's newly created *before*
        # running the schema (CREATE ... IF NOT EXISTS makes that the only
        # way to tell) - triggers only cover writes from here on, so a
        # brand-new index needs a one-time backfill for any rows that
        # already existed (an old DB migrating to this feature, or one
        # copied in from elsewhere). `count(*)` can't tell us this: for an
        # external-content FTS5 table it just reflects the content table's
        # row count regardless of whether those rows were ever tokenized
        # into the index, so a genuinely unindexed table looks identical to
        # a fully-indexed one by that measure.
        fts_already_existed = (
            conn.execute(
                "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'memories_fts'"
            ).fetchone()
            is not None
        )
        conn.executescript(FTS_SCHEMA)
        if not fts_already_existed:
            conn.execute("INSERT INTO memories_fts(memories_fts) VALUES ('rebuild')")
