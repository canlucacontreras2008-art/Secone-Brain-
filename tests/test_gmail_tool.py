import base64

from app import gmail_tool


class FakeExecutable:
    def __init__(self, result):
        self.result = result

    def execute(self):
        return self.result


class FakeMessagesAPI:
    def __init__(self, list_result=None, get_results=None, send_result=None):
        self.list_result = list_result if list_result is not None else {"messages": []}
        self.get_results = get_results or {}
        self.send_result = send_result
        self.calls = []

    def list(self, **kwargs):
        self.calls.append(("list", kwargs))
        return FakeExecutable(self.list_result)

    def get(self, **kwargs):
        self.calls.append(("get", kwargs))
        return FakeExecutable(self.get_results[kwargs["id"]])

    def send(self, **kwargs):
        self.calls.append(("send", kwargs))
        return FakeExecutable(self.send_result)


class FakeDraftsAPI:
    def __init__(self, create_result=None):
        self.create_result = create_result
        self.calls = []

    def create(self, **kwargs):
        self.calls.append(("create", kwargs))
        return FakeExecutable(self.create_result)


class FakeUsersAPI:
    def __init__(self, messages_api, drafts_api):
        self._messages_api = messages_api
        self._drafts_api = drafts_api

    def messages(self):
        return self._messages_api

    def drafts(self):
        return self._drafts_api


class FakeService:
    def __init__(self, messages_api=None, drafts_api=None):
        self._users_api = FakeUsersAPI(messages_api or FakeMessagesAPI(), drafts_api or FakeDraftsAPI())

    def users(self):
        return self._users_api


def _b64(text: str) -> str:
    return base64.urlsafe_b64encode(text.encode("utf-8")).decode("ascii")


def test_list_messages_returns_summaries_with_metadata():
    messages_api = FakeMessagesAPI(
        list_result={"messages": [{"id": "m1"}]},
        get_results={
            "m1": {
                "id": "m1",
                "snippet": "Hi there",
                "payload": {"headers": [{"name": "Subject", "value": "Hello"}, {"name": "From", "value": "a@b.com"}]},
            }
        },
    )
    service = FakeService(messages_api=messages_api)

    messages = gmail_tool.list_messages(query="is:unread", service=service)

    assert messages == [{"id": "m1", "subject": "Hello", "from": "a@b.com", "date": "", "snippet": "Hi there"}]
    assert messages_api.calls[0] == ("list", {"userId": "me", "q": "is:unread", "maxResults": 10})


def test_list_messages_with_no_results_returns_empty_list():
    service = FakeService(messages_api=FakeMessagesAPI(list_result={}))

    assert gmail_tool.list_messages(service=service) == []


def test_get_message_extracts_plain_text_body_from_nested_parts():
    payload = {
        "headers": [
            {"name": "Subject", "value": "Hello"},
            {"name": "From", "value": "a@b.com"},
            {"name": "To", "value": "me@example.com"},
        ],
        "mimeType": "multipart/alternative",
        "parts": [
            {"mimeType": "text/plain", "body": {"data": _b64("Plain text body.")}},
            {"mimeType": "text/html", "body": {"data": _b64("<p>HTML body.</p>")}},
        ],
    }
    messages_api = FakeMessagesAPI(get_results={"m1": {"id": "m1", "snippet": "...", "payload": payload}})
    service = FakeService(messages_api=messages_api)

    msg = gmail_tool.get_message("m1", service=service)

    assert msg["subject"] == "Hello"
    assert msg["body"] == "Plain text body."
    assert messages_api.calls[0] == ("get", {"userId": "me", "id": "m1", "format": "full"})


def test_get_message_falls_back_to_snippet_when_no_plain_text_part():
    payload = {"headers": [], "mimeType": "text/html", "body": {"data": _b64("<p>only html</p>")}}
    messages_api = FakeMessagesAPI(get_results={"m1": {"id": "m1", "snippet": "fallback snippet", "payload": payload}})
    service = FakeService(messages_api=messages_api)

    msg = gmail_tool.get_message("m1", service=service)

    assert msg["body"] == "fallback snippet"


def test_send_message_builds_a_mime_message_and_sends_it():
    messages_api = FakeMessagesAPI(send_result={"id": "sent1"})
    service = FakeService(messages_api=messages_api)

    result = gmail_tool.send_message(to="a@b.com", subject="Hi", body="Hello there", service=service)

    assert result == {"id": "sent1", "to": "a@b.com", "subject": "Hi"}
    call_kwargs = messages_api.calls[0][1]
    assert call_kwargs["userId"] == "me"
    raw = base64.urlsafe_b64decode(call_kwargs["body"]["raw"].encode("ascii")).decode()
    assert "To: a@b.com" in raw
    assert "Subject: Hi" in raw
    assert "Hello there" in raw


def test_create_draft_does_not_send_anything():
    drafts_api = FakeDraftsAPI(create_result={"id": "draft1"})
    service = FakeService(drafts_api=drafts_api)

    result = gmail_tool.create_draft(to="a@b.com", subject="Hi", body="Hello there", service=service)

    assert result == {"id": "draft1", "to": "a@b.com", "subject": "Hi"}
    assert drafts_api.calls[0][0] == "create"
    assert "message" in drafts_api.calls[0][1]["body"]
