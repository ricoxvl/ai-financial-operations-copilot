from typing import Literal
from pydantic import BaseModel, ConfigDict, Field


class DraftInput(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    customer_id: int = Field(gt=0)
    external_reference: str = Field(min_length=3, max_length=120, pattern=r"^[A-Za-z0-9][A-Za-z0-9._/-]*$")
    amount_cents: int = Field(gt=0, le=5_000_000)
    description: str = Field(min_length=3, max_length=500)
    idempotency_key: str = Field(min_length=8, max_length=120)


class DecisionInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    decision: Literal["approve", "reject"]


class AgentChatInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    message: str = Field(min_length=3, max_length=2000)
    thread_id: str | None = Field(default=None, min_length=12, max_length=64, pattern=r"^[a-zA-Z0-9-]+$")
