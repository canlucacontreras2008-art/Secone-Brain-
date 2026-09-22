from typing import List, Optional

from fastapi import FastAPI
from pydantic import BaseModel

from . import db
from . import memory as memory_store
from .brain import Brain

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
    result: str
    reflection: str


class LearnRequest(BaseModel):
    topic: str


class MemoryIn(BaseModel):
    kind: str
    content: str
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


@app.get("/memory")
def get_memory(kind: Optional[str] = None, limit: int = 100):
    return memory_store.list_memories(kind=kind, limit=limit)


@app.post("/memory")
def add_memory(item: MemoryIn):
    memory_id = memory_store.add_memory(item.kind, item.content, item.tags, source="manual")
    return {"id": memory_id}
