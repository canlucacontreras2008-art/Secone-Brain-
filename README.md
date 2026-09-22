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
- **`/wikipedia/scan`** - a Wikipedia-focused version of `/learn`: for each
  topic it searches Wikipedia, fetches the actual article, and extracts
  concrete facts from it. Both the search and fetch tools are domain-locked
  to `wikipedia.org` (see `tools.WIKIPEDIA_TOOLS`), so this can't wander off
  onto the open web even if the model tries to.
- **Research queue** (`/queue`) - a persisted, durable to-do list of topics
  to Wikipedia-scan, backed by SQLite (`app/research_queue.py`). Queuing a
  topic and actually running the scan are separate steps/requests - useful
  because a thorough scan can take a while, so you can queue up a batch of
  topics now and work through them (`/queue/run`) at your own pace, without
  one giant blocking request.

Nothing here is a black box: every fact and lesson the brain has stored is
visible and editable via `GET /memory` and `POST /memory` - or visually, as a
graph, at `/graph`.

## Memory graph (`/graph`)

A 3D view of everything the brain knows, as a small solar system: a glowing
golden holographic core in the center - a dense wireframe sphere (layered
latitude/longitude lines, scattered short "circuit trace" arcs, twinkling
points, a couple of tilted frame rings) rather than a plain ball - orbited
by one small "topic globe" per branch (the connected component a group of
memories belongs to, computed from real relationships: a task links to the
lesson it produced, and memories link when they share a tag), each tinted
in that branch's color. That branch's own memories then orbit *their*
topic globe rather than the main one - a hierarchy, not a flat shell -
and every level of it drifts continuously on its own, independent of
camera control. Lessons are green and tasks are blue at every level;
facts pick up their branch's color.

Drag to rotate, scroll to zoom, hover a memory for its label, click one for
the full detail panel. Search highlights matching memories and dims the
rest; the legend toggles a kind on/off. Names stay hidden until you hover,
select, or search for them, so the default view stays a clean, ambient
scene rather than a wall of text.

It's a single self-contained page (`app/static/graph.html`) - a hand-rolled
3D projection (rotate, perspective-project, painter's-algorithm depth sort)
on a plain `<canvas>`, no Three.js/WebGL/D3 or other JS dependency, so the
feature works offline and has nothing to vendor or build. Layout is
deterministic (seeded per node ID), so the same data settles into the same
positions across reloads - only the live auto-rotate animates.

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

| Method | Path         | Body                          | What it does |
|--------|--------------|--------------------------------|---------------|
| POST   | `/chat`      | `{"message": "..."}`           | Chat turn. Can search the web and read/write memory. |
| POST   | `/task`      | `{"description": "..."}`       | Runs a task end-to-end, then reflects and stores a lesson. Returns `{task_id, result, reflection}`. |
| POST   | `/learn`     | `{"topic": "..."}`             | Proactively researches a topic on the web and stores facts. |
| POST   | `/wikipedia/scan` | `{"topics": ["...", "..."]}` | Scans each topic on Wikipedia specifically and stores facts. |
| POST   | `/queue`     | `{"topics": ["...", "..."]}`   | Adds topics to the research queue (status `pending`). |
| GET    | `/queue`     | `?status=pending\|running\|done\|error` | Lists queue items and their status. |
| POST   | `/queue/run` | `?limit=N` (optional)          | Works through pending queue items via `/wikipedia/scan`'s logic. Omit `limit` to drain the whole queue. |
| GET    | `/memory`    | `?kind=fact\|lesson&limit=100` | Lists stored memories. |
| POST   | `/memory`    | `{"kind", "content", "tags"}`  | Manually add a memory. |
| GET    | `/graph`     | -                               | The memory graph UI (open in a browser). |
| GET    | `/graph/data`| -                               | `{nodes, edges}` JSON backing the graph UI. |
| GET    | `/health`    | -                               | Liveness check. |

### Example

```bash
curl -X POST localhost:8000/task \
  -H 'content-type: application/json' \
  -d '{"description": "Find the current version of Python and summarize what changed in the latest release."}'

curl -X POST localhost:8000/wikipedia/scan \
  -H 'content-type: application/json' \
  -d '{"topics": ["Quantum computing", "Ada Lovelace"]}'

# Queue a batch of coding + mechanics topics, then work through them
curl -X POST localhost:8000/queue \
  -H 'content-type: application/json' \
  -d '{"topics": ["Algorithm", "Data structure", "Object-oriented programming", "Version control", "Compiler", "Software design pattern", "Machine learning", "Classical mechanics", "Newton'"'"'s laws of motion", "Mechanical engineering", "Simple machine", "Kinematics", "Thermodynamics", "Fluid mechanics", "Gear"]}'

curl localhost:8000/queue?status=pending

# Process a few at a time (each scan can take a minute or two) - omit ?limit to drain the whole queue
curl -X POST "localhost:8000/queue/run?limit=3"

curl localhost:8000/memory?kind=lesson
```

## Tests

```bash
pytest
```

The memory, graph, and reflection-parsing tests run against a temp SQLite
file (or a stub Anthropic client for `_reflect`) and need no API key.
Exercising the full agentic loop (`Brain.chat` / `Brain.run_task`'s tool-use
turns) needs `ANTHROPIC_API_KEY` since it calls the live API - there's no
mocked test for that here by design, to avoid a mock that drifts from the
real tool-use response shape.

## Extending it

- **Better recall** - `memory.recall()` is deliberately simple (token
  overlap). Swap it for embeddings + a vector index once the memory table
  grows large enough that keyword matching misses things.
- **Scheduled self-study** - call `Brain.learn(topic)` from a cron job to have
  the brain keep a running set of topics current on its own.
- **Task outcomes** - `run_task` doesn't know if a task actually succeeded
  from the user's perspective. Add a feedback field to `/task` (or a
  follow-up `/task/{id}/feedback` endpoint) and weight reflection on that.
