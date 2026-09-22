from typing import List

from . import db


def log_task(description: str, result: str) -> int:
    with db.get_conn() as conn:
        cur = conn.execute(
            "INSERT INTO task_log (description, result) VALUES (?, ?)",
            (description, result),
        )
        return cur.lastrowid


def set_reflection(task_id: int, reflection: str) -> None:
    with db.get_conn() as conn:
        conn.execute(
            "UPDATE task_log SET reflection = ? WHERE id = ?",
            (reflection, task_id),
        )


def list_tasks(limit: int = 200) -> List[dict]:
    with db.get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM task_log ORDER BY id DESC LIMIT ?", (limit,)
        ).fetchall()
        return [dict(r) for r in rows]
