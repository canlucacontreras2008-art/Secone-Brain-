import threading
from typing import List, Optional

from . import db

# In-process stop signal for run_research_queue(). A plain module-level
# Event (thread-safe) is enough here - this is a single-server personal app,
# not a distributed job queue. Deliberately NOT wired into Brain._run_loop
# itself: that's shared by /chat and /task too, and a "stop learning" click
# must never abort an unrelated concurrent chat request.
_stop_event = threading.Event()


def request_stop() -> None:
    _stop_event.set()


def clear_stop() -> None:
    _stop_event.clear()


def stop_requested() -> bool:
    return _stop_event.is_set()


def delete(item_id: int) -> None:
    with db.get_conn() as conn:
        conn.execute("DELETE FROM research_queue WHERE id = ?", (item_id,))


def enqueue(topics: List[str]) -> List[dict]:
    with db.get_conn() as conn:
        items = []
        for topic in topics:
            cur = conn.execute("INSERT INTO research_queue (topic) VALUES (?)", (topic,))
            items.append({"id": cur.lastrowid, "topic": topic, "status": "pending"})
        return items


def list_queue(status: Optional[str] = None, limit: int = 200) -> List[dict]:
    with db.get_conn() as conn:
        if status:
            rows = conn.execute(
                "SELECT * FROM research_queue WHERE status = ? ORDER BY id ASC LIMIT ?",
                (status, limit),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM research_queue ORDER BY id ASC LIMIT ?", (limit,)
            ).fetchall()
        return [dict(r) for r in rows]


def next_pending() -> Optional[dict]:
    with db.get_conn() as conn:
        row = conn.execute(
            "SELECT * FROM research_queue WHERE status = 'pending' ORDER BY id ASC LIMIT 1"
        ).fetchone()
        return dict(row) if row else None


def mark_running(item_id: int) -> None:
    with db.get_conn() as conn:
        conn.execute("UPDATE research_queue SET status = 'running' WHERE id = ?", (item_id,))


def mark_done(item_id: int, result: str) -> None:
    with db.get_conn() as conn:
        conn.execute(
            "UPDATE research_queue SET status = 'done', result = ?, completed_at = datetime('now') "
            "WHERE id = ?",
            (result, item_id),
        )


def mark_error(item_id: int, error: str) -> None:
    with db.get_conn() as conn:
        conn.execute(
            "UPDATE research_queue SET status = 'error', result = ?, completed_at = datetime('now') "
            "WHERE id = ?",
            (error, item_id),
        )
