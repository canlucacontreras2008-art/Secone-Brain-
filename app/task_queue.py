import threading
from typing import List, Optional

from . import db

# Same reasoning as research_queue._stop_event: a plain module-level Event is
# enough for a single-server personal app, not a distributed job queue.
# Deliberately NOT wired into Brain._run_loop itself - that's shared by
# /chat and a manually-triggered /task too, and a "stop the task queue"
# click must never abort an unrelated concurrent request.
_stop_event = threading.Event()


def request_stop() -> None:
    _stop_event.set()


def clear_stop() -> None:
    _stop_event.clear()


def stop_requested() -> bool:
    return _stop_event.is_set()


def delete(item_id: int) -> None:
    with db.get_conn() as conn:
        conn.execute("DELETE FROM task_queue WHERE id = ?", (item_id,))


def enqueue(descriptions: List[str]) -> List[dict]:
    with db.get_conn() as conn:
        items = []
        for description in descriptions:
            cur = conn.execute("INSERT INTO task_queue (description) VALUES (?)", (description,))
            items.append({"id": cur.lastrowid, "description": description, "status": "pending"})
        return items


def list_queue(status: Optional[str] = None, limit: int = 200) -> List[dict]:
    with db.get_conn() as conn:
        if status:
            rows = conn.execute(
                "SELECT * FROM task_queue WHERE status = ? ORDER BY id ASC LIMIT ?",
                (status, limit),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM task_queue ORDER BY id ASC LIMIT ?", (limit,)
            ).fetchall()
        return [dict(r) for r in rows]


def next_pending() -> Optional[dict]:
    with db.get_conn() as conn:
        row = conn.execute(
            "SELECT * FROM task_queue WHERE status = 'pending' ORDER BY id ASC LIMIT 1"
        ).fetchone()
        return dict(row) if row else None


def mark_running(item_id: int) -> None:
    with db.get_conn() as conn:
        conn.execute("UPDATE task_queue SET status = 'running' WHERE id = ?", (item_id,))


def mark_done(item_id: int, result: str, task_id: int) -> None:
    with db.get_conn() as conn:
        conn.execute(
            "UPDATE task_queue SET status = 'done', result = ?, task_id = ?, "
            "completed_at = datetime('now') WHERE id = ?",
            (result, task_id, item_id),
        )


def mark_error(item_id: int, error: str) -> None:
    with db.get_conn() as conn:
        conn.execute(
            "UPDATE task_queue SET status = 'error', result = ?, completed_at = datetime('now') "
            "WHERE id = ?",
            (error, item_id),
        )
