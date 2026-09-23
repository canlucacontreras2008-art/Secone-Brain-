import os
import tempfile

import pytest

from app import config, db, research_queue, tools


@pytest.fixture(autouse=True)
def temp_db(monkeypatch):
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    monkeypatch.setattr(config, "DB_PATH", path)
    db.init_db()
    yield
    os.remove(path)


def test_queue_for_learning_enqueues_the_topic():
    result = tools.execute_tool("queue_for_learning", {"topic": "Quantum entanglement"})

    assert 'Queued "Quantum entanglement"' in result
    pending = research_queue.list_queue(status="pending")
    assert [item["topic"] for item in pending] == ["Quantum entanglement"]


def test_queue_for_learning_is_available_in_chat_but_not_wikipedia_scans():
    all_tool_names = {t["name"] for t in tools.ALL_TOOLS}
    wikipedia_tool_names = {t["name"] for t in tools.WIKIPEDIA_TOOLS}

    assert "queue_for_learning" in all_tool_names
    # A scan already IS the research - it shouldn't be able to queue more
    # research on itself.
    assert "queue_for_learning" not in wikipedia_tool_names


def test_unknown_tool_still_raises():
    with pytest.raises(ValueError):
        tools.execute_tool("not_a_real_tool", {})
