"""Builds the node-link graph of the brain's memory for the /graph interface.

Nodes are memories (facts, lessons) and tasks. Edges come from two real
relationships, not a layout guess: a task links to the lesson it produced
(`memories.task_id`), and memories link to each other when they share a tag.
"""

from itertools import combinations
from typing import Dict, List

from . import db

# Above this many memories, skip pairwise tag-overlap edges (O(n^2)) - the
# graph is still fully populated with nodes and task->lesson edges either way.
MAX_NODES_FOR_TAG_EDGES = 600

# A tag shared by more than this many memories (e.g. every fact from one
# Wikipedia scan sharing the article's topic tag) would draw a full clique -
# n=26 alone is 325 edges, unreadable regardless of layout spacing. Past this
# size, connect that tag's members in a ring instead: still visually groups
# them into one cluster, but with O(n) edges instead of O(n^2).
MAX_CLIQUE_TAG_SIZE = 6


def _truncate(text: str, length: int = 80) -> str:
    text = " ".join(text.split())
    return text if len(text) <= length else text[: length - 1].rstrip() + "…"


def build_graph() -> Dict[str, List[dict]]:
    with db.get_conn() as conn:
        memory_rows = [dict(r) for r in conn.execute("SELECT * FROM memories")]
        task_rows = [dict(r) for r in conn.execute("SELECT * FROM task_log")]

    nodes: Dict[str, dict] = {}
    edges: List[dict] = []

    for task in task_rows:
        node_id = f"t{task['id']}"
        nodes[node_id] = {
            "id": node_id,
            "kind": "task",
            "label": _truncate(task["description"]),
            "detail": task["result"],
            "tags": [],
            "source": "task_log",
            "created_at": task["created_at"],
            "degree": 0,
        }

    tag_index: Dict[str, List[str]] = {}

    for mem in memory_rows:
        node_id = f"m{mem['id']}"
        tags = [t for t in mem["tags"].split(",") if t]
        nodes[node_id] = {
            "id": node_id,
            "kind": mem["kind"],
            "label": _truncate(mem["content"]),
            "detail": mem["content"],
            "tags": tags,
            "source": mem["source"],
            "created_at": mem["created_at"],
            "degree": 0,
        }
        for tag in tags:
            tag_index.setdefault(tag, []).append(node_id)

        if mem["task_id"] is not None:
            task_node_id = f"t{mem['task_id']}"
            if task_node_id in nodes:
                edges.append({"source": task_node_id, "target": node_id, "kind": "produced"})

    if len(nodes) <= MAX_NODES_FOR_TAG_EDGES:
        seen_pairs = set()
        for tag, node_ids in tag_index.items():
            ids = sorted(set(node_ids))
            if len(ids) < 2:
                continue
            if len(ids) <= MAX_CLIQUE_TAG_SIZE:
                pairs = combinations(ids, 2)
            else:
                pairs = zip(ids, ids[1:] + ids[:1])
            for a, b in pairs:
                pair = tuple(sorted((a, b)))
                if pair in seen_pairs:
                    continue
                seen_pairs.add(pair)
                edges.append({"source": pair[0], "target": pair[1], "kind": "shared-tag", "tag": tag})

    for edge in edges:
        nodes[edge["source"]]["degree"] += 1
        nodes[edge["target"]]["degree"] += 1

    return {"nodes": list(nodes.values()), "edges": edges}
