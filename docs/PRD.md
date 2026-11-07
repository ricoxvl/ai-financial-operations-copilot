# Product Requirements Document — AI Financial Operations Copilot

**Version:** 0.1 clean restart  
**Product type:** Independent portfolio prototype using synthetic financial data  
**Scope:** Accounts receivable invoice discovery, verification, and draft proposal

## Problem

Finance operations specialists often switch between customer records, invoice lists,
policy documents, and manual checks to prepare invoices. Natural-language AI can
help coordinate these steps, but model mistakes, duplicate writes, and unapproved
financial actions make unsupervised automation unacceptable.

## Target user and job to be done

A finance operations analyst who needs to find customer and invoice information,
verify policy and duplicate risk, and prepare an accurate draft with a traceable
review process. The user should be able to reject or correct a proposal before
any financial record is created.

## MVP user story

> As a finance operations analyst, I can request a draft invoice in natural language,
> review the sourced data and policy checks, and explicitly approve or reject the
> proposal so that no invoice is created without authorization.

## Must-have functionality

- Search synthetic customers and invoice records using read-only tools.
- Retrieve a deterministic invoice policy, including an initial $50k pilot limit.
- Detect likely duplicate invoices using external invoice references.
- Validate customer, amount, reference, description, and authorized status.
- Persist a pending proposal without creating an invoice.
- Require an authenticated approver to create the invoice draft.
- Deduplicate repeated requests and repeated approve actions.
- Record an audit event at each relevant state change.
- Present user-visible rationale, errors, and approval status in the frontend.

## Explicitly out of scope

Real customer records, QuickBooks live integration, money transfers, payment
initiation, bank-account access, tax filing, automatic sending/posting of invoices,
production finance controls, and unattended execution of financial writes.

## Product acceptance criteria

1. Repeated identical idempotency key creates at most one proposal.
2. An unauthorized or rejected proposal creates zero invoices.
3. A valid approval creates exactly one local draft invoice.
4. Validation rejects negative/oversized amounts and unknown customers.
5. Every state-changing action produces an audit entry.
6. Errors include actionable codes/messages without exposing secrets.
7. Evaluation harness supports labeled expected tool calls and expected outcomes.

## Engineering decisions

- Store monetary amounts as **integer cents** rather than floating-point dollars.
- Keep business validation deterministic and outside the LLM.
- Split tool execution permission into read-only versus approval-sensitive.
- Use LangGraph for traceable orchestration and human-in-the-loop checkpoints.
- Start with SQLite locally, switch to PostgreSQL and proper reviewer identity
  before multi-user / production-style deployment.

## Delivery milestones

1. **Foundation** — FastAPI, SQL models, synthetic seed data, approval gate, tests.
2. **Finance tools** — read-only tool layer, deterministic policies, provenance.
3. **AI agent** — OpenAI strict tool calls and LangGraph orchestration.
4. **Reliability** — durable checkpoints, retries, concurrency, audit hardening.
5. **Frontend** — React workflow/chat and review queue.
6. **Experiment** — frozen benchmark dataset and fault-injection evaluation.
