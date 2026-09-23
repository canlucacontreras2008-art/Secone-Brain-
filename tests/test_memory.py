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


# --- FTS5 index sync (see db.FTS_SCHEMA) - recall() is only as correct as
# these triggers keeping memories_fts in step with memories.

def test_recall_reflects_an_edited_memory():
    memory_id = memory.add_memory("fact", "The sky is blue.", tags=[])

    assert memory.recall("ocean") == []  # doesn't match yet

    memory.update_memory(memory_id, content="The ocean is deep.")

    hits = memory.recall("ocean")
    assert len(hits) == 1
    assert hits[0]["content"] == "The ocean is deep."

    assert memory.recall("sky") == []  # old wording no longer matches


def test_recall_does_not_return_a_deleted_memory():
    memory_id = memory.add_memory("fact", "A fact about gears.", tags=[])
    assert memory.recall("gears")

    memory.delete_memory(memory_id)

    assert memory.recall("gears") == []


def test_recall_finds_rows_that_predate_the_fts_index():
    # Simulate a database that predates this index entirely (an old DB
    # upgrading to this feature, or one copied in from elsewhere): drop the
    # table and triggers init_db() already created, then insert a row
    # directly the way old code (with no index or triggers at all) would
    # have. Re-running init_db() should notice memories_fts doesn't exist
    # yet, recreate it, and backfill this pre-existing row into it.
    with db.get_conn() as conn:
        conn.executescript(
            "DROP TRIGGER memories_fts_ai; DROP TRIGGER memories_fts_ad; "
            "DROP TRIGGER memories_fts_au; DROP TABLE memories_fts;"
        )
        conn.execute(
            "INSERT INTO memories (kind, content, tags, topic, category, source) "
            "VALUES ('fact', 'A fact inserted before the index existed.', '', '', '', 'manual')"
        )

    db.init_db()

    hits = memory.recall("inserted")
    assert len(hits) == 1
    assert hits[0]["content"] == "A fact inserted before the index existed."
