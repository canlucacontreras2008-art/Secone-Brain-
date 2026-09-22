import json
import os
import tempfile
from dataclasses import dataclass
from typing import List

import pytest

from app import config, db, memory, tasks
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


class FakeMessages:
    def __init__(self, payload: dict):
        self.payload = payload

    def create(self, **kwargs):
        return type("Resp", (), {"content": [FakeTextBlock(json.dumps(self.payload))]})()


class FakeClient:
    def __init__(self, payload: dict):
        self.messages = FakeMessages(payload)


def make_brain(payload: dict) -> Brain:
    brain = Brain.__new__(Brain)  # skip __init__ - avoid constructing a real anthropic.Anthropic()
    brain.client = FakeClient(payload)
    return brain


def test_reflect_stores_lesson_with_model_provided_tags():
    task_id = tasks.log_task("Summarize a report", "Summarized it")
    brain = make_brain({"lesson": "Always skim the executive summary first.", "tags": ["reports", "reading"]})

    lesson = brain._reflect("Summarize a report", "Summarized it", task_id=task_id)

    assert lesson == "Always skim the executive summary first."
    stored = memory.list_memories(kind="lesson")
    assert len(stored) == 1
    assert stored[0]["task_id"] == task_id
    assert set(stored[0]["tags"].split(",")) == {"reports", "reading"}


def test_reflect_stores_nothing_when_lesson_is_null():
    task_id = tasks.log_task("Trivial task", "Done")
    brain = make_brain({"lesson": None, "tags": []})

    lesson = brain._reflect("Trivial task", "Done", task_id=task_id)

    assert lesson == ""
    assert memory.list_memories(kind="lesson") == []
