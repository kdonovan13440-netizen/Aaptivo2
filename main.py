import json
import secrets
from contextlib import asynccontextmanager
from fastapi import FastAPI, Depends, Header, HTTPException, Request
from fastapi.responses import HTMLResponse, Response
from pydantic import BaseModel, Field
from sqlalchemy import select
from .config import settings
from .db import init_db, SessionLocal
from .models import Task, ActionRequest
from .agent import answer
from .filesystem import list_files, read_text, write_text
from .integrations import NotConfigured
from .telephony import (
    TwilioProvider,
    closing_twiml,
    greeting_twiml,
    reprompt_twiml,
    reply_twiml,
    twilio_configured,
)
from .verticals import active_vertical, business_name, catalog

telephony = TwilioProvider() if twilio_configured() else NotConfigured()
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
    v = active_vertical()
    return {
        "status": "ok",
        "service": settings.app_name,
        "vertical": v.key,
        "vertical_name": v.name,
        "business": business_name(v),
    }

@app.get("/v1/verticals", dependencies=[Depends(auth)])
async def verticals():
    v = active_vertical()
    return {"active": v.key, "business": business_name(v), "verticals": catalog()}

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
    result = await telephony.handle_inbound(payload)
    if isinstance(result, dict) and "twiml" in result:
        return Response(content=result["twiml"], media_type="application/xml")
    return result

@app.post("/v1/calls/voice")
async def call_voice():
    # Twilio webhook (no API key: Twilio cannot send one). Opens the
    # conversation flow: greeting plus a speech gather.
    return Response(content=greeting_twiml(), media_type="application/xml")

@app.post("/v1/calls/gather")
async def call_gather(request: Request, retry: int = 0):
    # Twilio posts the caller's speech as the SpeechResult form field.
    form = await request.form()
    speech = str(form.get("SpeechResult") or "").strip()
    if not speech:
        if retry >= 1:
            return Response(content=closing_twiml(), media_type="application/xml")
        return Response(content=reprompt_twiml(), media_type="application/xml")
    if "goodbye" in speech.lower():
        return Response(content=closing_twiml(), media_type="application/xml")
    return Response(content=reply_twiml(answer(speech)), media_type="application/xml")

@app.post("/v1/calls/outbound", dependencies=[Depends(auth)])
async def outbound_call(to_number: str, purpose: str):
    if not twilio_configured():
        raise HTTPException(501,"No live calling provider configured. Configure a provider adapter and consent workflow first.")
    try:
        return await telephony.place_call(to_number, purpose)
    except RuntimeError as e:
        raise HTTPException(502, str(e))

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


DASHBOARD_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Aptivo Agent — Dashboard</title>
<style>
  body { font-family: system-ui, sans-serif; margin: 0; background: #0f1420; color: #e8ecf3; }
  header { padding: 20px 24px 8px; }
  h1 { margin: 0; font-size: 22px; }
  .sub { color: #9aa7bd; font-size: 13px; margin-top: 4px; }
  main { display: grid; gap: 16px; grid-template-columns: repeat(auto-fit, minmax(300px, 1fr)); padding: 16px 24px 24px; }
  .card { background: #182034; border: 1px solid #26314d; border-radius: 12px; padding: 16px; }
  .card h2 { margin: 0 0 10px; font-size: 15px; }
  .ok { color: #4ade80; } .bad { color: #f87171; } .muted { color: #9aa7bd; }
  input, textarea, button { font: inherit; border-radius: 8px; border: 1px solid #33415e; background: #0f1420; color: #e8ecf3; padding: 8px 10px; }
  button { background: #2f6df6; border-color: #2f6df6; color: #fff; cursor: pointer; }
  button:disabled { opacity: .5; cursor: default; }
  .row { display: flex; gap: 8px; } .row > * { flex: 1; }
  ul { margin: 8px 0 0; padding-left: 18px; } li { margin: 4px 0; }
  pre { white-space: pre-wrap; word-break: break-word; background: #0f1420; border-radius: 8px; padding: 10px; min-height: 40px; }
  label { font-size: 12px; color: #9aa7bd; display: block; margin-bottom: 4px; }
</style>
</head>
<body>
<header>
  <h1>Aptivo Agent</h1>
  <div class="sub">Dashboard — service status, tasks, chat and calls</div>
</header>
<main>
  <section class="card">
    <h2>Service</h2>
    <div id="health">Checking…</div>
    <div style="margin-top:12px">
      <label for="key">API key (needed for tasks, chat and calls)</label>
      <div class="row">
        <input id="key" type="password" placeholder="X-API-Key" autocomplete="off">
        <button id="saveKey" style="flex:0 0 auto">Save</button>
      </div>
    </div>
  </section>

  <section class="card">
    <h2>Vertical market</h2>
    <div id="verticalActive">Checking…</div>
    <ul id="verticals"><li class="muted">Enter the API key to browse every market this agent can work in.</li></ul>
    <p class="muted" style="font-size:12px">To switch markets, set AGENT_VERTICAL to a market key in the host's environment settings (and BUSINESS_NAME to the business name), then restart or redeploy. The greeting, the services and the booking questions all follow the market.</p>
  </section>

  <section class="card">
    <h2>Tasks</h2>
    <div class="row">
      <input id="taskTitle" placeholder="New task title">
      <button id="addTask" style="flex:0 0 auto">Add</button>
    </div>
    <ul id="tasks"><li class="muted">Enter the API key, then tasks load here.</li></ul>
  </section>

  <section class="card">
    <h2>Chat with Aptivo</h2>
    <div class="row">
      <input id="chatIn" placeholder="Say something…">
      <button id="sendChat" style="flex:0 0 auto">Send</button>
    </div>
    <pre id="chatOut" class="muted">Replies appear here. Needs the API key, and a GROQ_API_KEY on the server for AI answers.</pre>
  </section>

  <section class="card">
    <h2>Calls</h2>
    <div class="row">
      <input id="callTo" placeholder="Phone number">
      <input id="callWhy" placeholder="Purpose">
    </div>
    <button id="callBtn" style="margin-top:8px">Request outbound call</button>
    <pre id="callOut" class="muted">No telephony provider is configured yet, so calls will report that honestly instead of pretending to dial.</pre>
  </section>
</main>
<script>
const $ = id => document.getElementById(id);
const key = () => localStorage.getItem('aptivo_api_key') || '';
$('key').value = key();
$('saveKey').onclick = () => { localStorage.setItem('aptivo_api_key', $('key').value.trim()); loadTasks(); loadVerticals(); };
const headers = () => ({ 'Content-Type': 'application/json', 'X-API-Key': key() });

async function loadHealth() {
  try {
    const r = await fetch('/health'); const j = await r.json();
    $('health').innerHTML = '<span class="ok">● Online</span> — ' + j.service;
    $('verticalActive').innerHTML = 'Active market: <strong>' + j.vertical_name.replace(/</g,'&lt;') + '</strong>' +
      ' <span class="muted">(' + j.vertical + ') for ' + j.business.replace(/</g,'&lt;') + '</span>';
  } catch (e) { $('health').innerHTML = '<span class="bad">● Offline</span>'; $('verticalActive').textContent = 'Could not check.'; }
}
async function loadVerticals() {
  if (!key()) return;
  try {
    const r = await fetch('/v1/verticals', { headers: headers() });
    const j = await r.json();
    $('verticals').innerHTML = j.verticals.map(v =>
      '<li>' + (v.key === j.active ? '<strong>' : '') + v.name.replace(/</g,'&lt;') +
      (v.key === j.active ? ' — active</strong>' : '') +
      ' <span class="muted">' + v.key + ' — ' + v.tagline.replace(/</g,'&lt;') + '</span></li>').join('');
  } catch (e) { $('verticals').innerHTML = '<li class="bad">Could not load markets.</li>'; }
}
async function loadTasks() {
  if (!key()) return;
  try {
    const r = await fetch('/v1/tasks', { headers: headers() });
    const j = await r.json();
    $('tasks').innerHTML = (j.length ? '' : '<li class="muted">No tasks yet.</li>') +
      j.map(t => '<li>' + t.title.replace(/</g,'&lt;') + ' <span class="muted">(' + t.status + ')</span></li>').join('');
  } catch (e) { $('tasks').innerHTML = '<li class="bad">Could not load tasks.</li>'; }
}
$('addTask').onclick = async () => {
  const title = $('taskTitle').value.trim(); if (!title) return;
  await fetch('/v1/tasks', { method: 'POST', headers: headers(), body: JSON.stringify({ title }) });
  $('taskTitle').value = ''; loadTasks();
};
$('sendChat').onclick = async () => {
  const msg = $('chatIn').value.trim(); if (!msg) return;
  $('chatOut').textContent = '…';
  try {
    const r = await fetch('/v1/assistant/chat', { method: 'POST', headers: headers(), body: JSON.stringify({ message: msg }) });
    const j = await r.json();
    $('chatOut').textContent = j.reply || JSON.stringify(j);
  } catch (e) { $('chatOut').textContent = 'Chat request failed.'; }
};
$('callBtn').onclick = async () => {
  const to = $('callTo').value.trim(), why = $('callWhy').value.trim() || 'dashboard request';
  if (!to) return;
  try {
    const r = await fetch('/v1/calls/outbound?to_number=' + encodeURIComponent(to) + '&purpose=' + encodeURIComponent(why),
      { method: 'POST', headers: headers() });
    const j = await r.json();
    $('callOut').textContent = j.detail || JSON.stringify(j);
  } catch (e) { $('callOut').textContent = 'Call request failed.'; }
};
loadHealth(); loadTasks(); loadVerticals();
</script>
</body>
</html>
"""

@app.get("/dashboard", response_class=HTMLResponse)
async def dashboard():
    return DASHBOARD_HTML

@app.get("/", response_class=HTMLResponse)
async def root():
    return DASHBOARD_HTML
