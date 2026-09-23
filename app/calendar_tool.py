"""Google Calendar access for the brain's calendar tools (see tools.py).

Auth is a one-time, out-of-band step: run `python scripts/gcal_auth.py`
once, interactively, to grant access and save a refresh token to
GOOGLE_CALENDAR_TOKEN_PATH. Everything here only ever reads and silently
refreshes that saved token - it never opens a browser itself, since a
server process (or a phone) has no interactive session to do that in.
"""

import os
from datetime import datetime, timedelta
from typing import List, Optional
from zoneinfo import ZoneInfo

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

from . import config

SCOPES = ["https://www.googleapis.com/auth/calendar"]


def timezone_name() -> Optional[str]:
    return config.BRAIN_TIMEZONE or None


def now() -> datetime:
    tz = timezone_name()
    return datetime.now(ZoneInfo(tz)) if tz else datetime.now().astimezone()


def get_service():
    token_path = config.GOOGLE_CALENDAR_TOKEN_PATH
    if not os.path.exists(token_path):
        raise RuntimeError(
            f"No Google Calendar token at {token_path} - run "
            "`python scripts/gcal_auth.py` once to connect your calendar "
            "(see README \"Calendar\" section)."
        )
    creds = Credentials.from_authorized_user_file(token_path, SCOPES)
    if creds.expired and creds.refresh_token:
        creds.refresh(Request())
        with open(token_path, "w") as f:
            f.write(creds.to_json())
    return build("calendar", "v3", credentials=creds)


def _time_dict(value: str) -> dict:
    """Google's event start/end shape: {"date": ...} for an all-day event
    (a plain "YYYY-MM-DD", no "T"), otherwise {"dateTime": ...}. A dateTime
    with no UTC offset needs an explicit timeZone alongside it - attach
    BRAIN_TIMEZONE when one's configured, as a defensive fallback for a
    naive timestamp slipping through despite being told the current time.
    """
    if "T" not in value:
        return {"date": value}
    d = {"dateTime": value}
    tz = timezone_name()
    if tz and "+" not in value[10:] and not value.endswith("Z"):
        d["timeZone"] = tz
    return d


def _simplify(event: dict) -> dict:
    return {
        "id": event.get("id", ""),
        "summary": event.get("summary", ""),
        "start": event.get("start", {}).get("dateTime") or event.get("start", {}).get("date", ""),
        "end": event.get("end", {}).get("dateTime") or event.get("end", {}).get("date", ""),
        "location": event.get("location", ""),
        "description": event.get("description", ""),
    }


def list_events(
    time_min: Optional[str] = None,
    time_max: Optional[str] = None,
    query: Optional[str] = None,
    max_results: int = 20,
    service=None,
) -> List[dict]:
    service = service or get_service()
    if time_min is None:
        time_min = now().isoformat()
    if time_max is None:
        time_max = (now() + timedelta(days=7)).isoformat()
    result = (
        service.events()
        .list(
            calendarId=config.GOOGLE_CALENDAR_ID,
            timeMin=time_min,
            timeMax=time_max,
            q=query,
            maxResults=max_results,
            singleEvents=True,
            orderBy="startTime",
        )
        .execute()
    )
    return [_simplify(e) for e in result.get("items", [])]


def create_event(
    summary: str,
    start: str,
    end: str,
    description: str = "",
    location: str = "",
    service=None,
) -> dict:
    service = service or get_service()
    body = {"summary": summary, "start": _time_dict(start), "end": _time_dict(end)}
    if description:
        body["description"] = description
    if location:
        body["location"] = location
    created = service.events().insert(calendarId=config.GOOGLE_CALENDAR_ID, body=body).execute()
    return _simplify(created)


def update_event(
    event_id: str,
    summary: Optional[str] = None,
    start: Optional[str] = None,
    end: Optional[str] = None,
    description: Optional[str] = None,
    location: Optional[str] = None,
    service=None,
) -> dict:
    service = service or get_service()
    body = {}
    if summary is not None:
        body["summary"] = summary
    if start is not None:
        body["start"] = _time_dict(start)
    if end is not None:
        body["end"] = _time_dict(end)
    if description is not None:
        body["description"] = description
    if location is not None:
        body["location"] = location
    updated = (
        service.events()
        .patch(calendarId=config.GOOGLE_CALENDAR_ID, eventId=event_id, body=body)
        .execute()
    )
    return _simplify(updated)


def delete_event(event_id: str, service=None) -> None:
    service = service or get_service()
    service.events().delete(calendarId=config.GOOGLE_CALENDAR_ID, eventId=event_id).execute()
