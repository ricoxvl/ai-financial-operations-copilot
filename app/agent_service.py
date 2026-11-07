"""Agent entrypoint with explicit offline deterministic demo and optional real LangGraph+OpenAI."""
import importlib.util
import json
import os
import re
import uuid
from decimal import Decimal
from fastapi import HTTPException
from pydantic import ValidationError
from sqlalchemy.orm import Session
from .database import AgentRun, SessionLocal
from .finance import (check_duplicate, decide_invoice, get_policy, list_customers, list_invoices,
                      lookup_customer, prepare_invoice)
from .schemas import AgentChatInput, DecisionInput, DraftInput


def agent_status() -> dict:
    has_graph = importlib.util.find_spec("langgraph") is not None
    has_key = bool(os.getenv("OPENAI_API_KEY", "").strip())
    mode = "openai_langgraph" if has_graph and has_key else "offline_demo"
    return {"agent_mode": mode, "langgraph_available": has_graph,
            "openai_configured": has_key,
            "note": ("Live AI tool calling and LangGraph graph execution enabled." if mode == "openai_langgraph"
                     else "Deterministic offline demonstration, not a live LLM. Install requirements-agent.txt and set OPENAI_API_KEY for actual AI tool calling.")}


def _response(thread_id: str, mode: str, answer: str, status: str, trace: list[dict], request_id: int | None = None) -> dict:
    return {"thread_id": thread_id, "mode": mode, "answer": answer, "status": status,
            "pending_request_id": request_id if status == "pending_approval" else None,
            "request_id": request_id, "trace": trace}


def _save_demo(db: Session, thread_id: str, prompt: str, answer: str, status: str,
               trace: list[dict], request_id: int | None = None) -> dict:
    db.add(AgentRun(thread_id=thread_id, mode="offline_demo", prompt=prompt, answer=answer,
                    status=status, request_id=request_id, trace_json=json.dumps(trace)))
    db.commit()
    return _response(thread_id, "offline_demo", answer, status, trace, request_id)


def _extract_fields(message: str, db: Session) -> tuple[dict, list[str]]:
    """Intentionally limited offline parser, not an LLM or a general NLP system."""
    amount_match = re.search(r"\$\s*([0-9][0-9,]*(?:\.[0-9]{1,2})?)(?![0-9.])", message)
    reference_match = re.search(r"\b(?:reference|ref|invoice\s+number)\s*[:#-]?\s*([A-Za-z0-9][A-Za-z0-9._/-]{2,})\b", message, re.I)
    names = [c for c in list_customers(db) if c["name"].lower() in message.lower()]
    service_match = re.search(r"\bfor\s+((?:(?!\b(?:reference|ref)\b)[\w\s-])+?)\s*(?:,\s*(?:reference|ref)|\s*[.;]?$)", message, re.I)
    service = service_match.group(1).strip().strip(", ") if service_match else ""
    if names and service.lower().startswith(names[0]["name"].lower()):
        # "for Acme Corp" is a customer target, not a service description.
        service = ""
    explicit_service = re.search(r"\b(?:description|services?|work)\s*[:=-]\s*(.{3,100}?)(?:,\s*(?:reference|ref)|$)", message, re.I)
    if explicit_service:
        service = explicit_service.group(1).strip().rstrip(".")
    if not service:
        match = re.search(r"\bfor\s+([\w -]{3,80}?)\s+(?:to|for)\s+" + (re.escape(names[0]["name"]) if names else r"\S+"), message, re.I)
        if match:
            service = match.group(1).strip()
    fields = {
        "customer": names[0] if len(names) == 1 else None,
        "amount_cents": int(Decimal(amount_match.group(1).replace(",", "")) * 100) if amount_match else None,
        "external_reference": reference_match.group(1) if reference_match else None,
        "description": service if len(service) >= 3 else None,
    }
    missing = [label for key, label in [("customer", "customer (use an exact customer name)"),
                                      ("amount_cents", "USD amount, e.g. $2,500"),
                                      ("external_reference", "reference, e.g. INV-1005"),
                                      ("description", "description, e.g. description: consulting services")]
               if not fields[key]]
    return fields, missing


def _offline_chat(payload: AgentChatInput) -> dict:
    thread_id = str(uuid.uuid4())
    message = payload.message.strip()
    lower = message.lower()
    trace: list[dict] = []
    with SessionLocal() as db:
        if any(term in lower for term in ("policy", "limit", "approval requirement")) and not any(term in lower for term in ("draft", "create", "prepare")):
            policy = get_policy()
            trace.append({"tool": "retrieve_policy", "result": policy})
            return _save_demo(db, thread_id, message, "Policy: maximum $50,000 per local draft. Every proposal requires human approval. No emails, payments, or posting are performed.", "completed", trace)
        if any(term in lower for term in ("customers", "clients", "customer list")) and not any(term in lower for term in ("draft", "create", "prepare")):
            customers = list_customers(db)
            trace.append({"tool": "list_customers", "result": customers})
            return _save_demo(db, thread_id, message, "Synthetic customers: " + ", ".join(c["name"] for c in customers) + ".", "completed", trace)
        if any(term in lower for term in ("list invoice", "show invoice", "outstanding invoice", "recent invoice")):
            names = [c for c in list_customers(db) if c["name"].lower() in lower]
            invoices = list_invoices(db, names[0]["id"] if len(names) == 1 else None)
            trace.append({"tool": "search_invoices", "result": invoices})
            answer = (f"Found {len(invoices)} local draft invoice(s). " + "; ".join(f"{x['external_reference']} · ${x['amount_cents']/100:,.2f}" for x in invoices[:8])) if invoices else "No local draft invoices found. Approved proposals create drafts; this prototype doesn't track payment or outstanding status."
            return _save_demo(db, thread_id, message, answer, "completed", trace)
        if not any(term in lower for term in ("invoice", "draft", "prepare", "create")):
            return _save_demo(db, thread_id, message, "Offline demo supports: 'show customers', 'show policy', 'list invoices', or a structured invoice draft request. Live natural-language AI requires an API key and LangGraph dependencies.", "completed", trace)
        fields, missing = _extract_fields(message, db)
        if missing:
            return _save_demo(db, thread_id, message, "For a safe invoice proposal, provide: " + "; ".join(missing) + ". Example: Prepare invoice for Acme Corp, $2,500, description: Consulting services, reference INV-1005.", "needs_details", trace)
        customer = fields["customer"]
        trace.append({"tool": "lookup_customer", "result": lookup_customer(db, customer["name"])})
        trace.append({"tool": "retrieve_policy", "result": get_policy()})
        duplicate = check_duplicate(db, customer["id"], fields["external_reference"])
        trace.append({"tool": "check_duplicate", "result": duplicate})
        if duplicate["duplicate"]:
            return _save_demo(db, thread_id, message, "Duplicate reference detected. No new proposal or invoice was created.", "blocked", trace)
        try:
            draft = DraftInput(customer_id=customer["id"], external_reference=fields["external_reference"],
                               amount_cents=fields["amount_cents"], description=fields["description"],
                               idempotency_key="offline-" + uuid.uuid5(uuid.NAMESPACE_URL, f"{customer['id']}:{fields['external_reference']}").hex)
            prepared = prepare_invoice(db, draft)
        except (ValidationError, HTTPException) as error:
            reason = error.detail if isinstance(error, HTTPException) else "Amount or invoice fields fail the deterministic policy"
            trace.append({"tool": "prepare_invoice_draft", "error": str(reason)})
            return _save_demo(db, thread_id, message, f"Blocked by validation: {reason}. No invoice was created.", "blocked", trace)
        trace.append({"tool": "prepare_invoice_draft", "result": prepared})
        answer = f"Proposal #{prepared['id']} is awaiting review: {customer['name']} · ${prepared['amount_cents']/100:,.2f} · {prepared['description']} · {prepared['external_reference']}. No invoice exists until approved."
        return _save_demo(db, thread_id, message, answer, "pending_approval", trace, prepared["id"])


def chat(payload: AgentChatInput) -> dict:
    mode = agent_status()["agent_mode"]
    if mode == "openai_langgraph":
        from .graph_agent import start_graph
        return start_graph(payload.message)
    return _offline_chat(payload)


def get_thread(thread_id: str) -> dict:
    with SessionLocal() as db:
        item = db.get(AgentRun, thread_id)
        if item:
            return _response(thread_id, item.mode, item.answer, item.status,
                             json.loads(item.trace_json), item.request_id)
    if agent_status()["agent_mode"] == "openai_langgraph":
        from .graph_agent import read_graph
        return read_graph(thread_id)
    raise HTTPException(404, "Thread not found")


def resume_thread(thread_id: str, decision: DecisionInput) -> dict:
    with SessionLocal() as db:
        item = db.get(AgentRun, thread_id)
        if item:
            if item.request_id is None:
                raise HTTPException(409, "This thread has no proposal to approve")
            result = decide_invoice(db, item.request_id, decision)
            trace = json.loads(item.trace_json)
            event = {"tool": "human_approval", "result": {"decision": decision.decision, "invoice_id": result["invoice_id"]}}
            if item.status == "pending_approval":
                trace.append(event)
                item.trace_json = json.dumps(trace)
            item.status = result["status"]
            item.answer = (f"Approved. Local draft invoice #{result['invoice_id']} created exactly once."
                           if result["status"] == "approved" else "Rejected. No invoice was created.")
            db.commit()
            return _response(thread_id, item.mode, item.answer, item.status, trace, item.request_id)
    if agent_status()["agent_mode"] == "openai_langgraph":
        from .graph_agent import resume_graph
        return resume_graph(thread_id, decision.decision)
    raise HTTPException(404, "Thread not found")
