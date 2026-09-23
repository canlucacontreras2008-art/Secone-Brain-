import os
import tempfile

import pytest

from app import config, db, memory


@pytest.fixture(autouse=True)
def temp_db(monkeypatch):
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    monkeypatch.setattr(config, "DB_PATH", path)
    db.init_db()
    yield
    os.remove(path)


def test_add_and_recall():
    memory.add_memory("fact", "The user's favorite language is Python.", tags=["python", "preference"])
    memory.add_memory("fact", "Paris is the capital of France.", tags=["geography"])

    hits = memory.recall("What language does the user like?")

    assert hits
    assert "Python" in hits[0]["content"]


def test_recall_no_match_returns_empty():
    memory.add_memory("fact", "Some unrelated fact.", tags=[])

    assert memory.recall("zzz nonexistent query xyz") == []


def test_list_memories_filters_by_kind():
    memory.add_memory("fact", "A fact.", tags=[])
    memory.add_memory("lesson", "A lesson.", tags=[])

    lessons = memory.list_memories(kind="lesson")

    assert len(lessons) == 1
    assert lessons[0]["content"] == "A lesson."


def test_update_memory_only_changes_provided_fields():
    memory_id = memory.add_memory(
        "fact", "Gears transmit force.", tags=["wikipedia"], topic="Gear", category="Mechanics"
    )

    updated = memory.update_memory(memory_id, content="Gears transmit rotational force.")

    assert updated["content"] == "Gears transmit rotational force."
    assert updated["topic"] == "Gear"  # untouched
    assert updated["category"] == "Mechanics"  # untouched


def test_update_memory_replaces_tags():
    memory_id = memory.add_memory("fact", "A fact.", tags=["old"])

    updated = memory.update_memory(memory_id, tags=["new", "tags"])

    assert set(updated["tags"].split(",")) == {"new", "tags"}


def test_update_memory_on_missing_id_returns_none():
    assert memory.update_memory(999, content="doesn't matter") is None


def test_get_memory_returns_none_for_missing_id():
    assert memory.get_memory(999) is None


def test_delete_memory_removes_it():
    memory_id = memory.add_memory("fact", "Delete me.", tags=[])

    memory.delete_memory(memory_id)

    assert memory.get_memory(memory_id) is None
    assert memory.list_memories() == []


def test_delete_memory_of_missing_id_is_a_harmless_noop():
    memory.delete_memory(999)  # never raises, just matches zero rows
