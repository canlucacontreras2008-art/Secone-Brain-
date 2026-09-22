import os
import tempfile
from dataclasses import dataclass, field
from typing import Any, Dict

import pytest

from app import config, db, memory, tools
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
    brain = Brain.__new__(Brain)  # skip __init__ - avoid a real anthropic.Anthropic()
    brain.client = SequencedFakeClient(responses)
    return brain


def test_scan_wikipedia_stores_facts_and_uses_scoped_tools():
    responses = [
        make_response(
            [
                FakeToolUseBlock(
                    id="t1",
                    name="remember",
                    input={
                        "kind": "fact",
                        "content": "Water boils at 100C at sea level.",
                        # Deliberately a *different* phrasing than the scan
                        # topic - the server-side override must win regardless.
                        "topic": "Water (chemistry)",
                        "tags": ["water", "physics", "wikipedia"],
                    },
                )
            ],
            stop_reason="tool_use",
        ),
        make_response([FakeTextBlock("Summary of the Water article.")]),
    ]
    brain = make_brain(responses)

    result = brain.scan_wikipedia(["Water"])

    assert result["scanned"] == [{"topic": "Water", "summary": "Summary of the Water article."}]

    stored = memory.list_memories(kind="fact")
    assert len(stored) == 1
    assert stored[0]["content"] == "Water boils at 100C at sea level."
    # Server-side default_topic overrides whatever the model said - this is
    # what stops "Water" / "Water (chemistry)" / etc. from fragmenting into
    # separate topic globes for what is really one subject.
    assert stored[0]["topic"] == "Water"
    assert set(stored[0]["tags"].split(",")) == {"water", "physics", "wikipedia"}

    first_call_tools = brain.client.messages.calls[0]["tools"]
    assert first_call_tools == tools.WIKIPEDIA_TOOLS
    tool_names = {t["name"] for t in first_call_tools}
    assert tool_names == {"web_search", "web_fetch", "remember"}


class InfiniteToolUseFakeMessages:
    """Always returns a tool_use response - simulates a scan that never
    reaches end_turn, to check how many iterations the loop allows before
    giving up."""

    def __init__(self):
        self.calls = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        return make_response(
            [FakeToolUseBlock(id="t", name="remember", input={"kind": "fact", "content": "x", "tags": []})],
            stop_reason="tool_use",
        )


def test_scan_wikipedia_allows_more_iterations_than_the_default_cap():
    brain = Brain.__new__(Brain)
    brain.client = type("C", (), {"messages": InfiniteToolUseFakeMessages()})()

    result = brain.scan_wikipedia(["Never-ending topic"])

    # A thorough article needs more than the default chat/task cap
    # (config.MAX_TOOL_ITERATIONS) - scan_wikipedia raises it to 20.
    assert len(brain.client.messages.calls) == 20
    assert result["scanned"][0]["summary"] == (
        "I hit my step limit on this turn - here's where I got to so far."
    )


def test_scan_wikipedia_visits_each_topic_in_order():
    responses = [
        make_response([FakeTextBlock("Summary A")]),
        make_response([FakeTextBlock("Summary B")]),
    ]
    brain = make_brain(responses)

    result = brain.scan_wikipedia(["Topic A", "Topic B"])

    assert result["scanned"] == [
        {"topic": "Topic A", "summary": "Summary A"},
        {"topic": "Topic B", "summary": "Summary B"},
    ]
    assert len(brain.client.messages.calls) == 2
