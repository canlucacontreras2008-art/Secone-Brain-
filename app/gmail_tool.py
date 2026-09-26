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


_REPLY_HEADERS = ["Subject", "From", "To", "Reply-To", "Message-ID", "References"]


def _thread_and_headers(message_id: str, service) -> tuple:
    msg = (
        service.users()
        .messages()
        .get(userId="me", id=message_id, format="metadata", metadataHeaders=_REPLY_HEADERS)
        .execute()
    )
    return msg.get("threadId", ""), _headers_of(msg)


def _reply_subject(original_subject: str) -> str:
    return original_subject if original_subject.lower().startswith("re:") else f"Re: {original_subject}"


def _build_reply_raw_message(headers: dict, body: str, thread_id: str, cc: str = "") -> dict:
    message = MIMEText(body)
    message["To"] = headers.get("Reply-To") or headers.get("From", "")
    message["Subject"] = _reply_subject(headers.get("Subject", ""))
    if cc:
        message["Cc"] = cc
    in_reply_to = headers.get("Message-ID", "")
    if in_reply_to:
        # These two headers are what makes a mail client (and Gmail's own
        # UI) show this as part of the original conversation instead of an
        # unrelated new email - threadId alone isn't enough for clients
        # that thread by header rather than by Gmail's own thread id.
        message["In-Reply-To"] = in_reply_to
        references = headers.get("References", "")
        message["References"] = f"{references} {in_reply_to}".strip()
    raw = {"raw": base64.urlsafe_b64encode(message.as_bytes()).decode("ascii")}
    if thread_id:
        raw["threadId"] = thread_id
    return raw


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


def reply_message(message_id: str, body: str, cc: str = "", service=None) -> dict:
    """Reply within the same Gmail thread as an existing message, instead of
    gmail_send_message's brand-new, unrelated email."""
    service = service or get_service()
    thread_id, headers = _thread_and_headers(message_id, service)
    raw = _build_reply_raw_message(headers, body, thread_id, cc)
    sent = service.users().messages().send(userId="me", body=raw).execute()
    to = headers.get("Reply-To") or headers.get("From", "")
    return {"id": sent.get("id", ""), "to": to, "subject": _reply_subject(headers.get("Subject", ""))}


def create_reply_draft(message_id: str, body: str, cc: str = "", service=None) -> dict:
    service = service or get_service()
    thread_id, headers = _thread_and_headers(message_id, service)
    raw = _build_reply_raw_message(headers, body, thread_id, cc)
    draft = service.users().drafts().create(userId="me", body={"message": raw}).execute()
    to = headers.get("Reply-To") or headers.get("From", "")
    return {"id": draft.get("id", ""), "to": to, "subject": _reply_subject(headers.get("Subject", ""))}
