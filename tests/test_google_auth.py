import pytest

from app import config, google_auth


def test_get_credentials_raises_a_clear_error_when_not_yet_authorized(monkeypatch, tmp_path):
    monkeypatch.setattr(config, "GOOGLE_TOKEN_PATH", str(tmp_path / "no-such-token.json"))

    with pytest.raises(RuntimeError, match="google_auth.py"):
        google_auth.get_credentials()


def test_scopes_cover_both_calendar_and_gmail():
    assert google_auth.CALENDAR_SCOPE in google_auth.SCOPES
    assert google_auth.GMAIL_SCOPE in google_auth.SCOPES
