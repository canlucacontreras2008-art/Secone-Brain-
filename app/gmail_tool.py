"""Gmail access for the brain's Gmail tools (see tools.py).

Auth is shared with Calendar - see app/google_auth.py.
"""

import base64
from email.mime.text import MIMEText
from typing import List, Optional

from . import google_auth


def get_service():
    return google_auth.get_service("gmail", "v1")


def _decode_body(data: str) -> str:
    return base64.urlsafe_b64decode(data.encode("ascii")).decode("utf-8", errors="replace")


def _extract_plain_text(payload: dict) -> str:
    if payload.get("mimeType") == "text/plain" and payload.get("body", {}).get("data"):
        return _decode_body(payload["body"]["data"])
    for part in payload.get("parts", []) or []:
        text = _extract_plain_text(part)
        if text:
            return text
    return ""


def _headers_of(message: dict) -> dict:
    return {h["name"]: h["value"] for h in message.get("payload", {}).get("headers", [])}


def _build_raw_message(to: str, subject: str, body: str, cc: str = "") -> dict:
    message = MIMEText(body)
    message["To"] = to
    message["Subject"] = subject
    if cc:
        message["Cc"] = cc
    return {"raw": base64.urlsafe_b64encode(message.as_bytes()).decode("ascii")}


def list_messages(query: Optional[str] = None, max_results: int = 10, service=None) -> List[dict]:
    service = service or get_service()
    result = service.users().messages().list(userId="me", q=query, maxResults=max_results).execute()
    summaries = []
    for item in result.get("messages", []):
        msg = (
            service.users()
            .messages()
            .get(userId="me", id=item["id"], format="metadata", metadataHeaders=["Subject", "From", "Date"])
            .execute()
        )
        headers = _headers_of(msg)
        summaries.append(
            {
                "id": item["id"],
                "subject": headers.get("Subject", ""),
                "from": headers.get("From", ""),
                "date": headers.get("Date", ""),
                "snippet": msg.get("snippet", ""),
            }
        )
    return summaries


def get_message(message_id: str, service=None) -> dict:
    service = service or get_service()
    msg = service.users().messages().get(userId="me", id=message_id, format="full").execute()
    headers = _headers_of(msg)
    body = _extract_plain_text(msg.get("payload", {})) or msg.get("snippet", "")
    return {
        "id": message_id,
        "subject": headers.get("Subject", ""),
        "from": headers.get("From", ""),
        "to": headers.get("To", ""),
        "date": headers.get("Date", ""),
        "body": body,
    }


def send_message(to: str, subject: str, body: str, cc: str = "", service=None) -> dict:
    service = service or get_service()
    sent = service.users().messages().send(userId="me", body=_build_raw_message(to, subject, body, cc)).execute()
    return {"id": sent.get("id", ""), "to": to, "subject": subject}


def create_draft(to: str, subject: str, body: str, cc: str = "", service=None) -> dict:
    service = service or get_service()
    draft = (
        service.users()
        .drafts()
        .create(userId="me", body={"message": _build_raw_message(to, subject, body, cc)})
        .execute()
    )
    return {"id": draft.get("id", ""), "to": to, "subject": subject}
