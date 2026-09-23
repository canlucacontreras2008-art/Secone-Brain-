import os
import tempfile
from dataclasses import dataclass
from typing import Any, Dict

import pytest

from app import config, db
from app.brain import Brain


@pytest.fixture(autouse=True)
def temp_db(monkeypatch):
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    monkeypatch.setattr(config, "DB_PATH", path)
    db.init_db()
    yield
    os.remove(path)


@dataclass
class FakeTextBlock:
    text: str
    type: str = "text"


def make_response(content, stop_reason="end_turn"):
    return type("Resp", (), {"content": content, "stop_reason": stop_reason})()


class RecordingFakeMessages:
    def __init__(self):
        self.calls = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        if kwargs.get("output_config"):
            # run_task's follow-up _reflect() call - valid JSON, no lesson.
            return make_response(
                [FakeTextBlock('{"lesson": null, "topic": "", "category": "", "tags": []}')]
            )
        return make_response([FakeTextBlock("ok")])


def make_brain() -> Brain:
    brain = Brain.__new__(Brain)
    brain.client = type("C", (), {"messages": RecordingFakeMessages()})()
    return brain


def test_chat_system_prompt_includes_current_date_and_time():
    brain = make_brain()

    brain.chat("What's on my schedule?")

    system = brain.client.messages.calls[0]["system"]
    assert "Current date and time:" in system
    assert "RFC3339:" in system


def test_run_task_system_prompt_also_includes_current_date_and_time():
    brain = make_brain()

    brain.run_task("Do something")

    system = brain.client.messages.calls[0]["system"]
    assert "Current date and time:" in system
