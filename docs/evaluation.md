# Evaluation: executable checks and future live-agent experiment

## Executed in local environment

- `python -m pytest -q` → **52 passed**. Includes 40 isolated simulations of duplicate submissions, repeated approvals, invalid approval credentials, and reject-then-approve attempts, plus concurrent writes/approvals. These are not live service outage tests.
- `python scripts/evaluate.py` → **150/150 deterministic offline sanity cases passed**. Report: `reports/offline_evaluation.json`, including per-case expected tool sequence, observed sequence, outcomes and latency. This is intentionally limited to the **scripted demo**, so do **not** report the fraction as an AI agent benchmark.
- Category breakdown: customer lookup 20, invoice search 30, valid draft proposal 30, duplicate detection 25, policy check 20, incomplete request 15, oversized amount 10.

## How to perform a defensible LLM evaluation next

1. Freeze a **new** representative, diverse natural-language dataset with 150+ unseen prompts (avoid repeated templates used in offline sanity checks), including high-risk negative prompts.
2. Specify target model and versions, prompt versions, tool schemas, dataset split, exact expected calls and correct outcomes, and cost/latency budget.
3. Benchmark a single-agent native function-calling baseline against LangGraph with the *same* models/tools/inputs, separate tuning vs held-out sets.
4. Calculate end-to-end completion, exact/precision-recall tool choice, invalid schema rate, duplicate/unauthorized write rate, p50/p95 latency, token usage, and API cost.
5. Run separate real fault simulations: transient OpenAI timeouts, multi-worker database conflicts, actual checkpoint replay, concurrent approval, and controlled DB outage.
6. Save a dated results artifact with rows for expected and actual outcomes; only then update portfolio/resume metrics.

## Important interpretation

The old **78%→92% task completion**, **86%→96% tool selection** and **40 reliability faults** are *historical descriptions* of a previous version, not measured improvements of this clean restart. The deterministic offline template checks are intentionally easy, so 150/150 does **not** demonstrate model competence or generalization. The LangGraph/OpenAI code is included but was not runnable in the creation environment because the package index was inaccessible and no API key was supplied.
