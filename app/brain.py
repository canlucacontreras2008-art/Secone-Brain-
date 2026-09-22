import json

import anthropic

from . import config, memory, tasks, tools

SYSTEM_PROMPT = """You are Secone, a self-improving AI assistant.

You have three abilities beyond a normal chat model:
1. `web_search` - look things up on the live internet when your own knowledge
   might be stale, wrong, or missing.
2. `remember` - save durable facts and lessons to your own long-term memory.
3. `recall` - search that memory for anything relevant to what you're doing now.

Use `remember` proactively: when you learn something true about the world via
web_search, when the user tells you something about themselves or their
preferences, or when you notice something that would help you do better next
time. Be specific and atomic - one fact or lesson per call.
"""


class Brain:
    def __init__(self) -> None:
        self.client = anthropic.Anthropic()

    def _relevant_memories_block(self, query: str) -> str:
        hits = memory.recall(query, limit=config.MEMORY_RECALL_LIMIT)
        if not hits:
            return ""
        lines = [f"- ({h['kind']}) {h['content']}" for h in hits]
        return "Relevant things you already know:\n" + "\n".join(lines)

    def _run_loop(self, messages: list, extra_system: str = "") -> str:
        system = SYSTEM_PROMPT + (f"\n\n{extra_system}" if extra_system else "")

        for _ in range(config.MAX_TOOL_ITERATIONS):
            response = self.client.messages.create(
                model=config.MODEL,
                max_tokens=4096,
                system=system,
                tools=tools.ALL_TOOLS,
                messages=messages,
            )

            if response.stop_reason == "pause_turn":
                # Server-tool turn paused mid-flight; resend as-is to continue it.
                messages.append({"role": "assistant", "content": response.content})
                continue

            tool_uses = [b for b in response.content if b.type == "tool_use"]
            if not tool_uses:
                return next((b.text for b in response.content if b.type == "text"), "")

            messages.append({"role": "assistant", "content": response.content})

            tool_results = []
            for block in tool_uses:
                try:
                    result = tools.execute_tool(block.name, block.input)
                    tool_results.append(
                        {"type": "tool_result", "tool_use_id": block.id, "content": result}
                    )
                except Exception as exc:  # surfaced to the model, not raised to the caller
                    tool_results.append(
                        {
                            "type": "tool_result",
                            "tool_use_id": block.id,
                            "content": f"Error: {exc}",
                            "is_error": True,
                        }
                    )
            messages.append({"role": "user", "content": tool_results})

        return "I hit my step limit on this turn - here's where I got to so far."

    def chat(self, user_message: str) -> str:
        memories_block = self._relevant_memories_block(user_message)
        messages = [{"role": "user", "content": user_message}]
        return self._run_loop(messages, extra_system=memories_block)

    def run_task(self, task_description: str) -> dict:
        memories_block = self._relevant_memories_block(task_description)
        task_system = (
            "You are executing a discrete task, not chatting. Work it end to end "
            "using your tools, then give a clear final report of what you did and "
            "the outcome."
        )
        extra_system = "\n\n".join(part for part in (memories_block, task_system) if part)

        messages = [{"role": "user", "content": task_description}]
        result = self._run_loop(messages, extra_system=extra_system)

        task_id = tasks.log_task(task_description, result)
        reflection = self._reflect(task_description, result, task_id=task_id)
        tasks.set_reflection(task_id, reflection)
        return {"task_id": task_id, "result": result, "reflection": reflection}

    def _reflect(self, task_description: str, result: str, task_id: int) -> str:
        """Self-improvement step: extract a durable lesson from how the task went
        and store it - linked back to the task - so future tasks of a similar
        shape benefit from it.

        Tags come from the model, not a fixed label - a fixed tag like
        "task-reflection" on every lesson would make all lessons look
        connected to each other regardless of topic, once memories are
        viewed as a graph.
        """
        prompt = (
            f"You just finished this task:\n{task_description}\n\n"
            f"Here is how it went:\n{result}\n\n"
            "What is the single most useful, general lesson to remember for "
            "next time you face a similar task? If there's genuinely nothing "
            "worth keeping, set lesson to null."
        )
        response = self.client.messages.create(
            model=config.MODEL,
            max_tokens=300,
            output_config={
                "effort": "low",
                "format": {
                    "type": "json_schema",
                    "schema": {
                        "type": "object",
                        "properties": {
                            "lesson": {"type": ["string", "null"]},
                            "tags": {
                                "type": "array",
                                "items": {"type": "string"},
                                "description": "2-4 short topical keywords for this lesson.",
                            },
                        },
                        "required": ["lesson", "tags"],
                        "additionalProperties": False,
                    },
                },
            },
            messages=[{"role": "user", "content": prompt}],
        )
        text = next((b.text for b in response.content if b.type == "text"), "{}")
        data = json.loads(text)
        lesson = (data.get("lesson") or "").strip()
        if lesson:
            memory.add_memory(
                kind="lesson",
                content=lesson,
                tags=data.get("tags") or [],
                source="task",
                task_id=task_id,
            )
        return lesson

    def learn(self, topic: str) -> dict:
        """Proactively research a topic on the internet and store what's learned."""
        prompt = (
            f"Research this topic on the web: {topic}\n\n"
            "Find several concrete, currently-true facts about it. For each fact "
            "you're confident in, call `remember` with kind=fact. Then give a short "
            "summary of what you found."
        )
        summary = self._run_loop([{"role": "user", "content": prompt}])
        return {"summary": summary, "recent_facts": memory.list_memories(kind="fact", limit=20)}
