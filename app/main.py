"""API for a synthetic financial operations prototype, not a production finance system."""
import os
import secrets
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import Depends, FastAPI, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from .database import AuditEvent, DraftRequest, create_database_and_seed, get_db
from .finance import (decide_invoice, get_policy, list_customers, list_invoices,
                      list_requests, overview, prepare_invoice, request_dict)
from .schemas import AgentChatInput, DecisionInput, DraftInput
from .agent_service import chat, get_thread, resume_thread, agent_status

@asynccontextmanager
async def lifespan(app: FastAPI):
    create_database_and_seed()
    yield

app = FastAPI(title="AI Financial Operations Copilot", version="1.0.0", lifespan=lifespan,
              description="Local prototype with synthetic data; no external financial account connectivity.")
app.add_middleware(CORSMiddleware,
                   allow_origins=[o.strip() for o in os.getenv("APP_CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173").split(",") if o.strip()],
                   allow_credentials=False, allow_methods=["GET", "POST"], allow_headers=["Content-Type", "X-Approval-Token"])


def verify_approval_token(x_approval_token: str | None = Header(default=None)) -> None:
    expected = os.getenv("APP_APPROVAL_TOKEN")
    if not expected or expected == "replace-with-a-long-random-local-development-token":
        raise HTTPException(503, "Set a non-default APP_APPROVAL_TOKEN to enable approvals")
    if not x_approval_token or not secrets.compare_digest(x_approval_token, expected):
        raise HTTPException(403, "Invalid approval token")


@app.get("/health")
def health():
    return {"status": "ok", "phase": "fullstack", **agent_status()}


@app.get("/overview")
def get_overview(db: Session = Depends(get_db)):
    return overview(db)


@app.get("/policy")
def policy():
    return get_policy()


@app.get("/customers")
def customers(db: Session = Depends(get_db)):
    return list_customers(db)


@app.get("/invoices")
def invoices(customer_id: int | None = None, db: Session = Depends(get_db)):
    return list_invoices(db, customer_id)


@app.get("/requests")
def requests(status: str | None = None, db: Session = Depends(get_db)):
    return list_requests(db, status)


@app.get("/requests/{request_id}")
def get_request(request_id: int, db: Session = Depends(get_db)):
    item = db.get(DraftRequest, request_id)
    if not item:
        raise HTTPException(404, "Request not found")
    return request_dict(item)


@app.post("/requests", status_code=201)
def prepare_invoice_request(payload: DraftInput, db: Session = Depends(get_db)):
    return prepare_invoice(db, payload)


@app.post("/requests/{request_id}/decision", dependencies=[Depends(verify_approval_token)])
def decide(request_id: int, payload: DecisionInput, db: Session = Depends(get_db)):
    return decide_invoice(db, request_id, payload)


@app.get("/audit")
def audit(limit: int = 100, db: Session = Depends(get_db)):
    return [{"id": ev.id, "action": ev.action, "entity_id": ev.entity_id,
             "detail": ev.detail, "created_at": ev.created_at.isoformat() if ev.created_at else None}
            for ev in db.scalars(select(AuditEvent).order_by(AuditEvent.id.desc()).limit(min(max(limit, 1), 500))).all()]


@app.post("/agent/chat")
def agent_chat(payload: AgentChatInput):
    return chat(payload)


@app.get("/agent/threads/{thread_id}")
def agent_thread(thread_id: str):
    return get_thread(thread_id)


@app.post("/agent/threads/{thread_id}/decision", dependencies=[Depends(verify_approval_token)])
def agent_decide(thread_id: str, payload: DecisionInput):
    return resume_thread(thread_id, payload)


WEB_ROOT = Path(__file__).resolve().parent.parent / "web"

@app.get("/", include_in_schema=False)
def index():
    return FileResponse(WEB_ROOT / "index.html")

@app.get("/app.css", include_in_schema=False)
def app_css():
    return FileResponse(WEB_ROOT / "app.css", media_type="text/css")

@app.get("/app.js", include_in_schema=False)
def app_js():
    return FileResponse(WEB_ROOT / "app.js", media_type="application/javascript")
