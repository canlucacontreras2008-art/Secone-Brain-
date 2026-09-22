import os
import tempfile
from dataclasses import dataclass
from typing import Any, Dict

import pytest

from app import config, db, research_queue
from app.brain import Brain


@pytest.fixture(autouse=True)
def temp_db(monkeypatch):
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    monkeypatch.setattr(config, "DB_PATH", path)
    db.init_db()
    research_queue.clear_stop()  # the stop flag is a module-level singleton
    yield
    research_queue.clear_stop()
    os.remove(path)


@dataclass
class FakeTextBlock:
    text: str
    type: str = "text"


@dataclass
class FakeToolUseBlock:
    id: str
    name: str
    input: Dict[str, Any]
    type: str = "tool_use"


def make_response(content, stop_reason="end_turn"):
    return type("Resp", (), {"content": content, "stop_reason": stop_reason})()


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


def test_run_research_queue_processes_pending_items_in_order():
    research_queue.enqueue(["Algorithm", "Classical mechanics"])
    brain = make_brain([
        make_response([FakeTextBlock("Summary of Algorithm.")]),
        make_response([FakeTextBlock("Summary of Classical mechanics.")]),
    ])

    result = brain.run_research_queue()

    assert result["remaining"] == 0
    assert [p["topic"] for p in result["processed"]] == ["Algorithm", "Classical mechanics"]
    assert all(p["status"] == "done" for p in result["processed"])

    done = research_queue.list_queue(status="done")
    assert len(done) == 2
    assert done[0]["result"] == "Summary of Algorithm."


def test_run_research_queue_respects_limit():
    research_queue.enqueue(["A", "B", "C"])
    brain = make_brain([make_response([FakeTextBlock("Summary A.")])])

    result = brain.run_research_queue(limit=1)

    assert result["remaining"] == 2
    assert len(result["processed"]) == 1
    assert research_queue.list_queue(status="pending")[0]["topic"] == "B"


def test_run_research_queue_marks_errors_and_keeps_going():
    research_queue.enqueue(["Bad topic", "Good topic"])

    class FailThenSucceedMessages:
        def __init__(self):
            self.calls = 0

        def create(self, **kwargs):
            self.calls += 1
            if self.calls == 1:
                raise RuntimeError("simulated API failure")
            return make_response([FakeTextBlock("Summary of Good topic.")])

    brain = Brain.__new__(Brain)
    brain.client = type("C", (), {"messages": FailThenSucceedMessages()})()

    result = brain.run_research_queue()

    statuses = {p["topic"]: p["status"] for p in result["processed"]}
    assert statuses == {"Bad topic": "error", "Good topic": "done"}
    assert research_queue.list_queue(status="error")[0]["topic"] == "Bad topic"
    assert research_queue.list_queue(status="done")[0]["topic"] == "Good topic"


def test_run_research_queue_with_empty_queue_is_a_noop():
    brain = make_brain([])

    result = brain.run_research_queue()

    assert result == {"processed": [], "remaining": 0, "stopped": False}


def test_run_research_queue_stops_between_topics_not_mid_scan():
    research_queue.enqueue(["First", "Second", "Third"])

    class StopWhileFirstIsInFlightMessages:
        """Simulates clicking Stop while "First" is still being scanned - the
        flag is only checked *between* topics, so First still completes."""

        def create(self, **kwargs):
            research_queue.request_stop()
            return make_response([FakeTextBlock("Summary of First.")])

    brain = Brain.__new__(Brain)
    brain.client = type("C", (), {"messages": StopWhileFirstIsInFlightMessages()})()

    result = brain.run_research_queue()

    assert result["stopped"] is True
    assert [p["topic"] for p in result["processed"]] == ["First"]
    pending_topics = [i["topic"] for i in research_queue.list_queue(status="pending")]
    assert pending_topics == ["Second", "Third"]
