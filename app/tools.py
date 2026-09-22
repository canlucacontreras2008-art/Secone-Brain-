from . import memory

# Server tool - runs on Anthropic's infrastructure, no local execution needed.
WEB_SEARCH_TOOL = {
    "type": "web_search_20260209",
    "name": "web_search",
    "max_uses": 5,
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
            "tags": {
                "type": "array",
                "items": {"type": "string"},
                "description": "A few short keywords to help you find this again later.",
            },
        },
        "required": ["kind", "content", "tags"],
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


def execute_tool(name: str, tool_input: dict) -> str:
    """Dispatch a client-side tool call. Server tools (web_search) never reach here."""
    if name == "remember":
        memory.add_memory(
            kind=tool_input["kind"],
            content=tool_input["content"],
            tags=tool_input.get("tags", []),
            source="self",
        )
        return "Saved to memory."

    if name == "recall":
        hits = memory.recall(tool_input["query"])
        if not hits:
            return "No relevant memories found."
        return "\n".join(f"- ({h['kind']}) {h['content']}" for h in hits)

    raise ValueError(f"Unknown client tool: {name}")
