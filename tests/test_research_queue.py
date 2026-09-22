import os
import tempfile

import pytest

from app import config, db, research_queue


@pytest.fixture(autouse=True)
def temp_db(monkeypatch):
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    monkeypatch.setattr(config, "DB_PATH", path)
    db.init_db()
    yield
    os.remove(path)


def test_enqueue_and_list():
    items = research_queue.enqueue(["Algorithm", "Classical mechanics"])

    assert len(items) == 2
    assert all(i["status"] == "pending" for i in items)

    listed = research_queue.list_queue()
    assert [i["topic"] for i in listed] == ["Algorithm", "Classical mechanics"]


def test_next_pending_returns_oldest_first():
    research_queue.enqueue(["First", "Second"])

    first = research_queue.next_pending()
    assert first["topic"] == "First"

    research_queue.mark_running(first["id"])
    second = research_queue.next_pending()
    assert second["topic"] == "Second"


def test_mark_done_and_error_update_status_and_result():
    [item] = research_queue.enqueue(["Gear"])
    research_queue.mark_running(item["id"])
    research_queue.mark_done(item["id"], "Learned several facts about gears.")

    [done_item] = research_queue.list_queue(status="done")
    assert done_item["result"] == "Learned several facts about gears."
    assert done_item["completed_at"] is not None

    [other] = research_queue.enqueue(["Broken topic"])
    research_queue.mark_error(other["id"], "boom")
    [errored] = research_queue.list_queue(status="error")
    assert errored["result"] == "boom"


def test_list_queue_filters_by_status():
    research_queue.enqueue(["A", "B"])
    pending = research_queue.list_queue(status="pending")
    done = research_queue.list_queue(status="done")

    assert len(pending) == 2
    assert len(done) == 0
