# Secone Brain

An AI assistant that learns two ways: from the live internet (`web_search`)
and from its own experience doing tasks (self-reflection after every task,
stored as long-term memory it recalls on future work).

## How it thinks

- **`app/brain.py`** - the agentic loop. Every chat or task request runs
  Claude in a tool-use loop with three tools: `web_search` (a server-side
  tool, so it's real live internet access, not training data), `remember`,
  and `recall`.
- **`app/memory.py` + `app/db.py`** - long-term memory, backed by SQLite.
  Every memory is a `fact` (something true about the world or the user) or a
  `lesson` (something learned about how to do a task well). Recall is
  keyword-overlap search - no external vector DB or API key needed to get
  started; swap in embeddings later if recall quality becomes the bottleneck.
- **Self-improvement loop** - after every `/task` run, the brain asks itself
  "what's the one lesson worth keeping from that?" and stores the answer as a
  `lesson` memory. The next time it works on a similar task, that lesson gets
  pulled back into context automatically. `/learn` runs the same loop
  proactively: point it at a topic and it researches the web and stores what
  it finds as `fact` memories.

Nothing here is a black box: every fact and lesson the brain has stored is
visible and editable via `GET /memory` and `POST /memory`.

## Setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

cp .env.example .env
# edit .env and set ANTHROPIC_API_KEY (or run `ant auth login` and leave it unset)

uvicorn app.main:app --reload
```

## Endpoints

| Method | Path      | Body                          | What it does |
|--------|-----------|--------------------------------|---------------|
| POST   | `/chat`   | `{"message": "..."}`           | Chat turn. Can search the web and read/write memory. |
| POST   | `/task`   | `{"description": "..."}`       | Runs a task end-to-end, then reflects and stores a lesson. Returns `{result, reflection}`. |
| POST   | `/learn`  | `{"topic": "..."}`             | Proactively researches a topic on the web and stores facts. |
| GET    | `/memory` | `?kind=fact\|lesson&limit=100` | Lists stored memories. |
| POST   | `/memory` | `{"kind", "content", "tags"}`  | Manually add a memory. |
| GET    | `/health` | -                               | Liveness check. |

### Example

```bash
curl -X POST localhost:8000/task \
  -H 'content-type: application/json' \
  -d '{"description": "Find the current version of Python and summarize what changed in the latest release."}'

curl localhost:8000/memory?kind=lesson
```

## Tests

```bash
pytest
```

The memory-store tests run against a temp SQLite file and need no API key.
Exercising `Brain` itself needs `ANTHROPIC_API_KEY` since it calls the live
API - there's no mocked test for it here by design, to avoid a mock that
drifts from the real tool-use response shape.

## Extending it

- **Better recall** - `memory.recall()` is deliberately simple (token
  overlap). Swap it for embeddings + a vector index once the memory table
  grows large enough that keyword matching misses things.
- **Scheduled self-study** - call `Brain.learn(topic)` from a cron job to have
  the brain keep a running set of topics current on its own.
- **Task outcomes** - `run_task` doesn't know if a task actually succeeded
  from the user's perspective. Add a feedback field to `/task` (or a
  follow-up `/task/{id}/feedback` endpoint) and weight reflection on that.
