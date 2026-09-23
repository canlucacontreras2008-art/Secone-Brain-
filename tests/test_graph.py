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


def test_same_topic_creates_an_edge():
    memory.add_memory("fact", "Python is dynamically typed.", topic="Programming languages", tags=["python"])
    memory.add_memory("fact", "Rust has no garbage collector.", topic="Programming languages", tags=["rust"])
    memory.add_memory("fact", "The sky is blue.", topic="Sky")

    result = graph.build_graph()

    assert len(result["nodes"]) == 3
    same_topic_edges = [e for e in result["edges"] if e["kind"] == "same-topic"]
    assert len(same_topic_edges) == 1
    assert same_topic_edges[0]["topic"] == "Programming languages"

    degrees = {n["id"]: n["degree"] for n in result["nodes"]}
    assert sum(degrees.values()) == 2  # one edge touches two nodes


def test_large_shared_topic_uses_a_ring_not_a_clique():
    # 10 memories on one topic would be 45 edges as a full clique (unreadable
    # at any layout spacing) - past MAX_CLIQUE_TOPIC_SIZE, edges should form
    # a ring instead: exactly one edge per node. Unlike the old tag-based
    # design, a topic this large is still a real, single cluster - no upper
    # cutoff excludes it, since topic is an authoritative single field, not
    # a freeform tag that might just be a generic marker.
    for i in range(10):
        memory.add_memory("fact", f"Fact #{i} about Ada Lovelace.", topic="Ada Lovelace")

    result = graph.build_graph()

    same_topic_edges = [e for e in result["edges"] if e["kind"] == "same-topic"]
    assert len(same_topic_edges) == 10  # ring: one edge per node, not C(10, 2) = 45

    degrees = {n["id"]: n["degree"] for n in result["nodes"]}
    assert all(d == 2 for d in degrees.values())  # every node in a ring has degree 2

    branches = {n["branch"] for n in result["nodes"]}
    assert len(branches) == 1  # still one single cluster, just drawn as a ring


def test_shared_tags_do_not_merge_different_topics():
    # This is exactly what a batch of Wikipedia scans produces: every fact
    # carries the generic "wikipedia" tag, but each has its own distinct
    # topic. Tags are pure search metadata now - only topic drives grouping,
    # so sharing "wikipedia" must never merge unrelated topics into one
    # branch (the bug this guards against: "all topics on one globe").
    for i in range(11):
        memory.add_memory("fact", f"Algorithm fact #{i}.", topic="Algorithm", tags=["wikipedia"])
    for i in range(11):
        memory.add_memory("fact", f"Mechanics fact #{i}.", topic="Classical mechanics", tags=["wikipedia"])

    result = graph.build_graph()
    by_content = {n["detail"]: n for n in result["nodes"]}

    algorithm_branches = {by_content[f"Algorithm fact #{i}."]["branch"] for i in range(11)}
    mechanics_branches = {by_content[f"Mechanics fact #{i}."]["branch"] for i in range(11)}

    assert len(algorithm_branches) == 1  # all Algorithm facts share one branch
    assert len(mechanics_branches) == 1  # all mechanics facts share one branch
    assert algorithm_branches != mechanics_branches  # but the two topics are NOT merged

    # No edge should ever be keyed by a tag - "shared-tag" no longer exists.
    edge_kinds = {e["kind"] for e in result["edges"]}
    assert edge_kinds == {"same-topic"}


def test_memories_without_a_topic_stay_unbranched():
    memory.add_memory("fact", "Python is dynamically typed.", topic="Programming languages")
    memory.add_memory("fact", "Rust has no garbage collector.", topic="Programming languages")
    memory.add_memory("fact", "The sky is blue.")  # no topic at all

    result = graph.build_graph()
    by_content = {n["detail"]: n for n in result["nodes"]}

    assert by_content["Python is dynamically typed."]["branch"] is not None
    assert by_content["The sky is blue."]["branch"] is None
    assert by_content["The sky is blue."]["topic"] == ""


def test_branches_get_their_members_category():
    memory.add_memory("fact", "Gear fact.", topic="Gear", category="Mechanics")
    memory.add_memory("fact", "Another gear fact.", topic="Gear", category="Mechanics")
    memory.add_memory("fact", "Algorithm fact.", topic="Algorithm", category="Coding")
    memory.add_memory("fact", "Another algorithm fact.", topic="Algorithm", category="Coding")

    result = graph.build_graph()
    by_content = {n["detail"]: n for n in result["nodes"]}

    assert by_content["Gear fact."]["category"] == "Mechanics"
    assert by_content["Algorithm fact."]["category"] == "Coding"


def test_branch_without_any_category_stays_uncategorized():
    memory.add_memory("fact", "Python is dynamically typed.", topic="Programming languages")
    memory.add_memory("fact", "Rust has no garbage collector.", topic="Programming languages")

    result = graph.build_graph()

    assert {n["category"] for n in result["nodes"]} == {""}


def test_one_stray_category_does_not_split_the_branch():
    # Majority vote among the branch's own members - a single off-label
    # remember call shouldn't fork one topic's globe into two categories.
    memory.add_memory("fact", "Gear fact A.", topic="Gear", category="Mechanics")
    memory.add_memory("fact", "Gear fact B.", topic="Gear", category="Mechanics")
    memory.add_memory("fact", "Gear fact C.", topic="Gear", category="Science")

    result = graph.build_graph()

    assert {n["category"] for n in result["nodes"]} == {"Mechanics"}


def test_task_links_to_its_lesson():
    task_id = tasks.log_task("Do the thing", "Did the thing")
    memory.add_memory("lesson", "Always check the thing first.", source="task", task_id=task_id)

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
