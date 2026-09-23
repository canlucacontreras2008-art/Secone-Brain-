import re
from collections import Counter
from typing import List, Optional

from . import db

_WORD_RE = re.compile(r"[a-z0-9']+")


def _tokenize(text: str) -> List[str]:
    return _WORD_RE.findall(text.lower())


def add_memory(
    kind: str,
    content: str,
    tags: Optional[List[str]] = None,
    source: str = "manual",
    task_id: Optional[int] = None,
    topic: str = "",
    category: str = "",
) -> int:
    tag_str = ",".join(tags or [])
    with db.get_conn() as conn:
        cur = conn.execute(
            "INSERT INTO memories (kind, content, tags, topic, category, source, task_id) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (kind, content, tag_str, topic, category, source, task_id),
        )
        return cur.lastrowid


def get_memory(memory_id: int) -> Optional[dict]:
    with db.get_conn() as conn:
        row = conn.execute("SELECT * FROM memories WHERE id = ?", (memory_id,)).fetchone()
        return dict(row) if row else None


def update_memory(
    memory_id: int,
    content: Optional[str] = None,
    topic: Optional[str] = None,
    category: Optional[str] = None,
    tags: Optional[List[str]] = None,
) -> Optional[dict]:
    """Update only the fields provided - None means "leave as is", not "clear"."""
    fields = []
    values = []
    if content is not None:
        fields.append("content = ?")
        values.append(content)
    if topic is not None:
        fields.append("topic = ?")
        values.append(topic)
    if category is not None:
        fields.append("category = ?")
        values.append(category)
    if tags is not None:
        fields.append("tags = ?")
        values.append(",".join(tags))

    if fields:
        with db.get_conn() as conn:
            conn.execute(f"UPDATE memories SET {', '.join(fields)} WHERE id = ?", (*values, memory_id))
    return get_memory(memory_id)


def delete_memory(memory_id: int) -> None:
    with db.get_conn() as conn:
        conn.execute("DELETE FROM memories WHERE id = ?", (memory_id,))


def list_memories(kind: Optional[str] = None, limit: int = 200) -> List[dict]:
    with db.get_conn() as conn:
        if kind:
            rows = conn.execute(
                "SELECT * FROM memories WHERE kind = ? ORDER BY id DESC LIMIT ?",
                (kind, limit),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM memories ORDER BY id DESC LIMIT ?", (limit,)
            ).fetchall()
        return [dict(r) for r in rows]


def recall(query: str, limit: int = 6) -> List[dict]:
    """Keyword-overlap relevance search over stored memories.

    No embeddings or external services - just token overlap between the query
    and each memory's content/tags. Good enough to bootstrap self-improvement;
    swap in a vector store later if recall quality becomes the bottleneck.
    """
    query_terms = Counter(_tokenize(query))
    if not query_terms:
        return []

    with db.get_conn() as conn:
        rows = conn.execute("SELECT * FROM memories").fetchall()

    scored = []
    for row in rows:
        haystack = Counter(
            _tokenize(row["content"] + " " + row["tags"] + " " + row["topic"] + " " + row["category"])
        )
        score = sum((haystack & query_terms).values())
        if score > 0:
            scored.append((score, dict(row)))

    scored.sort(key=lambda pair: pair[0], reverse=True)
    return [item for _, item in scored[:limit]]
