"""Deterministic financial operations. NEVER trust tool/LLM arguments directly."""
from collections import Counter
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from fastapi import HTTPException
from .database import AuditEvent, Customer, DraftRequest, Invoice
from .schemas import DecisionInput, DraftInput

MAX_INVOICE_CENTS = 5_000_000


def request_dict(item: DraftRequest) -> dict:
    return {"id": item.id, "customer_id": item.customer_id,
            "customer_name": item.customer.name if item.customer else None,
            "external_reference": item.external_reference, "amount_cents": item.amount_cents,
            "description": item.description, "status": item.status, "invoice_id": item.invoice_id,
            "created_at": item.created_at.isoformat() if item.created_at else None}


def invoice_dict(item: Invoice, db: Session) -> dict:
    customer = db.get(Customer, item.customer_id)
    return {"id": item.id, "source_request_id": item.source_request_id,
            "customer_id": item.customer_id, "customer_name": customer.name if customer else "Unknown",
            "external_reference": item.external_reference, "amount_cents": item.amount_cents,
            "description": item.description, "status": item.status,
            "created_at": item.created_at.isoformat() if item.created_at else None}


def list_customers(db: Session) -> list[dict]:
    return [{"id": c.id, "name": c.name} for c in db.scalars(select(Customer).order_by(Customer.name)).all()]


def list_requests(db: Session, status: str | None = None) -> list[dict]:
    statement = select(DraftRequest).order_by(DraftRequest.id.desc())
    if status:
        statement = statement.where(DraftRequest.status == status)
    return [request_dict(r) for r in db.scalars(statement).all()]


def list_invoices(db: Session, customer_id: int | None = None) -> list[dict]:
    statement = select(Invoice).order_by(Invoice.id.desc())
    if customer_id is not None:
        statement = statement.where(Invoice.customer_id == customer_id)
    return [invoice_dict(i, db) for i in db.scalars(statement).all()]


def lookup_customer(db: Session, name: str) -> dict:
    term = name.strip()
    if not term:
        return {"matches": [], "error": "Customer name is required"}
    matches = db.scalars(select(Customer).where(func.lower(Customer.name).like(f"%{term.lower()}%"))).all()
    return {"matches": [{"id": c.id, "name": c.name} for c in matches],
            "exact_match": next(({"id": c.id, "name": c.name} for c in matches if c.name.lower() == term.lower()), None)}


def get_policy() -> dict:
    return {"currency": "USD", "maximum_invoice_cents": MAX_INVOICE_CENTS,
            "approval_required": True, "writes": "local_draft_only",
            "policy": "A human reviewer must approve every invoice proposal. Never issue, pay, send, or post an invoice automatically."}


def check_duplicate(db: Session, customer_id: int, external_reference: str) -> dict:
    rows = db.scalars(select(DraftRequest).where(DraftRequest.customer_id == customer_id,
                                                func.lower(DraftRequest.external_reference) == external_reference.strip().lower())).all()
    return {"duplicate": bool(rows), "matching_request_ids": [r.id for r in rows]}


def prepare_invoice(db: Session, payload: DraftInput) -> dict:
    existing = db.scalar(select(DraftRequest).where(DraftRequest.idempotency_key == payload.idempotency_key))
    if existing:
        same = all(getattr(existing, k) == getattr(payload, k) for k in
                   ("customer_id", "external_reference", "amount_cents", "description"))
        if not same:
            raise HTTPException(409, "Idempotency key reused with different inputs")
        return request_dict(existing)
    if not db.get(Customer, payload.customer_id):
        raise HTTPException(404, "Unknown customer")
    duplicate = check_duplicate(db, payload.customer_id, payload.external_reference)
    if duplicate["duplicate"]:
        raise HTTPException(409, f"Possible duplicate of request {duplicate['matching_request_ids'][0]}")
    proposal = DraftRequest(**payload.model_dump(), status="pending")
    db.add(proposal)
    try:
        db.flush()
        db.add(AuditEvent(action="proposal_created", entity_id=proposal.id, detail=proposal.external_reference))
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "Conflicting request; retry lookup before creating") from None
    db.refresh(proposal)
    return request_dict(proposal)


def decide_invoice(db: Session, request_id: int, payload: DecisionInput) -> dict:
    request = db.get(DraftRequest, request_id)
    if not request:
        raise HTTPException(404, "Request not found")
    target = "approved" if payload.decision == "approve" else "rejected"
    if request.status != "pending":
        if request.status == target:
            return request_dict(request)
        raise HTTPException(409, "A finalized decision cannot be changed")
    try:
        if target == "approved":
            invoice = Invoice(source_request_id=request.id, customer_id=request.customer_id,
                              external_reference=request.external_reference, amount_cents=request.amount_cents,
                              description=request.description, status="draft")
            db.add(invoice)
            db.flush()
            request.invoice_id = invoice.id
        request.status = target
        db.add(AuditEvent(action=f"proposal_{target}", entity_id=request.id, detail=request.external_reference))
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "Approval conflict; inspect the latest proposal state") from None
    db.refresh(request)
    return request_dict(request)


def overview(db: Session) -> dict:
    invoices = list_invoices(db)
    requests = list_requests(db)
    status = Counter(r["status"] for r in requests)
    return {"draft_total_cents": sum(i["amount_cents"] for i in invoices),
            "draft_invoice_count": len(invoices), "pending_count": status["pending"],
            "approved_count": status["approved"], "rejected_count": status["rejected"],
            "customer_count": db.scalar(select(func.count()).select_from(Customer)),
            "recent_invoices": invoices[:5], "recent_requests": requests[:5]}
