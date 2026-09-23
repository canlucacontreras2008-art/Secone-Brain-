from pathlib import Path
from typing import List, Optional

from fastapi import FastAPI
from fastapi.responses import FileResponse
from pydantic import BaseModel

from . import db, graph
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


@app.get("/graph")
def graph_page():
    return FileResponse(STATIC_DIR / "graph.html")


@app.get("/voice")
def voice_page():
    return FileResponse(STATIC_DIR / "voice.html")


@app.get("/graph/data")
def graph_data():
    return graph.build_graph()
