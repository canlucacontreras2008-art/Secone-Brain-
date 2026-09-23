# Secone Brain

An AI assistant that learns two ways: from the live internet (`web_search`)
and from its own experience doing tasks (self-reflection after every task,
stored as long-term memory it recalls on future work).

## How it thinks

- **`app/brain.py`** - the agentic loop. Every chat or task request runs
  Claude in a tool-use loop with `web_search` (a server-side tool, so it's
  real live internet access, not training data), `remember`, `recall`,
  `queue_for_learning`, and four Google Calendar tools (see "Calendar"
  below). `queue_for_learning` - the model calls this itself when it
  notices a real gap in what it knows, adding that topic to the research
  queue (see below) instead of just guessing. It's the same queue the
  **Voice Chat** page and the graph's Queue panel both show, so a gap
  surfaced in conversation shows up right there to research later.
- **`app/memory.py` + `app/db.py`** - long-term memory, backed by SQLite.
  Every memory is a `fact` (something true about the world or the user) or a
  `lesson` (something learned about how to do a task well), plus two
  authoritative grouping fields the model sets on every `remember` call (see
  `tools.REMEMBER_TOOL`): `topic` - the specific subject, freeform but meant
  to be reused verbatim across memories about the same subject - and
  `category` - the broader grand-topic that subject belongs under (e.g.
  "Gear" the topic sits under "Mechanics" the category), picked from a fixed
  list (`tools.CATEGORIES`) so it can't drift into near-duplicate wording the
  way an open-ended field could. `tags` remain a separate, freeform field for
  search only - neither one affects grouping. Recall is keyword-overlap
  search - no external vector DB or API key needed to get started; swap in
  embeddings later if recall quality becomes the bottleneck.
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
  onto the open web even if the model tries to. Every fact from one scan is
  forced to the exact same `topic` string server-side (`default_topic` in
  `Brain._run_loop`) rather than trusting the model to phrase it identically
  across many separate `remember` calls - otherwise "Ada Lovelace" one call
  and "Ada Lovelace (mathematician)" the next would fragment one real
  subject into several unrelated topic clusters.
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

A 3D view of everything the brain knows, as a small solar system with three
nested levels: a glowing golden holographic core in the center - a dense
wireframe sphere (layered latitude/longitude lines, scattered short "circuit
trace" arcs, twinkling points, a couple of tilted frame rings) rather than a
plain ball - orbited by one bigger, neutral-toned **category globe** per
grand-topic (e.g. "Mechanics", "Coding" - `category`, see above), labeled
persistently since there are only a handful of these. Inside each category
globe orbit the smaller **topic globes** for every branch under it (the
connected component a group of memories belongs to, computed from real
relationships: a task links to the lesson it produced, and memories link
when they share the same `topic`), each tinted in that branch's own color.
A branch with no category at all falls back to orbiting the main globe
directly, exactly as before this level existed - nothing regresses for old
or uncategorized data. That branch's own memories then orbit *their* topic
globe in turn - a hierarchy, not a flat shell - and every level of it drifts
continuously on its own, independent of camera control. Lessons are green
and tasks are blue at every level; facts pick up their branch's color.

Old data saved before `category` existed has no category yet, so it stays
uncategorized (orbiting the main globe directly) until you run
`python scripts/backfill_categories.py`, which retroactively categorizes
memories whose `topic` matches a known Wikipedia-scan topic (see
`TOPIC_TO_CATEGORY` in that script - extend it for topics beyond the ones
already covered). New scans and manual `remember` calls categorize
themselves automatically.

Drag to rotate, scroll to zoom, hover a memory for its label, click one for
the full detail panel. Search highlights matching memories and dims the
rest; the legend toggles a kind on/off. Names stay hidden until you hover,
select, or search for them, so the default view stays a clean, ambient
scene rather than a wall of text.

Works on a phone, too: one-finger drag rotates, pinch zooms in and out, and
tap a memory for its detail panel (the hint text switches to touch wording
automatically on a touch device). The header, search bar, and queue panel
resize to fit a narrow screen instead of overflowing it, and every button
has a bigger tap target than its on-screen size suggests.

## Using it from your phone

The interface is just a page the FastAPI server serves, so your phone needs
to be able to reach that server over the network - by default `uvicorn`
only listens on `localhost`, which only your own computer can reach.

1. Start the server bound to your machine's LAN address instead of just
   `localhost`:
   ```bash
   uvicorn app.main:app --host 0.0.0.0 --reload
   ```
2. Find your computer's local IP address (Windows: `ipconfig`, look for
   "IPv4 Address" under your active adapter; macOS/Linux: `ifconfig` or
   `ip addr`). It'll look like `192.168.x.x`.
3. On your phone, connect to the **same Wi-Fi network** and open
   `http://<that-IP>:8000/graph` in the browser.

Everything - chat, tasks, Wikipedia scanning, the queue - works from the
phone exactly the same way, since it's all plain HTTP hitting the same
server; there's nothing Wikipedia-scan-specific to make work separately.

**Only do this on a trusted home network, never on public Wi-Fi** -
`--host 0.0.0.0` makes the API (including everything in memory) reachable
by any device on that network, not just your phone.

A **Queue** button in the header opens a panel for managing the research
queue entirely from the browser - no `curl` needed. Add a topic (typed or
Enter), remove one with its `×`, **Run** to work through everything pending,
**Stop** to halt after the current topic finishes (it won't abort an
Anthropic API call mid-conversation, just stop starting new ones). The panel
polls `GET /queue` every few seconds, so status - a colored dot per item:
gray pending, pulsing amber running, green done, red error - stays live
whether the run was started here or via `curl`. A learning progress bar
along the bottom (`done/total learned`, plus a failed count if any) tracks
the same data and appears automatically once anything's been queued.

It's a single self-contained page (`app/static/graph.html`) - a hand-rolled
3D projection (rotate, perspective-project, painter's-algorithm depth sort)
on a plain `<canvas>`, no Three.js/WebGL/D3 or other JS dependency, so the
feature works offline and has nothing to vendor or build. Layout is
deterministic (seeded per node ID), so the same data settles into the same
positions across reloads - only the live auto-rotate animates.

The search box also has a microphone button next to it, for searching your
memories by voice instead of typing.

## Voice Chat (`/voice`)

A minimal chat page for talking to the brain out loud: tap the mic, speak,
and it transcribes your speech, sends it to `/chat`, shows the reply, and
(unless you uncheck "Speak replies aloud") reads it back to you. Typing
still works exactly as before - the mic is an alternative input, not a
replacement.

Voice input and output are both just browser APIs
(`SpeechRecognition`/`webkitSpeechRecognition` for input,
`speechSynthesis` for output) - nothing server-side, no extra API key or
service. Chrome and Edge (desktop and Android) support both; Firefox and
Safari have little to no `SpeechRecognition` support, so the mic button
disables itself with an explanation and typing still works everywhere.

When you ask about something the brain doesn't know enough about, it can
call `queue_for_learning` on its own (see "How it thinks" above) to add
that topic to the research queue - check the Queue panel on the Memory
Graph page to see it show up and run it.

## Calendar

The brain can read, create, update, and delete events on your real Google
Calendar - through chat, a task, or Voice Chat ("what's on my schedule
tomorrow?", "schedule a dentist appointment Friday at 2pm"), or directly via
the `/calendar/events` endpoints below.

It only ever does this because you asked in the moment - it never touches
your calendar proactively - and it's given the current date and time in every
chat/task so it can resolve "tomorrow" or "next Tuesday" correctly. Before
changing or deleting an event, it looks it up first via
`calendar_list_events` rather than guessing an id.

### One-time setup

Google requires you to create your own OAuth credentials - there's no way
around this step, and no default/shared credentials would be safe to ship in
a public repo anyway.

1. Go to the [Google Cloud Console](https://console.cloud.google.com/), create
   a project (or pick an existing one).
2. **APIs & Services -> Library** - search for "Google Calendar API" and
   enable it.
3. **APIs & Services -> OAuth consent screen** - choose **External**, fill in
   the required fields (app name, your email), and add your own Google
   account as a **test user**. Leaving the app in "Testing" mode is fine for
   personal use - no Google review needed, it just means only accounts you
   list as test users can authorize it.
4. **APIs & Services -> Credentials -> Create Credentials -> OAuth client
   ID**. Application type: **Desktop app**. Download the resulting JSON and
   save it as `credentials.json` in the project root.
5. Run the one-time interactive authorization:
   ```bash
   python scripts/gcal_auth.py
   ```
   This opens your browser, you sign in and approve access, and it saves a
   `token.json` locally. The server reads and silently refreshes that token
   from then on - you only run this script again if you delete `token.json`
   or revoke access.

**Never commit `credentials.json` or `token.json`** - both are already in
`.gitignore`. `credentials.json` identifies your OAuth app; `token.json` is
an active credential for your real calendar - treat it like a password.

By default this uses your **primary** calendar and resolves relative dates
against the server's own local timezone. Override either in `.env`:
```
GOOGLE_CALENDAR_ID=primary
BRAIN_TIMEZONE=America/New_York
```
`BRAIN_TIMEZONE` matters if the server runs somewhere (e.g. a cloud box)
whose local timezone isn't yours - set it to your own [IANA timezone
name](https://en.wikipedia.org/wiki/List_of_tz_database_time_zones) so
"tomorrow" means tomorrow in *your* timezone, not the server's.

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
| POST   | `/queue/stop`| -                               | Signals the running queue to halt after its current topic finishes. |
| DELETE | `/queue/{id}`| -                               | Removes one queue item by id, any status. |
| GET    | `/memory`    | `?kind=fact\|lesson&limit=100` | Lists stored memories. |
| POST   | `/memory`    | `{"kind", "content", "topic", "category", "tags"}` | Manually add a memory. `topic` groups it with others on the same subject; `category` (see `tools.CATEGORIES`) nests that topic under a grand-topic globe. |
| GET    | `/calendar/events` | `?time_min=&time_max=&query=&max_results=20` | Lists calendar events in a range (defaults to now through 7 days out). |
| POST   | `/calendar/events` | `{"summary", "start", "end", "description", "location"}` | Creates an event. `start`/`end` are RFC3339 datetimes, or plain `"YYYY-MM-DD"` for an all-day event. |
| PATCH  | `/calendar/events/{id}` | any subset of the fields above | Updates only the fields provided. |
| DELETE | `/calendar/events/{id}` | -                         | Deletes an event. |
| GET    | `/graph`     | -                               | The memory graph UI (open in a browser). |
| GET    | `/graph/data`| -                               | `{nodes, edges}` JSON backing the graph UI. |
| GET    | `/voice`     | -                               | The voice chat UI (open in a browser). |
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
