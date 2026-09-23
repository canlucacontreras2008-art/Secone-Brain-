import json
from typing import List, Optional

import anthropic

from . import calendar_tool, config, memory, research_queue, task_queue, tasks, tools

SYSTEM_PROMPT = """You are Secone, a self-improving AI assistant.

You have six abilities beyond a normal chat model:
1. `web_search` - look things up on the live internet when your own knowledge
   might be stale, wrong, or missing.
2. `remember` - save durable facts and lessons to your own long-term memory.
3. `recall` - search that memory for anything relevant to what you're doing now.
4. `queue_for_learning` - queue a topic for later, deeper research when you
   notice a real gap in what you know.
5. Google Calendar tools (`calendar_list_events`, `calendar_create_event`,
   `calendar_update_event`, `calendar_delete_event`) - read and manage the
   user's real calendar.
6. Gmail tools (`gmail_list_messages`, `gmail_read_message`,
   `gmail_create_draft`, `gmail_send_message`) - search, read, draft, and
   send the user's real email.

Use `remember` proactively: when you learn something true about the world via
web_search, when the user tells you something about themselves or their
preferences, or when you notice something that would help you do better next
time. Be specific and atomic - one fact or lesson per call. Every memory
needs a `topic` - the general subject it's about. Reuse the exact same topic
string across multiple memories about the same subject (don't paraphrase it
differently each time); topic is what groups related memories together, so
inconsistent phrasing splits one real subject into several unrelated ones.
Every memory also needs a `category` - the broad grand-topic its topic
belongs under (e.g. "Mechanics", "Coding", "History"), picked from a fixed
list so several related topics cluster under one bigger category, one level
above individual topics.

Use `queue_for_learning` when the conversation touches a topic you genuinely
don't have enough confident knowledge about - not for every unfamiliar word,
just a real gap - so you can research it properly later instead of guessing
now. This doesn't replace answering the user as best you can in the moment;
it's in addition to that.

Only create, change, or delete a calendar event when the user has clearly
asked you to - never proactively, and never guess which existing event they
mean without checking `calendar_list_events` first. You're given the current
date and time below; resolve relative dates ("tomorrow", "next Tuesday")
against that before calling a calendar tool, rather than guessing.

Sending an email can't be undone once it's sent - use `gmail_send_message`
only when the user has explicitly said to send it (not just draft, write,
or reply to it). Whenever it's ambiguous whether they want it sent
immediately, use `gmail_create_draft` instead and let them review and send
it themselves.
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

    def _current_time_block(self) -> str:
        now = calendar_tool.now()
        return f"Current date and time: {now.strftime('%A, %Y-%m-%d %H:%M %Z').strip()} (RFC3339: {now.isoformat()})."

    def _run_loop(
        self,
        messages: list,
        extra_system: str = "",
        tool_list: Optional[list] = None,
        max_iterations: Optional[int] = None,
        default_topic: str = "",
    ) -> str:
        system = SYSTEM_PROMPT + (f"\n\n{extra_system}" if extra_system else "")
        active_tools = tools.ALL_TOOLS if tool_list is None else tool_list
        iterations = config.MAX_TOOL_ITERATIONS if max_iterations is None else max_iterations

        for _ in range(iterations):
            response = self.client.messages.create(
                model=config.MODEL,
                max_tokens=4096,
                system=system,
                tools=active_tools,
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
                    result = tools.execute_tool(block.name, block.input, default_topic=default_topic)
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
        extra_system = "\n\n".join(part for part in (self._current_time_block(), memories_block) if part)
        messages = [{"role": "user", "content": user_message}]
        return self._run_loop(messages, extra_system=extra_system)

    def run_task(self, task_description: str) -> dict:
        memories_block = self._relevant_memories_block(task_description)
        task_system = (
            "You are executing a discrete task, not chatting. Work it end to end "
            "using your tools, then give a clear final report of what you did and "
            "the outcome."
        )
        extra_system = "\n\n".join(
            part for part in (self._current_time_block(), memories_block, task_system) if part
        )

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

        Topic/tags come from the model, not a fixed label - a fixed tag like
        "task-reflection" on every lesson would make all lessons look
        connected to each other regardless of subject, once memories are
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
                            "topic": {
                                "type": "string",
                                "description": "The general subject this lesson is about.",
                            },
                            "category": {
                                "type": "string",
                                "enum": tools.CATEGORIES,
                                "description": "The broad grand-topic this lesson's topic belongs under.",
                            },
                            "tags": {
                                "type": "array",
                                "items": {"type": "string"},
                                "description": "2-4 short extra keywords for search.",
                            },
                        },
                        "required": ["lesson", "topic", "category", "tags"],
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
                topic=data.get("topic") or "",
                category=data.get("category") or "",
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
        # Force every fact's topic to the exact string the caller asked for,
        # rather than trusting the model to phrase it identically on every
        # `remember` call in this conversation.
        summary = self._run_loop([{"role": "user", "content": prompt}], default_topic=topic)
        return {"summary": summary, "recent_facts": memory.list_memories(kind="fact", limit=20)}

    def _scan_one_wikipedia_topic(self, topic: str) -> str:
        prompt = (
            f'Search Wikipedia for "{topic}", fetch the most relevant '
            "article, and read it. Call `remember` with kind=fact for "
            "each concrete, verifiable fact you find - names, dates, "
            "numbers, definitions, relationships. Aim for 8-15 facts if "
            "the article supports it. Tag every fact with 2-4 short extra "
            "search keywords."
        )
        return self._run_loop(
            [{"role": "user", "content": prompt}],
            tool_list=tools.WIKIPEDIA_TOOLS,
            # A full article can need search + fetch + ~15 individual
            # `remember` calls - the default iteration cap (tuned for
            # chat/task turns) cuts a thorough scan off before it can
            # give a closing summary, even though the facts up to that
            # point are still saved.
            max_iterations=20,
            # Force every fact from this article to the exact same topic
            # string - the caller's, not whatever phrasing the model might
            # drift into across many separate `remember` calls. This is what
            # keeps "Ada Lovelace" from splitting into several near-duplicate
            # topic globes just because the model varied its wording.
            default_topic=topic,
        )

    def scan_wikipedia(self, topics: List[str]) -> dict:
        """Learn from Wikipedia specifically: for each topic, search Wikipedia,
        fetch the most relevant article, and store concrete facts from it.

        Search and fetch are both domain-restricted to wikipedia.org
        (see tools.WIKIPEDIA_TOOLS) so this can't wander off onto the open web.
        """
        scanned = [{"topic": topic, "summary": self._scan_one_wikipedia_topic(topic)} for topic in topics]
        return {"scanned": scanned, "recent_facts": memory.list_memories(kind="fact", limit=30)}

    def run_research_queue(self, limit: Optional[int] = None) -> dict:
        """Work through the research queue: pop pending topics one at a time
        and Wikipedia-scan each. Persisted in SQLite (not just held in memory),
        so queuing a topic and actually running it can happen in separate
        requests - useful since a thorough scan can take a while.

        Checks the stop flag between topics (not mid-scan) - a click on
        "Stop" lets whatever topic is in flight finish, then halts before
        starting the next one, rather than aborting an Anthropic API call
        mid-conversation.
        """
        research_queue.clear_stop()
        processed = []
        count = 0
        stopped = False
        while limit is None or count < limit:
            if research_queue.stop_requested():
                stopped = True
                break
            item = research_queue.next_pending()
            if item is None:
                break
            research_queue.mark_running(item["id"])
            try:
                summary = self._scan_one_wikipedia_topic(item["topic"])
                research_queue.mark_done(item["id"], summary)
                processed.append({"id": item["id"], "topic": item["topic"], "status": "done", "summary": summary})
            except Exception as exc:  # keep the queue moving even if one topic fails
                research_queue.mark_error(item["id"], str(exc))
                processed.append({"id": item["id"], "topic": item["topic"], "status": "error", "error": str(exc)})
            count += 1

        return {
            "processed": processed,
            "remaining": len(research_queue.list_queue(status="pending")),
            "stopped": stopped,
        }

    def run_task_queue(self, limit: Optional[int] = None) -> dict:
        """Work through the task queue: pop pending task descriptions one at
        a time and run each end to end via run_task() (including its usual
        self-reflection). Persisted in SQLite, so queuing tasks and actually
        running them can happen in separate requests - same reasoning as
        run_research_queue.

        Checks the stop flag between tasks (not mid-task) - a click on
        "Stop" lets whatever task is in flight finish, then halts before
        starting the next one.
        """
        task_queue.clear_stop()
        processed = []
        count = 0
        stopped = False
        while limit is None or count < limit:
            if task_queue.stop_requested():
                stopped = True
                break
            item = task_queue.next_pending()
            if item is None:
                break
            task_queue.mark_running(item["id"])
            try:
                outcome = self.run_task(item["description"])
                task_queue.mark_done(item["id"], outcome["result"], outcome["task_id"])
                processed.append(
                    {
                        "id": item["id"],
                        "description": item["description"],
                        "status": "done",
                        "task_id": outcome["task_id"],
                        "result": outcome["result"],
                    }
                )
            except Exception as exc:  # keep the queue moving even if one task fails
                task_queue.mark_error(item["id"], str(exc))
                processed.append(
                    {"id": item["id"], "description": item["description"], "status": "error", "error": str(exc)}
                )
            count += 1

        return {
            "processed": processed,
            "remaining": len(task_queue.list_queue(status="pending")),
            "stopped": stopped,
        }
