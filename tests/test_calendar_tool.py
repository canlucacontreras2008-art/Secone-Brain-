import pytest

from app import calendar_tool, config


class FakeExecutable:
    def __init__(self, result):
        self.result = result

    def execute(self):
        return self.result


class FakeEventsAPI:
    def __init__(self, list_result=None, insert_result=None, patch_result=None):
        self.list_result = list_result if list_result is not None else {"items": []}
        self.insert_result = insert_result
        self.patch_result = patch_result
        self.calls = []

    def list(self, **kwargs):
        self.calls.append(("list", kwargs))
        return FakeExecutable(self.list_result)

    def insert(self, **kwargs):
        self.calls.append(("insert", kwargs))
        return FakeExecutable(self.insert_result)

    def patch(self, **kwargs):
        self.calls.append(("patch", kwargs))
        return FakeExecutable(self.patch_result)

    def delete(self, **kwargs):
        self.calls.append(("delete", kwargs))
        return FakeExecutable(None)


class FakeService:
    def __init__(self, events_api):
        self._events_api = events_api

    def events(self):
        return self._events_api


RAW_EVENT = {
    "id": "abc123",
    "summary": "Dentist",
    "start": {"dateTime": "2026-09-24T15:00:00-07:00"},
    "end": {"dateTime": "2026-09-24T16:00:00-07:00"},
    "location": "Main St",
    "description": "Annual checkup",
}


def test_list_events_returns_simplified_events():
    api = FakeEventsAPI(list_result={"items": [RAW_EVENT]})
    events = calendar_tool.list_events(
        time_min="2026-09-24T00:00:00-07:00", time_max="2026-09-25T00:00:00-07:00", service=FakeService(api)
    )

    assert events == [
        {
            "id": "abc123",
            "summary": "Dentist",
            "start": "2026-09-24T15:00:00-07:00",
            "end": "2026-09-24T16:00:00-07:00",
            "location": "Main St",
            "description": "Annual checkup",
        }
    ]
    assert api.calls[0][0] == "list"
    assert api.calls[0][1]["timeMin"] == "2026-09-24T00:00:00-07:00"


def test_list_events_defaults_time_range_when_omitted():
    api = FakeEventsAPI()
    calendar_tool.list_events(service=FakeService(api))

    kwargs = api.calls[0][1]
    assert kwargs["timeMin"]  # defaulted to now(), just needs to be non-empty
    assert kwargs["timeMax"] > kwargs["timeMin"]


def test_create_event_builds_a_timed_event_body():
    api = FakeEventsAPI(insert_result=RAW_EVENT)
    event = calendar_tool.create_event(
        summary="Dentist",
        start="2026-09-24T15:00:00-07:00",
        end="2026-09-24T16:00:00-07:00",
        location="Main St",
        description="Annual checkup",
        service=FakeService(api),
    )

    assert event["id"] == "abc123"
    body = api.calls[0][1]["body"]
    assert body["start"] == {"dateTime": "2026-09-24T15:00:00-07:00"}
    assert body["end"] == {"dateTime": "2026-09-24T16:00:00-07:00"}
    assert body["summary"] == "Dentist"
    assert body["location"] == "Main St"


def test_create_event_builds_an_all_day_event_body():
    api = FakeEventsAPI(insert_result={"id": "x", "summary": "Birthday", "start": {"date": "2026-10-01"}, "end": {"date": "2026-10-02"}})
    calendar_tool.create_event(summary="Birthday", start="2026-10-01", end="2026-10-02", service=FakeService(api))

    body = api.calls[0][1]["body"]
    assert body["start"] == {"date": "2026-10-01"}
    assert body["end"] == {"date": "2026-10-02"}


def test_create_event_attaches_configured_timezone_to_naive_datetimes(monkeypatch):
    monkeypatch.setattr(config, "BRAIN_TIMEZONE", "America/New_York")
    api = FakeEventsAPI(insert_result=RAW_EVENT)
    calendar_tool.create_event(
        summary="Dentist", start="2026-09-24T15:00:00", end="2026-09-24T16:00:00", service=FakeService(api)
    )

    body = api.calls[0][1]["body"]
    assert body["start"] == {"dateTime": "2026-09-24T15:00:00", "timeZone": "America/New_York"}


def test_update_event_only_includes_provided_fields():
    api = FakeEventsAPI(patch_result=RAW_EVENT)
    calendar_tool.update_event("abc123", summary="Dentist (rescheduled)", service=FakeService(api))

    body = api.calls[0][1]["body"]
    assert body == {"summary": "Dentist (rescheduled)"}


def test_delete_event_calls_delete_with_the_event_id():
    api = FakeEventsAPI()
    calendar_tool.delete_event("abc123", service=FakeService(api))

    assert api.calls[0] == ("delete", {"calendarId": config.GOOGLE_CALENDAR_ID, "eventId": "abc123"})


def test_get_service_raises_a_clear_error_when_not_yet_authorized(monkeypatch, tmp_path):
    monkeypatch.setattr(config, "GOOGLE_CALENDAR_TOKEN_PATH", str(tmp_path / "no-such-token.json"))

    with pytest.raises(RuntimeError, match="gcal_auth.py"):
        calendar_tool.get_service()
