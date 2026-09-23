import os
import tempfile

import pytest

from app import calendar_tool, config, db, gmail_tool, research_queue, tools


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


def test_calendar_tools_are_available_in_chat_but_not_wikipedia_scans():
    all_tool_names = {t["name"] for t in tools.ALL_TOOLS}
    wikipedia_tool_names = {t["name"] for t in tools.WIKIPEDIA_TOOLS}
    calendar_names = {
        "calendar_list_events",
        "calendar_create_event",
        "calendar_update_event",
        "calendar_delete_event",
    }

    assert calendar_names <= all_tool_names
    assert not (calendar_names & wikipedia_tool_names)


def test_calendar_list_events_dispatch_formats_events(monkeypatch):
    monkeypatch.setattr(
        calendar_tool,
        "list_events",
        lambda **kwargs: [
            {"id": "e1", "summary": "Dentist", "start": "2026-09-24T15:00:00-07:00",
             "end": "2026-09-24T16:00:00-07:00", "location": "Main St", "description": ""}
        ],
    )

    result = tools.execute_tool("calendar_list_events", {"query": "dentist"})

    assert "[e1] Dentist" in result
    assert "@ Main St" in result


def test_calendar_list_events_dispatch_reports_no_events(monkeypatch):
    monkeypatch.setattr(calendar_tool, "list_events", lambda **kwargs: [])

    result = tools.execute_tool("calendar_list_events", {})

    assert result == "No events found in that range."


def test_calendar_create_event_dispatch_calls_through(monkeypatch):
    captured = {}

    def fake_create_event(**kwargs):
        captured.update(kwargs)
        return {"id": "new1", "summary": kwargs["summary"], "start": kwargs["start"], "end": kwargs["end"]}

    monkeypatch.setattr(calendar_tool, "create_event", fake_create_event)

    result = tools.execute_tool(
        "calendar_create_event",
        {"summary": "Dentist", "start": "2026-09-24T15:00:00-07:00", "end": "2026-09-24T16:00:00-07:00"},
    )

    assert captured["summary"] == "Dentist"
    assert "Created event [new1]" in result


def test_calendar_update_event_dispatch_excludes_event_id_from_fields(monkeypatch):
    captured = {}

    def fake_update_event(event_id, **fields):
        captured["event_id"] = event_id
        captured["fields"] = fields
        return {"id": event_id, "summary": fields.get("summary", "Dentist")}

    monkeypatch.setattr(calendar_tool, "update_event", fake_update_event)

    result = tools.execute_tool("calendar_update_event", {"event_id": "e1", "summary": "Dentist (moved)"})

    assert captured["event_id"] == "e1"
    assert captured["fields"] == {"summary": "Dentist (moved)"}
    assert "Updated event [e1]" in result


def test_calendar_delete_event_dispatch_calls_through(monkeypatch):
    captured = {}
    monkeypatch.setattr(calendar_tool, "delete_event", lambda event_id: captured.setdefault("event_id", event_id))

    result = tools.execute_tool("calendar_delete_event", {"event_id": "e1"})

    assert captured["event_id"] == "e1"
    assert "Deleted event e1" in result


def test_gmail_tools_are_available_in_chat_but_not_wikipedia_scans():
    all_tool_names = {t["name"] for t in tools.ALL_TOOLS}
    wikipedia_tool_names = {t["name"] for t in tools.WIKIPEDIA_TOOLS}
    gmail_names = {
        "gmail_list_messages",
        "gmail_read_message",
        "gmail_create_draft",
        "gmail_send_message",
    }

    assert gmail_names <= all_tool_names
    assert not (gmail_names & wikipedia_tool_names)


def test_gmail_list_messages_dispatch_formats_messages(monkeypatch):
    monkeypatch.setattr(
        gmail_tool,
        "list_messages",
        lambda **kwargs: [
            {"id": "m1", "subject": "Hello", "from": "a@b.com", "date": "Mon", "snippet": "Hi there"}
        ],
    )

    result = tools.execute_tool("gmail_list_messages", {"query": "is:unread"})

    assert "[m1] Hello" in result
    assert "a@b.com" in result


def test_gmail_list_messages_dispatch_reports_no_messages(monkeypatch):
    monkeypatch.setattr(gmail_tool, "list_messages", lambda **kwargs: [])

    result = tools.execute_tool("gmail_list_messages", {})

    assert result == "No messages found."


def test_gmail_read_message_dispatch_formats_the_message(monkeypatch):
    monkeypatch.setattr(
        gmail_tool,
        "get_message",
        lambda message_id: {
            "id": message_id, "subject": "Hello", "from": "a@b.com", "to": "me@example.com",
            "date": "Mon", "body": "Hello there.",
        },
    )

    result = tools.execute_tool("gmail_read_message", {"message_id": "m1"})

    assert "Subject: Hello" in result
    assert "Hello there." in result


def test_gmail_create_draft_dispatch_never_sends(monkeypatch):
    captured = {}

    def fake_create_draft(**kwargs):
        captured.update(kwargs)
        return {"id": "d1", "to": kwargs["to"], "subject": kwargs["subject"]}

    monkeypatch.setattr(gmail_tool, "create_draft", fake_create_draft)
    # gmail_send_message must never be touched by a draft dispatch.
    monkeypatch.setattr(
        gmail_tool, "send_message", lambda **kwargs: pytest.fail("create_draft must not send")
    )

    result = tools.execute_tool(
        "gmail_create_draft", {"to": "a@b.com", "subject": "Hi", "body": "Hello there"}
    )

    assert captured["to"] == "a@b.com"
    assert "Created draft [d1]" in result


def test_gmail_send_message_dispatch_calls_through(monkeypatch):
    captured = {}

    def fake_send_message(**kwargs):
        captured.update(kwargs)
        return {"id": "s1", "to": kwargs["to"], "subject": kwargs["subject"]}

    monkeypatch.setattr(gmail_tool, "send_message", fake_send_message)

    result = tools.execute_tool(
        "gmail_send_message", {"to": "a@b.com", "subject": "Hi", "body": "Hello there"}
    )

    assert captured["to"] == "a@b.com"
    assert "Sent message [s1]" in result
