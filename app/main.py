from pathlib import Path
from typing import List, Optional

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel

from . import calendar_tool, db, graph
from . import memory as memory_store
from . import research_queue
from .brain import Brain

STATIC_DIR = Path(__file__).parent / "static"

app = FastAPI(title="Secone Brain")
brain = Brain()


@app.on_event("startup")
def startup() -> None:
    db.init_db()


class ChatRequest(BaseModel):
    message: str


class ChatResponse(BaseModel):
    reply: str


class TaskRequest(BaseModel):
    description: str


class TaskResponse(BaseModel):
    task_id: int
    result: str
    reflection: str


class LearnRequest(BaseModel):
    topic: str


class WikipediaScanRequest(BaseModel):
    topics: List[str]


class QueueRequest(BaseModel):
    topics: List[str]


class MemoryIn(BaseModel):
    kind: str
    content: str
    topic: str = ""
    category: str = ""
    tags: List[str] = []


class MemoryUpdate(BaseModel):
    content: Optional[str] = None
    topic: Optional[str] = None
    category: Optional[str] = None
    tags: Optional[List[str]] = None


class CalendarEventIn(BaseModel):
    summary: str
    start: str
    end: str
    description: str = ""
    location: str = ""


class CalendarEventUpdate(BaseModel):
    summary: Optional[str] = None
    start: Optional[str] = None
    end: Optional[str] = None
    description: Optional[str] = None
    location: Optional[str] = None


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/chat", response_model=ChatResponse)
def chat(req: ChatRequest):
    return ChatResponse(reply=brain.chat(req.message))


@app.post("/task", response_model=TaskResponse)
def run_task(req: TaskRequest):
    return TaskResponse(**brain.run_task(req.description))


@app.post("/learn")
def learn(req: LearnRequest):
    return brain.learn(req.topic)


@app.post("/wikipedia/scan")
def scan_wikipedia(req: WikipediaScanRequest):
    return brain.scan_wikipedia(req.topics)


@app.post("/queue")
def add_to_queue(req: QueueRequest):
    return {"queued": research_queue.enqueue(req.topics)}


@app.get("/queue")
def get_queue(status: Optional[str] = None, limit: int = 200):
    return research_queue.list_queue(status=status, limit=limit)


@app.post("/queue/run")
def run_queue(limit: Optional[int] = None):
    return brain.run_research_queue(limit=limit)


@app.post("/queue/stop")
def stop_queue():
    research_queue.request_stop()
    return {"stopped": True}


@app.delete("/queue/{item_id}")
def delete_queue_item(item_id: int):
    research_queue.delete(item_id)
    return {"deleted": item_id}


@app.get("/memory")
def get_memory(kind: Optional[str] = None, limit: int = 100):
    return memory_store.list_memories(kind=kind, limit=limit)


@app.post("/memory")
def add_memory(item: MemoryIn):
    memory_id = memory_store.add_memory(
        item.kind, item.content, item.tags, source="manual", topic=item.topic, category=item.category
    )
    return {"id": memory_id}


@app.patch("/memory/{memory_id}")
def update_memory(memory_id: int, item: MemoryUpdate):
    updated = memory_store.update_memory(memory_id, **item.model_dump())
    if updated is None:
        raise HTTPException(status_code=404, detail="Memory not found")
    return updated


@app.delete("/memory/{memory_id}")
def delete_memory(memory_id: int):
    memory_store.delete_memory(memory_id)
    return {"deleted": memory_id}


@app.get("/calendar/events")
def list_calendar_events(
    time_min: Optional[str] = None,
    time_max: Optional[str] = None,
    query: Optional[str] = None,
    max_results: int = 20,
):
    try:
        return calendar_tool.list_events(
            time_min=time_min, time_max=time_max, query=query, max_results=max_results
        )
    except RuntimeError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@app.post("/calendar/events")
def create_calendar_event(event: CalendarEventIn):
    try:
        return calendar_tool.create_event(**event.model_dump())
    except RuntimeError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@app.patch("/calendar/events/{event_id}")
def update_calendar_event(event_id: str, event: CalendarEventUpdate):
    fields = {k: v for k, v in event.model_dump().items() if v is not None}
    try:
        return calendar_tool.update_event(event_id, **fields)
    except RuntimeError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@app.delete("/calendar/events/{event_id}")
def delete_calendar_event(event_id: str):
    try:
        calendar_tool.delete_event(event_id)
    except RuntimeError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return {"deleted": event_id}


@app.get("/graph")
def graph_page():
    return FileResponse(STATIC_DIR / "graph.html")


@app.get("/voice")
def voice_page():
    return FileResponse(STATIC_DIR / "voice.html")


@app.get("/graph/data")
def graph_data():
    return graph.build_graph()
