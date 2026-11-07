# FinPilot — AI Financial Operations Copilot

**Working full-stack portfolio MVP with synthetic financial data.** Local invoice proposal management, customer/invoice search, dashboard, approvals, audit events, and a *separate optional* OpenAI + LangGraph agent.

> **Safety and truth-in-demo:** The included offline chat mode is a **deterministic scripted demo, not an LLM**. The actual LangGraph/OpenAI orchestration implementation is in `app/graph_agent.py`; it becomes active only after you install its optional dependencies and configure an API key. This environment could not install those packages or call the live API, so live mode and the React/Vite build are **not verified here**. No QuickBooks, bank, payment, or external finance integrations exist. Never use this app for real financial data or production financial approvals.

## What's included

| Component | Status | Where |
|---|---|---|
| FastAPI + SQLAlchemy database, synthetic seeded customers | Working, tested | `app/main.py`, `app/database.py` |
| Deterministic finance tools, policy cap, unique references | Working, tested | `app/finance.py` |
| Atomic review/approval → one local draft, rejection and idempotency | Working, tested | `app/finance.py` |
| Browser dashboard, AI-like offline demo, proposals, approvals, audit | Working via FastAPI; browser screenshot not captured | `web/` |
| React + Vite version of the dashboard | Source included, npm build not verified | `frontend/` |
| OpenAI Responses API strict native tool calling | Source included; credentials required, unverified live | `app/graph_agent.py` |
| LangGraph state graph, SQLite checkpoints, `interrupt` and `Command(resume)` | Source included; optional install needed, unverified live | `app/graph_agent.py` |
| Automated functional and resilience tests | **52 passing locally** | `tests/` |
| 150 labeled deterministic offline sanity scenarios | **150/150 passing locally**; not model metrics | `data/`, `scripts/evaluate.py`, `reports/` |

## 1. Start locally (no OpenAI key or Node needed)

Requires **Python 3.11+**. From the project root:

```bash
python -m venv .venv
# Windows PowerShell: .venv\Scripts\Activate.ps1
# Mac/Linux: source .venv/bin/activate
python -m pip install -r requirements.txt
python scripts/setup_demo.py
python -m uvicorn app.main:app --reload
```

Open **http://127.0.0.1:8000/** for the working no-build dashboard, or **http://127.0.0.1:8000/docs** for FastAPI docs. The setup script generates a local approval token and stores it in an untracked `.env`. Copy the token into the approval dialog.

Offline demo prompts:

- `Show customers`
- `What is the approval policy?`
- `List recent invoices`
- `Prepare invoice for Acme Corp, $2,500, description: Consulting services, reference INV-1005.`

The offline parser intentionally accepts only a limited syntax. Use the **New proposal** form for any request it cannot interpret. Every demo prompt is processed on *synthetic* data and independently; separate chat turns do not imply conversational memory.

**Test the human-in-the-loop journey:** Send the sample invoice prompt → see the executed lookup/policy/duplicate/proposal tools → review in Approval Center → enter the generated approval token → approve → verify the single local draft appears under Invoices → inspect Audit Trail. Re-sending the same reference will be blocked. Rejecting creates no invoice. Nothing is issued or paid.

## 2. Turn on actual OpenAI + LangGraph agent

An OpenAI API key is **not included**; API usage may incur charges. With internet/package access available:

```bash
python -m pip install -r requirements-agent.txt
```

Edit `.env`:

```ini
OPENAI_API_KEY=YOUR_OWN_API_KEY
OPENAI_MODEL=gpt-4.1-mini
```

Restart `uvicorn` and refresh the dashboard. The status badge will read **OpenAI + LangGraph**. If it still reads **Offline demo**, verify your key, dependency installation, and `/health` response. To use another compatible OpenAI model, adjust `OPENAI_MODEL`.

The LangGraph pipeline is `model → execute one tool → model` for reads, with `prepare_invoice_draft → interrupt(human approval) → resume(decision) → deterministic write`. SQLite graph checkpoint state persists separately in `copilot-checkpoints.sqlite`. The API verifies the local approval token **before** calling `Command(resume=...)`. The LLM never receives a direct invoice-creation or approval tool. **Live integration has not been executed in this environment; test it with your own key before making performance claims.**

## 3. Optional React app

The included `web/` dashboard is the fastest version to run. A separately authored **React/Vite dashboard** is also included, connected to the same backend APIs. Once Node.js and package downloads are available:

```bash
cd frontend
npm install
npm run dev
```

Open **http://127.0.0.1:5173** with FastAPI still running on port 8000. To compile the production React assets, run `npm run build`. **That npm build could not be run here because package installation was offline**, so fix any environment-specific build issues before deployment. The always-available `web/` dashboard remains an independent fallback.

## 4. Verify local controls and repeatable evaluations

```bash
python -m pytest -q
python scripts/evaluate.py
```

- **52 passing tests:** approvals/rejections, bad tokens, idempotency, case-insensitive references, invalid values, UI route smoke tests, and 40 isolated replay/authorization/rejection scenarios. The 40 fault scenarios are **simulated application faults**, not real database failovers or network timeouts.
- **150 synthetic offline checks:** frozen cases spanning customer lookup (20), invoice search (30), invoice proposals (30), duplicate checks (25), policy (20), insufficient information (15), and validation failures (10). See `reports/offline_evaluation.json`. These measure the *deterministic demo*, **not** LLM tool-selection or task-completion accuracy.
- The historical resume figures (78%→92%, 86%→96%) do **not** describe this new build. A proper online agent A/B evaluation must be designed and run separately, with recorded model/version, cost, latency, tool traces, and held-out data.

## Project layout

```text
app/
  main.py          FastAPI routes, approval header, frontend serving
  database.py      SQLAlchemy tables, test customer data
  finance.py       deterministic financial logic and atomic writes
  agent_service.py scripted offline demo + live mode dispatch
  graph_agent.py   optional OpenAI Responses + LangGraph pipeline
  schemas.py       Pydantic input constraints
web/               no-build polished dashboard (HTML / CSS / JS)
frontend/          separate React/Vite dashboard project
scripts/           setup_demo, generate_evaluation_cases, evaluate
reports/           150-case offline report
 data/              synthetic evaluation input cases
tests/             52 automated tests, isolated test database
 docs/              PRD, architecture, evaluation limitations
```

## Security, scope, and remaining production work

This project is a **local prototype**. The single shared approval token is not user identity, role-based access control, or authorization appropriate for production. Missing production controls include authenticated logins, role-scoped access, per-reviewer audit identity, request/rate limiting, CSRF protection for cookie-based auth (if introduced), resilient multi-process checkpoint locks, secrets management, migrations, retention/privacy policy, alerting, monitoring, security review, real financial data validation, and formal external integration tests. Consider PostgreSQL, encrypted credentials and a queue for jobs before any multi-user deployment. No financial transaction is ever executed.

All monetary values are stored as **integer USD cents**. The policy limit is $50,000. Case-insensitive unique customer/reference indexes and idempotency keys prevent duplicate local drafts from replays. A rejected proposal reserves its reference in this simplified prototype; use a new reference for a new request.

## Documentation

- [`docs/PRD.md`](docs/PRD.md): product requirements and user story
- [`docs/architecture.md`](docs/architecture.md): app architecture and trust boundaries
- [`docs/evaluation.md`](docs/evaluation.md): evaluation metrics and limits
- [OpenAI function calling](https://developers.openai.com/api/docs/guides/function-calling)
- [LangGraph human interrupts](https://reference.langchain.com/python/langgraph/types/interrupt)
