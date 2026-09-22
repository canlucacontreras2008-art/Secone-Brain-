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
