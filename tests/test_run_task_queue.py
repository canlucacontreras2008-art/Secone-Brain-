import json
import os
import tempfile
from dataclasses import dataclass

import pytest

from app import config, db, task_queue
from app.brain import Brain


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


@dataclass
class FakeTextBlock:
    text: str
    type: str = "text"


def make_response(content, stop_reason="end_turn"):
    return type("Resp", (), {"content": content, "stop_reason": stop_reason})()


def make_reflect_response(lesson=None):
    payload = {"lesson": lesson, "topic": "", "category": "", "tags": []}
    return make_response([FakeTextBlock(json.dumps(payload))])


class SequencedFakeMessages:
    def __init__(self, responses):
        self._responses = list(responses)
        self.calls = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        return self._responses.pop(0)


class SequencedFakeClient:
    def __init__(self, responses):
        self.messages = SequencedFakeMessages(responses)


def make_brain(responses) -> Brain:
    brain = Brain.__new__(Brain)
    brain.client = SequencedFakeClient(responses)
    return brain


def test_run_task_queue_processes_pending_items_in_order():
    task_queue.enqueue(["Summarize a report", "Clean up the inbox"])
    # Each task consumes two calls: the main run_task() loop, then _reflect().
    brain = make_brain(
        [
            make_response([FakeTextBlock("Summarized the report.")]),
            make_reflect_response(),
            make_response([FakeTextBlock("Cleaned up the inbox.")]),
            make_reflect_response(),
        ]
    )

    result = brain.run_task_queue()

    assert result["remaining"] == 0
    assert [p["description"] for p in result["processed"]] == ["Summarize a report", "Clean up the inbox"]
    assert all(p["status"] == "done" for p in result["processed"])

    done = task_queue.list_queue(status="done")
    assert len(done) == 2
    assert done[0]["result"] == "Summarized the report."
    assert done[0]["task_id"] is not None


def test_run_task_queue_respects_limit():
    task_queue.enqueue(["A", "B", "C"])
    brain = make_brain([make_response([FakeTextBlock("Did A.")]), make_reflect_response()])

    result = brain.run_task_queue(limit=1)

    assert result["remaining"] == 2
    assert len(result["processed"]) == 1
    assert task_queue.list_queue(status="pending")[0]["description"] == "B"


def test_run_task_queue_marks_errors_and_keeps_going():
    task_queue.enqueue(["Bad task", "Good task"])

    class FailThenSucceedMessages:
        def __init__(self):
            self.calls = 0

        def create(self, **kwargs):
            self.calls += 1
            if self.calls == 1:
                raise RuntimeError("simulated API failure")
            if kwargs.get("output_config"):
                return make_reflect_response()
            return make_response([FakeTextBlock("Did the good task.")])

    brain = Brain.__new__(Brain)
    brain.client = type("C", (), {"messages": FailThenSucceedMessages()})()

    result = brain.run_task_queue()

    statuses = {p["description"]: p["status"] for p in result["processed"]}
    assert statuses == {"Bad task": "error", "Good task": "done"}
    assert task_queue.list_queue(status="error")[0]["description"] == "Bad task"
    assert task_queue.list_queue(status="done")[0]["description"] == "Good task"


def test_run_task_queue_with_empty_queue_is_a_noop():
    brain = make_brain([])

    result = brain.run_task_queue()

    assert result == {"processed": [], "remaining": 0, "stopped": False}


def test_run_task_queue_stops_between_tasks_not_mid_task():
    task_queue.enqueue(["First", "Second", "Third"])

    class StopWhileFirstIsInFlightMessages:
        """Simulates clicking Stop while "First" is still running - the flag
        is only checked *between* tasks, so First still completes (both its
        main loop and its reflection) before the queue halts."""

        def create(self, **kwargs):
            task_queue.request_stop()
            if kwargs.get("output_config"):
                return make_reflect_response()
            return make_response([FakeTextBlock("Summary of First.")])

    brain = Brain.__new__(Brain)
    brain.client = type("C", (), {"messages": StopWhileFirstIsInFlightMessages()})()

    result = brain.run_task_queue()

    assert result["stopped"] is True
    assert [p["description"] for p in result["processed"]] == ["First"]
    pending = [i["description"] for i in task_queue.list_queue(status="pending")]
    assert pending == ["Second", "Third"]
