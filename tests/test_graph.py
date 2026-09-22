import os
import tempfile

import pytest

from app import config, db, graph, memory, tasks


@pytest.fixture(autouse=True)
def temp_db(monkeypatch):
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    monkeypatch.setattr(config, "DB_PATH", path)
    db.init_db()
    yield
    os.remove(path)


def test_empty_graph():
    result = graph.build_graph()
    assert result == {"nodes": [], "edges": []}


def test_shared_tag_edge_between_memories():
    memory.add_memory("fact", "Python is dynamically typed.", tags=["python", "languages"])
    memory.add_memory("fact", "Rust has no garbage collector.", tags=["rust", "languages"])
    memory.add_memory("fact", "The sky is blue.", tags=["sky"])

    result = graph.build_graph()

    assert len(result["nodes"]) == 3
    shared_tag_edges = [e for e in result["edges"] if e["kind"] == "shared-tag"]
    assert len(shared_tag_edges) == 1
    assert shared_tag_edges[0]["tag"] == "languages"

    degrees = {n["id"]: n["degree"] for n in result["nodes"]}
    assert sum(degrees.values()) == 2  # one edge touches two nodes


def test_large_shared_tag_cluster_uses_a_ring_not_a_clique():
    # 10 memories all sharing one tag would be 45 edges as a full clique
    # (unreadable at any layout spacing) - past MAX_CLIQUE_TAG_SIZE, edges
    # should form a ring instead: exactly one edge per node.
    for i in range(10):
        memory.add_memory("fact", f"Fact #{i} about Ada Lovelace.", tags=["Ada Lovelace"])

    result = graph.build_graph()

    shared_tag_edges = [e for e in result["edges"] if e["kind"] == "shared-tag"]
    assert len(shared_tag_edges) == 10  # ring: one edge per node, not C(10, 2) = 45

    degrees = {n["id"]: n["degree"] for n in result["nodes"]}
    assert all(d == 2 for d in degrees.values())  # every node in a ring has degree 2


def test_task_links_to_its_lesson():
    task_id = tasks.log_task("Do the thing", "Did the thing")
    memory.add_memory("lesson", "Always check the thing first.", tags=[], source="task", task_id=task_id)

    result = graph.build_graph()

    task_node = next(n for n in result["nodes"] if n["kind"] == "task")
    lesson_node = next(n for n in result["nodes"] if n["kind"] == "lesson")
    produced_edges = [e for e in result["edges"] if e["kind"] == "produced"]

    assert len(produced_edges) == 1
    assert produced_edges[0] == {
        "source": task_node["id"],
        "target": lesson_node["id"],
        "kind": "produced",
    }
