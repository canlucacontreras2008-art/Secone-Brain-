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
) -> int:
    tag_str = ",".join(tags or [])
    with db.get_conn() as conn:
        cur = conn.execute(
            "INSERT INTO memories (kind, content, tags, source) VALUES (?, ?, ?, ?)",
            (kind, content, tag_str, source),
        )
        return cur.lastrowid


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
        haystack = Counter(_tokenize(row["content"] + " " + row["tags"]))
        score = sum((haystack & query_terms).values())
        if score > 0:
            scored.append((score, dict(row)))

    scored.sort(key=lambda pair: pair[0], reverse=True)
    return [item for _, item in scored[:limit]]
