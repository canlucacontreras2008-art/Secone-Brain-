from . import calendar_tool, gmail_tool, memory, phone_timer, research_queue

# Server tools - run on Anthropic's infrastructure, no local execution needed.
WEB_SEARCH_TOOL = {
    "type": "web_search_20260209",
    "name": "web_search",
    "max_uses": 5,
}

# Wikipedia-scoped variants for the /wikipedia/scan endpoint: allowed_domains
# means these can't wander off Wikipedia even if the model tries to.
WIKIPEDIA_SEARCH_TOOL = {
    "type": "web_search_20260209",
    "name": "web_search",
    "max_uses": 3,
    "allowed_domains": ["en.wikipedia.org", "wikipedia.org"],
}

WIKIPEDIA_FETCH_TOOL = {
    "type": "web_fetch_20260209",
    "name": "web_fetch",
    "max_uses": 5,
    "allowed_domains": ["en.wikipedia.org", "wikipedia.org"],
}

# A fixed, closed vocabulary rather than a freeform string - same fix as the
# `topic` field, one level up: an open-ended category label would drift
# ("Coding" vs "Programming" vs "Computer science") and split one real
# grand-topic into several category globes. Add to this list to support a
# new grand topic; existing memories keep their category either way.
CATEGORIES = [
    "Mechanics",
    "Coding",
    "History",
    "Science",
    "Mathematics",
    "Biology",
    "Geography",
    "Art & Culture",
    "Philosophy",
    "Economics",
    "General",
]

REMEMBER_TOOL = {
    "name": "remember",
    "description": (
        "Save a fact or a lesson you have learned to long-term memory, so you can "
        "recall it in future conversations and tasks. Use this whenever you learn "
        "something durable: a fact from the web, something the user told you about "
        "themselves, or a lesson about how a task went. One fact or lesson per call."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "kind": {"type": "string", "enum": ["fact", "lesson"]},
            "content": {"type": "string"},
            "topic": {
                "type": "string",
                "description": (
                    "The general subject this memory is about, in a short, "
                    "consistent form (e.g. \"Ada Lovelace\", \"Classical mechanics\"). "
                    "This is the authoritative grouping key - reuse the exact same "
                    "string across every memory about the same subject so they "
                    "cluster together, rather than inventing a slightly different "
                    "phrasing each time."
                ),
            },
            "category": {
                "type": "string",
                "enum": CATEGORIES,
                "description": (
                    "The broad grand-topic this memory's `topic` belongs under. Pick "
                    "the closest match from this fixed list rather than inventing a "
                    "new label, so e.g. \"Gear\" and \"Newton's laws of motion\" - two "
                    "different topics - both land under \"Mechanics\" and cluster "
                    "into the same category globe."
                ),
            },
            "tags": {
                "type": "array",
                "items": {"type": "string"},
                "description": (
                    "A few extra short keywords for search - not used for grouping, "
                    "just to help find this again later."
                ),
            },
        },
        "required": ["kind", "content", "topic", "category", "tags"],
        "additionalProperties": False,
    },
}

RECALL_TOOL = {
    "name": "recall",
    "description": "Search your long-term memory for facts and lessons relevant to a query.",
    "input_schema": {
        "type": "object",
        "properties": {
            "query": {"type": "string"},
        },
        "required": ["query"],
        "additionalProperties": False,
    },
}

QUEUE_LEARNING_TOOL = {
    "name": "queue_for_learning",
    "description": (
        "Queue a topic for the brain to research later (a Wikipedia scan, run from "
        "the research queue) when you don't have enough confident knowledge to "
        "answer well. Use this when you notice a real, specific gap in what you "
        "know - not on every message, only when the conversation genuinely touches "
        "something you don't know enough about - so the brain can fill that gap "
        "before it comes up again, rather than guessing or making something up now."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "topic": {
                "type": "string",
                "description": (
                    "The specific subject to research, phrased the way you'd search "
                    "for it (e.g. \"Quantum entanglement\")."
                ),
            },
        },
        "required": ["topic"],
        "additionalProperties": False,
    },
}

CALENDAR_LIST_EVENTS_TOOL = {
    "name": "calendar_list_events",
    "description": (
        "List events on the user's Google Calendar in a time range - use this "
        "to answer questions about their schedule (e.g. \"what do I have "
        "tomorrow\", \"am I free Friday afternoon\"). You're given the current "
        "date and time in context; resolve relative dates against that before "
        "calling this."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "time_min": {
                "type": "string",
                "description": "RFC3339 start of the range, e.g. \"2026-09-24T00:00:00-07:00\". Omit for now.",
            },
            "time_max": {
                "type": "string",
                "description": "RFC3339 end of the range. Omit for 7 days after time_min.",
            },
            "query": {
                "type": "string",
                "description": "Optional free-text filter on event title/description.",
            },
        },
        "required": [],
        "additionalProperties": False,
    },
}

CALENDAR_CREATE_EVENT_TOOL = {
    "name": "calendar_create_event",
    "description": (
        "Create a new event on the user's Google Calendar. Only do this when "
        "the user has clearly asked you to schedule or add something - never "
        "proactively. Resolve relative dates (\"tomorrow\", \"next Tuesday\") "
        "against the current date/time given in context into an actual "
        "RFC3339 timestamp before calling this."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "summary": {"type": "string", "description": "The event's title."},
            "start": {
                "type": "string",
                "description": (
                    "RFC3339 datetime (e.g. \"2026-09-24T15:00:00-07:00\"), or a "
                    "plain date (\"2026-09-24\") for an all-day event."
                ),
            },
            "end": {"type": "string", "description": "Same format as start."},
            "description": {"type": "string", "description": "Optional longer notes."},
            "location": {"type": "string", "description": "Optional location."},
            "recurrence": {
                "type": "array",
                "items": {"type": "string"},
                "description": (
                    "Optional RFC5545 recurrence rules to make this a repeating "
                    "event, e.g. [\"RRULE:FREQ=WEEKLY;BYDAY=MO;COUNT=10\"] for "
                    "every Monday, 10 times, or "
                    "[\"RRULE:FREQ=DAILY;UNTIL=20261231T000000Z\"] for daily "
                    "until a date. Omit for a one-time event."
                ),
            },
        },
        "required": ["summary", "start", "end"],
        "additionalProperties": False,
    },
}

CALENDAR_UPDATE_EVENT_TOOL = {
    "name": "calendar_update_event",
    "description": (
        "Update an existing event on the user's Google Calendar - only the "
        "fields you provide are changed. Find the event_id first via "
        "calendar_list_events. Only do this when the user has clearly asked "
        "you to change something."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "event_id": {"type": "string"},
            "summary": {"type": "string"},
            "start": {"type": "string", "description": "RFC3339 datetime, or a plain date for an all-day event."},
            "end": {"type": "string", "description": "Same format as start."},
            "description": {"type": "string"},
            "location": {"type": "string"},
            "recurrence": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Replace the event's RFC5545 recurrence rules. Same format as calendar_create_event.",
            },
        },
        "required": ["event_id"],
        "additionalProperties": False,
    },
}

CALENDAR_DELETE_EVENT_TOOL = {
    "name": "calendar_delete_event",
    "description": (
        "Delete/cancel an event on the user's Google Calendar. Find the "
        "event_id first via calendar_list_events. Only do this when the user "
        "has clearly asked you to cancel or remove something - it can't be "
        "undone from here."
    ),
    "input_schema": {
        "type": "object",
        "properties": {"event_id": {"type": "string"}},
        "required": ["event_id"],
        "additionalProperties": False,
    },
}

GMAIL_LIST_MESSAGES_TOOL = {
    "name": "gmail_list_messages",
    "description": (
        "Search/list the user's Gmail messages. Use Gmail's own search syntax "
        "in `query` (e.g. \"is:unread\", \"from:someone@example.com\", "
        "\"subject:invoice\"). Omit query to list the most recent messages."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "query": {"type": "string", "description": "Gmail search query. Optional."},
            "max_results": {"type": "integer", "description": "Defaults to 10."},
        },
        "required": [],
        "additionalProperties": False,
    },
}

GMAIL_READ_MESSAGE_TOOL = {
    "name": "gmail_read_message",
    "description": "Read the full content of one Gmail message by id (from gmail_list_messages).",
    "input_schema": {
        "type": "object",
        "properties": {"message_id": {"type": "string"}},
        "required": ["message_id"],
        "additionalProperties": False,
    },
}

GMAIL_CREATE_DRAFT_TOOL = {
    "name": "gmail_create_draft",
    "description": (
        "Create a draft email in the user's Gmail - saved for them to review "
        "and send themselves, nothing is sent yet. Prefer this over "
        "gmail_send_message whenever there's any doubt about whether the "
        "user wants it sent immediately."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "to": {"type": "string", "description": "Recipient email address."},
            "subject": {"type": "string"},
            "body": {"type": "string"},
            "cc": {"type": "string", "description": "Optional CC address(es), comma-separated."},
        },
        "required": ["to", "subject", "body"],
        "additionalProperties": False,
    },
}

GMAIL_SEND_MESSAGE_TOOL = {
    "name": "gmail_send_message",
    "description": (
        "Immediately send an email from the user's Gmail account - this "
        "cannot be undone once sent. Only call this when the user has "
        "explicitly said to send it (not just draft, write, or prepare an "
        "email) - if there's any doubt, use gmail_create_draft instead and "
        "let the user review and send it themselves."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "to": {"type": "string"},
            "subject": {"type": "string"},
            "body": {"type": "string"},
            "cc": {"type": "string", "description": "Optional CC address(es), comma-separated."},
        },
        "required": ["to", "subject", "body"],
        "additionalProperties": False,
    },
}

GMAIL_REPLY_MESSAGE_TOOL = {
    "name": "gmail_reply_message",
    "description": (
        "Immediately send a reply within the same Gmail thread as an "
        "existing message (found via gmail_list_messages/gmail_read_message) "
        "- this cannot be undone once sent. Prefer this over "
        "gmail_send_message when replying to something specific, since it "
        "threads correctly instead of showing up as an unrelated new email. "
        "Only call this when the user has explicitly said to send the "
        "reply - if there's any doubt, use gmail_create_reply_draft instead."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "message_id": {"type": "string", "description": "The message being replied to."},
            "body": {"type": "string"},
            "cc": {"type": "string", "description": "Optional CC address(es), comma-separated."},
        },
        "required": ["message_id", "body"],
        "additionalProperties": False,
    },
}

PHONE_SET_TIMER_TOOL = {
    "name": "phone_set_timer",
    "description": (
        "Set a real timer on the user's Android phone (via a MacroDroid "
        "webhook, see README 'Phone timer'). Only do this when the user has "
        "clearly asked for a timer/reminder of a specific duration - never "
        "proactively."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "minutes": {"type": "number", "description": "How long the timer should run, in minutes."},
            "label": {"type": "string", "description": "Optional label shown on the timer, e.g. \"Pasta\"."},
        },
        "required": ["minutes"],
        "additionalProperties": False,
    },
}

GMAIL_CREATE_REPLY_DRAFT_TOOL = {
    "name": "gmail_create_reply_draft",
    "description": (
        "Create a reply draft within the same Gmail thread as an existing "
        "message - saved for the user to review and send themselves, "
        "nothing is sent yet."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "message_id": {"type": "string", "description": "The message being replied to."},
            "body": {"type": "string"},
            "cc": {"type": "string", "description": "Optional CC address(es), comma-separated."},
        },
        "required": ["message_id", "body"],
        "additionalProperties": False,
    },
}

# Not included in WIKIPEDIA_TOOLS - a scan already IS the research, so letting
# it queue more research on itself risks a self-referential spiral. Calendar
# and Gmail tools aren't relevant to a Wikipedia scan either.
ALL_TOOLS = [
    WEB_SEARCH_TOOL,
    REMEMBER_TOOL,
    RECALL_TOOL,
    QUEUE_LEARNING_TOOL,
    CALENDAR_LIST_EVENTS_TOOL,
    CALENDAR_CREATE_EVENT_TOOL,
    CALENDAR_UPDATE_EVENT_TOOL,
    CALENDAR_DELETE_EVENT_TOOL,
    GMAIL_LIST_MESSAGES_TOOL,
    GMAIL_READ_MESSAGE_TOOL,
    GMAIL_CREATE_DRAFT_TOOL,
    GMAIL_SEND_MESSAGE_TOOL,
    GMAIL_REPLY_MESSAGE_TOOL,
    GMAIL_CREATE_REPLY_DRAFT_TOOL,
    PHONE_SET_TIMER_TOOL,
]
WIKIPEDIA_TOOLS = [WIKIPEDIA_SEARCH_TOOL, WIKIPEDIA_FETCH_TOOL, REMEMBER_TOOL]


def execute_tool(name: str, tool_input: dict, default_topic: str = "") -> str:
    """Dispatch a client-side tool call. Server tools (web_search) never reach here.

    default_topic, when set, overrides whatever topic the model chose - used by
    a Wikipedia scan to force every fact from one article to the exact same
    topic string, rather than trusting the model to phrase it identically
    across many separate tool calls in the same conversation.
    """
    if name == "remember":
        memory.add_memory(
            kind=tool_input["kind"],
            content=tool_input["content"],
            tags=tool_input.get("tags", []),
            topic=default_topic or tool_input.get("topic", ""),
            category=tool_input.get("category", ""),
            source="self",
        )
        return "Saved to memory."

    if name == "recall":
        hits = memory.recall(tool_input["query"])
        if not hits:
            return "No relevant memories found."
        return "\n".join(f"- ({h['kind']}) {h['content']}" for h in hits)

    if name == "queue_for_learning":
        topic = tool_input["topic"]
        research_queue.enqueue([topic])
        return f'Queued "{topic}" for learning.'

    if name == "calendar_list_events":
        events = calendar_tool.list_events(
            time_min=tool_input.get("time_min"),
            time_max=tool_input.get("time_max"),
            query=tool_input.get("query"),
        )
        if not events:
            return "No events found in that range."
        lines = []
        for e in events:
            line = f"- [{e['id']}] {e['summary']}: {e['start']} to {e['end']}"
            if e["location"]:
                line += f" @ {e['location']}"
            lines.append(line)
        return "\n".join(lines)

    if name == "calendar_create_event":
        event = calendar_tool.create_event(
            summary=tool_input["summary"],
            start=tool_input["start"],
            end=tool_input["end"],
            description=tool_input.get("description", ""),
            location=tool_input.get("location", ""),
            recurrence=tool_input.get("recurrence"),
        )
        return f"Created event [{event['id']}] \"{event['summary']}\" from {event['start']} to {event['end']}."

    if name == "calendar_update_event":
        fields = {k: v for k, v in tool_input.items() if k != "event_id"}
        event = calendar_tool.update_event(tool_input["event_id"], **fields)
        return f"Updated event [{event['id']}] \"{event['summary']}\"."

    if name == "calendar_delete_event":
        calendar_tool.delete_event(tool_input["event_id"])
        return f"Deleted event {tool_input['event_id']}."

    if name == "gmail_list_messages":
        kwargs = {"query": tool_input.get("query")}
        if "max_results" in tool_input:
            kwargs["max_results"] = tool_input["max_results"]
        messages = gmail_tool.list_messages(**kwargs)
        if not messages:
            return "No messages found."
        return "\n".join(
            f"- [{m['id']}] {m['subject']} - from {m['from']} ({m['date']}): {m['snippet']}"
            for m in messages
        )

    if name == "gmail_read_message":
        msg = gmail_tool.get_message(tool_input["message_id"])
        return (
            f"From: {msg['from']}\nTo: {msg['to']}\nDate: {msg['date']}\n"
            f"Subject: {msg['subject']}\n\n{msg['body']}"
        )

    if name == "gmail_create_draft":
        draft = gmail_tool.create_draft(
            to=tool_input["to"],
            subject=tool_input["subject"],
            body=tool_input["body"],
            cc=tool_input.get("cc", ""),
        )
        return f"Created draft [{draft['id']}] to {draft['to']}: \"{draft['subject']}\"."

    if name == "gmail_send_message":
        sent = gmail_tool.send_message(
            to=tool_input["to"],
            subject=tool_input["subject"],
            body=tool_input["body"],
            cc=tool_input.get("cc", ""),
        )
        return f"Sent message [{sent['id']}] to {sent['to']}: \"{sent['subject']}\"."

    if name == "gmail_reply_message":
        sent = gmail_tool.reply_message(
            message_id=tool_input["message_id"],
            body=tool_input["body"],
            cc=tool_input.get("cc", ""),
        )
        return f"Sent reply [{sent['id']}] to {sent['to']}: \"{sent['subject']}\"."

    if name == "gmail_create_reply_draft":
        draft = gmail_tool.create_reply_draft(
            message_id=tool_input["message_id"],
            body=tool_input["body"],
            cc=tool_input.get("cc", ""),
        )
        return f"Created reply draft [{draft['id']}] to {draft['to']}: \"{draft['subject']}\"."

    if name == "phone_set_timer":
        result = phone_timer.set_timer(minutes=tool_input["minutes"], label=tool_input.get("label", ""))
        label_part = f' "{result["label"]}"' if result["label"] else ""
        return f"Set a {result['minutes']}-minute timer{label_part} on your phone."

    raise ValueError(f"Unknown client tool: {name}")
