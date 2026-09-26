import urllib.error

import pytest

from app import config, phone_timer


def test_set_timer_requires_webhook_url_configured(monkeypatch):
    monkeypatch.setattr(config, "MACRODROID_WEBHOOK_URL", "")

    with pytest.raises(RuntimeError, match="MACRODROID_WEBHOOK_URL"):
        phone_timer.set_timer(minutes=5)


def test_set_timer_calls_the_webhook_with_seconds_and_label(monkeypatch):
    monkeypatch.setattr(config, "MACRODROID_WEBHOOK_URL", "https://trigger.macrodroid.com/abc/def")
    captured = {}

    class FakeResponse:
        def read(self):
            return b""

    def fake_urlopen(url, timeout=None):
        captured["url"] = url
        captured["timeout"] = timeout
        return FakeResponse()

    monkeypatch.setattr(phone_timer.urllib.request, "urlopen", fake_urlopen)

    result = phone_timer.set_timer(minutes=2.5, label="Pasta")

    assert result == {"minutes": 2.5, "label": "Pasta"}
    assert captured["url"].startswith("https://trigger.macrodroid.com/abc/def?")
    assert "timer_seconds=150" in captured["url"]
    assert "timer_label=Pasta" in captured["url"]


def test_set_timer_wraps_unreachable_webhook_as_runtime_error(monkeypatch):
    monkeypatch.setattr(config, "MACRODROID_WEBHOOK_URL", "https://trigger.macrodroid.com/abc/def")

    def fake_urlopen(url, timeout=None):
        raise urllib.error.URLError("no route to host")

    monkeypatch.setattr(phone_timer.urllib.request, "urlopen", fake_urlopen)

    with pytest.raises(RuntimeError, match="Could not reach the MacroDroid webhook"):
        phone_timer.set_timer(minutes=5)
