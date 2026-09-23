import os
import tempfile

import pytest

from app import config, db, task_queue


@pytest.fixture(autouse=True)
def temp_db(monkeypatch):
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    monkeypatch.setattr(config, "DB_PATH", path)
    db.init_db()
    task_queue.clear_stop()  # the stop flag is a module-level singleton
    yield
    task_queue.clear_stop()
    os.remove(path)


def test_enqueue_and_list():
    items = task_queue.enqueue(["Summarize a report", "Clean up the inbox"])

    assert len(items) == 2
    assert all(i["status"] == "pending" for i in items)

    listed = task_queue.list_queue()
    assert [i["description"] for i in listed] == ["Summarize a report", "Clean up the inbox"]


def test_next_pending_returns_oldest_first():
    task_queue.enqueue(["First", "Second"])

    first = task_queue.next_pending()
    assert first["description"] == "First"

    task_queue.mark_running(first["id"])
    second = task_queue.next_pending()
    assert second["description"] == "Second"


def test_mark_done_and_error_update_status_and_result():
    [item] = task_queue.enqueue(["Do the thing"])
    task_queue.mark_running(item["id"])
    task_queue.mark_done(item["id"], "Did the thing.", task_id=42)

    [done_item] = task_queue.list_queue(status="done")
    assert done_item["result"] == "Did the thing."
    assert done_item["task_id"] == 42
    assert done_item["completed_at"] is not None

    [other] = task_queue.enqueue(["Broken task"])
    task_queue.mark_error(other["id"], "boom")
    [errored] = task_queue.list_queue(status="error")
    assert errored["result"] == "boom"


def test_list_queue_filters_by_status():
    task_queue.enqueue(["A", "B"])
    pending = task_queue.list_queue(status="pending")
    done = task_queue.list_queue(status="done")

    assert len(pending) == 2
    assert len(done) == 0


def test_delete_removes_the_item():
    [a, b] = task_queue.enqueue(["A", "B"])

    task_queue.delete(a["id"])

    remaining = task_queue.list_queue()
    assert [i["id"] for i in remaining] == [b["id"]]


def test_delete_of_missing_id_is_a_harmless_noop():
    task_queue.delete(999)  # never raises, just matches zero rows
    assert task_queue.list_queue() == []


def test_stop_flag_round_trip():
    assert task_queue.stop_requested() is False

    task_queue.request_stop()
    assert task_queue.stop_requested() is True

    task_queue.clear_stop()
    assert task_queue.stop_requested() is False
