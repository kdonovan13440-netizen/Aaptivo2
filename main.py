import json
import secrets
from contextlib import asynccontextmanager
from fastapi import FastAPI, Depends, Header, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from .config import settings
from .db import init_db, SessionLocal
from .models import Task, ActionRequest
from .agent import answer
from .filesystem import list_files, read_text, write_text
from .integrations import NotConfigured

telephony = NotConfigured()
calendar = NotConfigured()

@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    yield

app = FastAPI(title=settings.app_name, version="0.1.0", lifespan=lifespan)

async def auth(x_api_key: str = Header(default="")):
    if not settings.api_key or settings.api_key == "change-me-before-deploying":
        raise HTTPException(503, "Set a secure API_KEY in the environment before using protected routes.")
    if not secrets.compare_digest(x_api_key, settings.api_key):
        raise HTTPException(401, "Invalid API key.")

class TaskIn(BaseModel):
    title: str = Field(min_length=1, max_length=300)
    description: str = ""
    due_at: str | None = None

class ChatIn(BaseModel):
    message: str = Field(min_length=1, max_length=12000)

class ActionIn(BaseModel):
    action: str
    payload: dict = {}

class FileWrite(BaseModel):
    path: str
    content: str

@app.get("/health")
async def health():
    return {"status":"ok","service":settings.app_name}

@app.post("/v1/assistant/chat", dependencies=[Depends(auth)])
async def chat(body: ChatIn):
    return {"reply": answer(body.message)}

@app.post("/v1/tasks", dependencies=[Depends(auth)])
async def create_task(body: TaskIn):
    async with SessionLocal() as db:
        task = Task(**body.model_dump())
        db.add(task)
        await db.commit()
        await db.refresh(task)
        return {"id":task.id,"title":task.title,"status":task.status}

@app.get("/v1/tasks", dependencies=[Depends(auth)])
async def get_tasks():
    async with SessionLocal() as db:
        rows = (await db.execute(select(Task).order_by(Task.id.desc()))).scalars().all()
        return [{"id":t.id,"title":t.title,"description":t.description,"status":t.status,"due_at":t.due_at} for t in rows]

@app.post("/v1/actions/request", dependencies=[Depends(auth)])
async def request_action(body: ActionIn):
    async with SessionLocal() as db:
        item = ActionRequest(action=body.action, payload=json.dumps(body.payload))
        db.add(item)
        await db.commit()
        await db.refresh(item)
        return {"id":item.id,"status":item.status,"message":"Queued; a trusted companion must obtain user confirmation before execution."}

@app.get("/v1/files", dependencies=[Depends(auth)])
async def files(path: str = "."):
    try:
        return {"files":list_files(path)}
    except ValueError as e:
        raise HTTPException(400,str(e))

@app.get("/v1/files/read", dependencies=[Depends(auth)])
async def file_read(path: str):
    try:
        return {"content":read_text(path)}
    except (ValueError,FileNotFoundError) as e:
        raise HTTPException(400,str(e))

@app.post("/v1/files/write", dependencies=[Depends(auth)])
async def file_write(body: FileWrite):
    try:
        return {"saved":write_text(body.path,body.content)}
    except ValueError as e:
        raise HTTPException(400,str(e))

@app.post("/v1/calls/inbound")
async def inbound_call(payload: dict):
    return await telephony.handle_inbound(payload)

@app.post("/v1/calls/outbound", dependencies=[Depends(auth)])
async def outbound_call(to_number: str, purpose: str):
    raise HTTPException(501,"No live calling provider configured. Configure a provider adapter and consent workflow first.")

@app.get("/v1/calendar/events", dependencies=[Depends(auth)])
async def calendar_events(start: str, end: str):
    try:
        return {"events":await calendar.list_events(start,end)}
    except RuntimeError as e:
        raise HTTPException(501,str(e))

@app.post("/v1/calendar/events", dependencies=[Depends(auth)])
async def calendar_create(event: dict):
    try:
        return await calendar.create_event(event)
    except RuntimeError as e:
        raise HTTPException(501,str(e))
