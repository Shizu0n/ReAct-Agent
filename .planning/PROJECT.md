# ReAct Agent — Free-Tier Portfolio Showcase

## What This Is

A working ReAct (Reasoning + Acting) agent, deployed full-stack, built to demonstrate
modern AI-agent engineering competence to hiring managers and recruiters for AI roles.
The product runs entirely on **free-tier LLM providers** (Gemini, Groq, GitHub Models) and
free infrastructure — the constraint is deliberate and treated as part of the engineering
story, not as a limitation to hide.

The next phase of work scales the agent with three market-relevant 2026 capabilities —
**long-term memory + RAG**, **MCP (Model Context Protocol) tooling**, and
**observability/evals** — all implemented within free-tier quotas.

## Core Value

A recruiter can open the live demo and, within minutes, see legible evidence of
agent-engineering skill: an agent that reasons visibly, remembers across turns, retrieves
from documents the user uploaded, exposes its execution traces and eval results — all
running on $0 of model spend.

## Audience

Hiring managers / recruiters evaluating candidates for **AI/Agent Engineer**,
**LLM/ML Engineer**, **Full-stack AI**, and **AI Platform/Infra** roles. The three new
pillars map to those role signals:

- MCP + expanded tools → AI/Agent Engineer
- Memory + RAG → LLM/ML Engineer
- Observability + evals → AI Platform/Infra
- Existing React frontend → Full-stack AI

## Requirements

### Validated

<!-- Inferred from existing codebase (.planning/codebase/). Shipped and relied upon. -->

- ✓ ReAct agent loop via LangGraph 2-node StateGraph (agent_node ↔ tool_node) — existing
- ✓ Native OpenAI-compatible function calling (no text-parsing ReAct) — existing
- ✓ Tools: web_search (Tavily), python_executor (sandboxed subprocess), calculator — existing
- ✓ Multi-provider free-tier fallback (Gemini → Groq → GitHub Models) with usage tracking — existing
- ✓ Per-role provider preference (responder=Gemini, suggester=Groq) — existing
- ✓ SSE streaming of the live reasoning trace (Thought/Action/Observation/Final) — existing
- ✓ React + Vite frontend: chat workspace, reasoning panel, portfolio landing page — existing
- ✓ Conversation-aware prompt suggestions (degrades to static fallback) — existing
- ✓ Evaluation harness: task success + tool-selection accuracy vs. labelled dataset (100% baseline) — existing
- ✓ Security boundaries: subprocess isolation, AST validation, import whitelist, global secret redaction — existing
- ✓ Rate limiting (10 req/min/IP) and frontend session persistence (localStorage) — existing
- ✓ Deployed full-stack on Vercel (FastAPI backend + static frontend) — existing

### Active

<!-- New scope. Hypotheses until shipped and validated. Three pillars, sequenced. -->

- [ ] Persistence foundation: Supabase (Postgres + pgvector) as the shared backbone for memory, RAG, and trace storage
- [ ] Long-term memory keyed by anonymous session/thread id (no auth), persisted across sessions
- [ ] RAG over user-uploaded documents (ingestion + chunking + Gemini free embeddings + pgvector retrieval)
- [ ] Document upload + ingestion UI in the frontend
- [ ] Observability: persisted execution traces, an eval/trace dashboard, and free-tier quota/cost tracking surfaced in the UI
- [ ] MCP (Model Context Protocol) integration: agent consumes and/or exposes tools over MCP (HTTP/SSE transport, serverless-compatible)
- [ ] Free-tier resilience as a first-class feature: Supabase keep-alive (Vercel cron) + embedding rate-limit / batching handling

### Out of Scope

- Paid models / paid providers — $0 budget; free-tier operation is the core differentiator, not a fallback
- Multi-agent orchestration — easy to implement poorly, weak portfolio signal without a real use case; deliberately deferred
- Full user authentication — anonymous session id is sufficient for v1 memory; memory layer designed so auth can be added later
- Native mobile app — web-first; not relevant to the hiring signal

## Context

- **Stateless today.** Backend runs on Vercel serverless with an ephemeral filesystem and
  an in-memory trace store (last 100 runs). Memory and RAG therefore require an external
  persistence layer — this is the architectural driver for the Supabase decision.
- **Existing observability is partial.** Usage tracking (tokens, est. cost, provider, latency),
  an in-memory trace store, and the eval harness already exist. The observability pillar
  extends these (persistence + dashboard + quota), not greenfield.
- **Free-tier quota is the binding constraint** across every pillar. Embedding generation,
  inference, and DB activity all consume free quotas that must be respected and handled
  gracefully (batching, fallback, rate-limit awareness).
- The codebase favors explicit control flow, native tool calling, and visible reasoning as
  the primary UX differentiator. New work should preserve that ethos.
- Full codebase map available in `.planning/codebase/` (ARCHITECTURE, STACK, STRUCTURE,
  CONVENTIONS, INTEGRATIONS, CONCERNS, TESTING).

## Constraints

- **Budget**: $0 for models/infra — only free tiers (Gemini, Groq, GitHub Models, Supabase free, Vercel free) — portfolio project, no revenue.
- **Tech stack**: Python 3.11 / FastAPI / LangGraph backend; React 19 / Vite / TS frontend — extend, don't rewrite.
- **Platform**: Vercel serverless (ephemeral FS, no long-lived processes) — external persistence required; MCP must use HTTP/SSE transport (no stdio servers).
- **Persistence**: Supabase free tier pauses after ~7 days of inactivity — demo must stay reachable (keep-alive) and degrade gracefully if paused.
- **Quota**: Free embedding/inference rate limits — ingestion must batch and handle rate limits.
- **Audience time budget**: Recruiter evaluates in minutes — every feature must be legible quickly via README/live demo.

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| Supabase (Postgres + pgvector) as persistence backbone | Free tier; already connected; unifies memory + RAG + trace persistence in one service | — Pending |
| Ship all three pillars sequenced as a multi-phase roadmap | Pillars layer naturally (foundation → memory → RAG → observability → MCP); covers all target role signals | — Pending |
| RAG over user-uploaded documents | Most recognizable, "product-like" RAG demo; stronger signal than a fixed corpus | — Pending |
| Anonymous session/thread id for memory (no auth) | Delivers memory fast without auth surface; foundation designed to allow auth later | — Pending |
| Exclude multi-agent orchestration | Low signal-to-effort for portfolio; avoids shallow breadth | — Pending |
| Treat free-tier resilience as a first-class feature | Operating a resilient agent within free quotas is itself a seniority signal | — Pending |

## Evolution

This document evolves at phase transitions and milestone boundaries.

**After each phase transition** (via `/gsd-transition`):
1. Requirements invalidated? → Move to Out of Scope with reason
2. Requirements validated? → Move to Validated with phase reference
3. New requirements emerged? → Add to Active
4. Decisions to log? → Add to Key Decisions
5. "What This Is" still accurate? → Update if drifted

**After each milestone** (via `/gsd-complete-milestone`):
1. Full review of all sections
2. Core Value check — still the right priority?
3. Audit Out of Scope — reasons still valid?
4. Update Context with current state

---
*Last updated: 2026-06-28 after initialization*
