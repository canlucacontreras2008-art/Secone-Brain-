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


def test_a_generic_tag_shared_across_many_topics_does_not_merge_branches():
    # This is exactly what a batch of Wikipedia scans produces: every fact
    # carries the generic "wikipedia" source tag *and* its own specific
    # topic tag. If "wikipedia" contributed edges, a ring would still fully
    # connect every fact from every topic into one giant component - the
    # bug this test guards against ("all topics ended up on one globe").
    # 11 + 11 = 22 facts share "wikipedia" - over MAX_TAG_FANOUT_FOR_EDGES (20),
    # while each topic tag alone (11) stays comfortably under it.
    for i in range(11):
        memory.add_memory("fact", f"Algorithm fact #{i}.", tags=["wikipedia", "Algorithm"])
    for i in range(11):
        memory.add_memory("fact", f"Mechanics fact #{i}.", tags=["wikipedia", "Classical mechanics"])

    result = graph.build_graph()
    by_content = {n["detail"]: n for n in result["nodes"]}

    algorithm_branches = {by_content[f"Algorithm fact #{i}."]["branch"] for i in range(11)}
    mechanics_branches = {by_content[f"Mechanics fact #{i}."]["branch"] for i in range(11)}

    assert len(algorithm_branches) == 1  # all Algorithm facts share one branch
    assert len(mechanics_branches) == 1  # all mechanics facts share one branch
    assert algorithm_branches != mechanics_branches  # but the two topics are NOT merged

    # The "wikipedia" tag itself must not appear on any edge - it's excluded
    # as too generic (shared by more memories than MAX_TAG_FANOUT_FOR_EDGES).
    tags_used = {e.get("tag") for e in result["edges"] if e["kind"] == "shared-tag"}
    assert "wikipedia" not in tags_used


def test_connected_memories_share_a_branch_and_isolated_ones_dont():
    memory.add_memory("fact", "Python is dynamically typed.", tags=["python", "languages"])
    memory.add_memory("fact", "Rust has no garbage collector.", tags=["rust", "languages"])
    memory.add_memory("fact", "The sky is blue.", tags=["sky"])  # no shared tag with anything

    result = graph.build_graph()
    by_content = {n["detail"]: n for n in result["nodes"]}

    python_branch = by_content["Python is dynamically typed."]["branch"]
    rust_branch = by_content["Rust has no garbage collector."]["branch"]
    sky_branch = by_content["The sky is blue."]["branch"]

    assert python_branch is not None
    assert python_branch == rust_branch  # connected via the "languages" tag
    assert sky_branch is None  # isolated - no edges, so no branch


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
