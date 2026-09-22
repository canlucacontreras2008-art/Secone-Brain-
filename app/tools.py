from . import memory

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
            "tags": {
                "type": "array",
                "items": {"type": "string"},
                "description": (
                    "A few extra short keywords for search - not used for grouping, "
                    "just to help find this again later."
                ),
            },
        },
        "required": ["kind", "content", "topic", "tags"],
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

ALL_TOOLS = [WEB_SEARCH_TOOL, REMEMBER_TOOL, RECALL_TOOL]
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
            source="self",
        )
        return "Saved to memory."

    if name == "recall":
        hits = memory.recall(tool_input["query"])
        if not hits:
            return "No relevant memories found."
        return "\n".join(f"- ({h['kind']}) {h['content']}" for h in hits)

    raise ValueError(f"Unknown client tool: {name}")
