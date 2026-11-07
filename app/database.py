"""Synthetic finance records. Monetary values are always integer USD cents."""
import os
from datetime import datetime, timezone
from typing import Generator

from dotenv import load_dotenv
from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, UniqueConstraint, Index, func, create_engine, event
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, relationship, sessionmaker

load_dotenv()


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    pass


class Customer(Base):
    __tablename__ = "customers"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120), unique=True, index=True)


class DraftRequest(Base):
    __tablename__ = "draft_requests"
    # The unique constraint prevents two concurrent requests from reserving the
    # same customer + external reference, including different idempotency keys.
    __table_args__ = (UniqueConstraint("customer_id", "external_reference", name="uq_customer_reference"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    idempotency_key: Mapped[str] = mapped_column(String(120), unique=True, index=True)
    customer_id: Mapped[int] = mapped_column(ForeignKey("customers.id"))
    external_reference: Mapped[str] = mapped_column(String(120))
    description: Mapped[str] = mapped_column(String(500))
    amount_cents: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(20), default="pending")
    invoice_id: Mapped[int | None] = mapped_column(ForeignKey("invoices.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)
    customer: Mapped[Customer] = relationship()


Index("uq_customer_ref_case_insensitive", DraftRequest.customer_id, func.lower(DraftRequest.external_reference), unique=True)


class Invoice(Base):
    __tablename__ = "invoices"
    __table_args__ = (UniqueConstraint("customer_id", "external_reference", name="uq_invoice_reference"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    source_request_id: Mapped[int] = mapped_column(ForeignKey("draft_requests.id"), unique=True)
    customer_id: Mapped[int] = mapped_column(ForeignKey("customers.id"))
    external_reference: Mapped[str] = mapped_column(String(120))
    description: Mapped[str] = mapped_column(String(500))
    amount_cents: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(30), default="draft")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)


class AuditEvent(Base):
    __tablename__ = "audit_events"
    id: Mapped[int] = mapped_column(primary_key=True)
    action: Mapped[str] = mapped_column(String(80))
    entity_id: Mapped[int] = mapped_column(Integer)
    detail: Mapped[str] = mapped_column(String(500))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)


class AgentRun(Base):
    """Persist offline demo threads; true LangGraph uses its own checkpointer."""
    __tablename__ = "agent_runs"
    thread_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    mode: Mapped[str] = mapped_column(String(20))
    prompt: Mapped[str] = mapped_column(Text)
    answer: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(20))
    request_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    trace_json: Mapped[str] = mapped_column(Text, default="[]")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)


DB_URL = os.environ.get("APP_DATABASE_URL", "sqlite:///./copilot.db")
engine = create_engine(DB_URL, connect_args={"check_same_thread": False, "timeout": 15} if DB_URL.startswith("sqlite") else {}, pool_pre_ping=True)

if DB_URL.startswith("sqlite"):
    @event.listens_for(engine, "connect")
    def _sqlite_settings(conn, _record):
        cursor = conn.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.execute("PRAGMA busy_timeout=15000")
        cursor.close()

SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def get_db() -> Generator[Session, None, None]:
    with SessionLocal() as db:
        yield db


def create_database_and_seed() -> None:
    Base.metadata.create_all(bind=engine)
    with SessionLocal() as db:
        if db.query(Customer).count() == 0:
            db.add_all([Customer(name="Acme Corp"), Customer(name="Northstar Labs"), Customer(name="Summit Retail"), Customer(name="BluePeak Analytics")])
            db.commit()
