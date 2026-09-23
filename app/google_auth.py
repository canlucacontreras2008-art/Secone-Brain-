"""Shared Google OAuth plumbing for Calendar and Gmail.

Both features are granted through one OAuth app and one consent flow -
scripts/google_auth.py, run once, interactively, to save GOOGLE_TOKEN_PATH -
rather than making the user click through Google's consent screen twice for
two separate tokens. Everything here only ever reads and silently refreshes
that saved token; it never opens a browser itself, since a server process
has no interactive session to do that in.
"""

import os

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

from . import config

CALENDAR_SCOPE = "https://www.googleapis.com/auth/calendar"
GMAIL_SCOPE = "https://www.googleapis.com/auth/gmail.modify"
SCOPES = [CALENDAR_SCOPE, GMAIL_SCOPE]


def get_credentials() -> Credentials:
    token_path = config.GOOGLE_TOKEN_PATH
    if not os.path.exists(token_path):
        raise RuntimeError(
            f"No Google token at {token_path} - run `python scripts/google_auth.py` "
            "once to connect your Google account (see README)."
        )
    creds = Credentials.from_authorized_user_file(token_path, SCOPES)
    if creds.expired and creds.refresh_token:
        creds.refresh(Request())
        with open(token_path, "w") as f:
            f.write(creds.to_json())
    return creds


def get_service(api_name: str, api_version: str):
    return build(api_name, api_version, credentials=get_credentials())
