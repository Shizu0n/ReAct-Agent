# Feature Research

**Domain:** Portfolio AI agent — four new pillars (Memory, RAG, MCP, Observability)
**Researched:** 2026-06-28
**Confidence:** HIGH (architecture known, audience known, constraints known; no market uncertainty)

---

## Context and Framing

This file covers **only the four new pillars**. The existing system (ReAct loop, SSE streaming,
multi-provider fallback, eval harness) is already shipped and is not re-researched here.

**The defining constraint for all categorizations:** a recruiter evaluates the live demo in under
two minutes. Features that are invisible in the UI in that window — no matter how technically
sound — do not contribute to the portfolio signal. Every table-stakes and differentiator call
below is made through that lens.

**Audience signal map:**
- Long-term memory + RAG → LLM/ML Engineer signal
- MCP tooling → AI/Agent Engineer signal
- Observability/evals → AI Platform/Infra signal
- Frontend integration of all above → Full-stack AI signal

---

## Pillar 1: Long-term Memory (anonymous session/thread ID)

### Table Stakes

Features a recruiter or technical evaluator will expect if "memory" is claimed. Missing any of
these makes the memory feature look like a localStorage trick, not an agent capability.

| Feature | Why Expected | Complexity | Free-Tier Feasibility | Notes |
|---------|--------------|------------|----------------------|-------|
| Cross-session recall | Core promise of "memory" — the agent must remember facts stated in a *previous browser session*, not just within one tab | LOW-MEDIUM | HIGH — Supabase rows keyed by session ID | Session ID must be persisted in localStorage and sent to backend on every run |
| Agent references stored facts in responses | Memory only signals value when the agent *uses* it: "As you mentioned last time..." | LOW | HIGH — system prompt injection | Inject retrieved memories into the system prompt context window before LLM call |
| Memory write transparency in reasoning trace | The reasoning trace already shows tool calls — memory reads/writes should appear there too ("Memory stored: user prefers concise answers") | MEDIUM | HIGH | Treat memory read/write as pseudo-steps in the SSE stream; makes the pipeline legible |
| Session ID visible to user | Recruiter needs to know the mechanism — a visible "Session ID: abc123" (copyable) explains *how* cross-session memory works without auth | LOW | HIGH | Already have session ID concept in frontend; just surface it |
| Memory clear/reset | Without this, demo sessions pollute each other; also shows the system can manage state | LOW | HIGH — DELETE WHERE session_id = ... | Single button, no per-item management needed |

### Differentiators

| Feature | Portfolio Signal Value | Complexity | Free-Tier Feasibility | Notes |
|---------|----------------------|------------|----------------------|-------|
| Semantic memory retrieval (pgvector similarity) | Signals understanding that "memory" is a retrieval problem, not just a list — strongest LLM/ML signal in this pillar | MEDIUM | MEDIUM — requires embedding calls; Gemini free tier is rate-limited (15 RPM on gemini-embedding-004) | Store memories as vectors; retrieve by semantic similarity at query time. Batch writes to stay within rate limits |
| Memory type distinction (facts vs preferences vs conversation) | Shows design thinking: not all memories are equal | MEDIUM | HIGH — just a `memory_type` column | "User prefers metric units" (preference) vs "User is building a fintech app" (fact) — different retrieval weight |
| Memory retrieval shown as a ReAct step | Makes the invisible visible: "Thought: Let me check what I know about this user. Action: memory_read. Observation: User prefers Python 3.11..." | LOW — once memory_read is a tool | HIGH | Add `memory_read` to the tool registry; it will appear in the reasoning panel automatically |

### Anti-Features

| Feature | Why It Seems Good | Why to Avoid | Alternative |
|---------|-------------------|--------------|-------------|
| Per-memory editing UI | Transparency | High UI complexity, low recruiter legibility in 2 min | "Clear all" + show raw memory list as read-only |
| Memory importance scoring / automatic forgetting | Sophisticated | Hard to demo correctly; fails silently when wrong memories are kept | Simple recency + count-based relevance; keep last N memories |
| Auth-gated memory (user accounts) | "Real" product | PROJECT.md explicitly excludes auth; adds auth complexity with zero portfolio benefit over session ID | Session ID in localStorage — explain this is intentional and auth-upgradable |
| Memory summarization (compress old memories) | Handles memory growth | Adds an LLM call just for housekeeping; burns quota | Cap at 50 memories per session; evict oldest |

### Complexity Budget

The table-stakes set is a single Supabase table (`memories`) with columns `(session_id, content,
embedding, memory_type, created_at)` plus a `memory_read` tool. The embedding-based retrieval is
the only meaningful complexity spike. Entire pillar is buildable in one focused phase.

---

## Pillar 2: RAG over Uploaded Documents

### Table Stakes

These are non-negotiable for the demo to read as "RAG" rather than "document stuffing":

| Feature | Why Expected | Complexity | Free-Tier Feasibility | Notes |
|---------|--------------|------------|----------------------|-------|
| File upload UI (PDF + plain text minimum) | Entry point to the whole feature — if a recruiter can't upload something, they can't evaluate RAG | LOW | HIGH — standard HTML file input + Supabase Storage (1 GB free) | Drag-and-drop is differentiating; basic file input is table stakes |
| Ingestion progress feedback | Chunking + embedding takes 3–30 seconds; a blank UI looks broken | LOW | HIGH — SSE or polling endpoint | Show: "Extracting text... Chunking (12 chunks)... Embedding... Done." Transparency is the differentiator |
| Document list (what's been uploaded) | User needs to know the agent has context; recruiter needs to see the state of the system | LOW | HIGH — query Supabase | Per session, show uploaded doc names + chunk count |
| Query over uploaded document, get answer | The actual RAG loop — retrieve → inject → respond | MEDIUM | MEDIUM — rate-limited embedding on query side too | This is the core feature; must work reliably |
| Source citations in response | Without citations, RAG looks like hallucination. "According to [document] (chunk 3)..." is the credibility marker | MEDIUM | HIGH — return chunk metadata alongside answer | Citations are what distinguish RAG from "I read the doc" — non-negotiable |

### Differentiators

| Feature | Portfolio Signal Value | Complexity | Free-Tier Feasibility | Notes |
|---------|----------------------|------------|----------------------|-------|
| Retrieval step in reasoning trace | Shows the *mechanism*, not just the output — "Action: document_search. Query: 'payment terms'. Observation: Retrieved 3 chunks from contract.pdf." | LOW once tool is registered | HIGH | Add `document_search` to the tool registry; it appears in ReasoningPanel automatically. Strongest single differentiator for LLM/ML signal |
| Chunk-level citation with similarity score | "Source: contract.pdf, chunk 4 (similarity: 0.87)" — signals you understand vector retrieval semantics | MEDIUM | HIGH — pgvector returns cosine distance | Include similarity score in citation metadata surfaced in UI |
| Multi-document querying | Search across all uploaded docs, not just one — recruiter can upload two documents and ask a cross-document question | LOW — already multi-doc if stored in same table | HIGH | Just filter by session_id, not doc_id — trivially multi-doc |
| Ingestion pipeline stats in UI | Show chunk count, embedding model used, avg chunk length — makes the pipeline legible to a technical evaluator in seconds | LOW | HIGH | Surface in document list panel |
| "Not found in documents" graceful handling | When the answer isn't in the uploaded docs, the agent should say so rather than hallucinate — shows awareness of RAG failure modes | LOW — system prompt instruction | HIGH | Instruction in system prompt: "If the retrieved chunks do not answer the question, say so explicitly" |

### What Makes RAG Look Credible vs Naive

**Credible RAG signals (do these):**
- Retrieval step visible in reasoning trace (not a black box)
- Citations with chunk origin and similarity score
- Chunking strategy stated (e.g., "512 tokens, 50-token overlap") in the ingestion feedback
- Graceful "not in document" response
- Ingestion rate-limit handling shown (batch embedding with delay, not fire-and-forget)

**Naive RAG signals (avoid these):**
- Stuffing the whole document into the system prompt (fails on any doc > 4K tokens)
- Citations that are just the filename with no chunk reference
- Embedding done synchronously in the HTTP handler (times out on long docs)
- No feedback during ingestion (blank UI for 15 seconds)
- Hallucinated answers when the document doesn't contain the answer

### Anti-Features

| Feature | Why It Seems Good | Why to Avoid | Alternative |
|---------|-------------------|--------------|-------------|
| OCR for scanned PDFs | Handles real-world docs | High complexity (Tesseract/cloud OCR), adds 200+ ms per page | Accept text-layer PDFs only; state clearly in UI "Text PDFs supported" |
| Reranking with cross-encoder | Improves retrieval quality | Additional model call, complex to explain, marginal demo benefit | Good chunking + pgvector similarity is sufficient for a portfolio demo |
| Web URL ingestion ("paste a URL") | Expands demo range | Requires scraping pipeline (robots.txt, JS rendering); scope creep | File upload only for v1 |
| Persistent cross-session documents (global corpus) | Richer retrieval | Conflates sessions, raises storage concerns | Session-scoped documents only; recruiter uploads fresh each demo |
| Fine-grained chunk editing | Advanced | No recruiter evaluates this; very high UI cost | Read-only chunk inspection in document list is sufficient |

### Complexity Budget

Two Supabase tables (`documents`, `chunks`), pypdf for extraction, Gemini free embeddings with
batching, pgvector for similarity search, a `document_search` tool in the agent registry. The
ingestion endpoint is the only genuinely hard part (rate-limit-aware batching). Everything else
follows existing patterns in the codebase.

---

## Pillar 3: MCP Tooling

### What "MCP-Native Agent" Means in Practice

Model Context Protocol (MCP) is a JSON-RPC 2.0 protocol for tool/resource discovery between
agents and tool servers. Two directions:

- **Consuming external MCP servers:** the agent acts as an MCP *client*, connects to a server,
  discovers its tools, and calls them during the ReAct loop.
- **Exposing own tools as an MCP server:** the agent acts as an MCP *server*, making its tools
  (web_search, python_executor, etc.) available to other agents.

**Critical constraint:** Vercel serverless means no long-lived processes — stdio transport (used
by most public MCP servers) is impossible. Only HTTP/SSE transport works.

**Which direction is more impressive for portfolio?**
Consuming is more legible in 2 minutes: a recruiter can see a tool call in the reasoning trace
and the README can link to the external MCP server. Exposing is deeper technically but requires
a second client to demo, which is invisible to a recruiter looking at the live demo.

**Recommendation:** Implement consuming first. Build a minimal HTTP/SSE MCP server as a companion
Vercel function (same repo) that exposes 1–2 tools — this demonstrates *both* directions without
requiring an external client.

### Table Stakes

| Feature | Why Expected | Complexity | Free-Tier Feasibility | Notes |
|---------|--------------|------------|----------------------|-------|
| At least one MCP server consumed end-to-end | The claim "MCP integration" requires proof — one working tool call from an MCP server through the agent is the minimum | MEDIUM | HIGH — Python MCP SDK + HTTP/SSE transport | Use the official `mcp` Python package. Deploy a companion MCP server as a Vercel function in the same repo |
| MCP tool calls visible in reasoning trace | MCP tool calls must look identical to native tool calls in the reasoning panel — the trace *is* the demo | LOW once plumbed | HIGH | MCP tools registered in TOOL_SCHEMAS alongside native tools; tool_node handles them the same way |
| README explains MCP architecture clearly | Technical evaluators will read this; vague "supports MCP" is worthless | LOW | HIGH | Diagram: agent ↔ MCP client ↔ HTTP/SSE ↔ MCP server (Vercel function) |
| At least one meaningful MCP tool (not a toy echo) | A "hello world" MCP tool signals you read a tutorial; a real tool signals engineering judgment | MEDIUM | HIGH | Good candidate: a "calculator" or "unit converter" MCP server that wraps an external API the existing tools don't cover |

### Differentiators

| Feature | Portfolio Signal Value | Complexity | Free-Tier Feasibility | Notes |
|---------|----------------------|------------|----------------------|-------|
| Bidirectional MCP (consume + expose) | Shows protocol understanding at both ends — strongest AI/Agent signal in this pillar | HIGH | MEDIUM — exposing requires implementing MCP server spec correctly | Expose existing tools (web_search, python_executor) as an MCP server endpoint; another agent could consume them |
| Dynamic tool discovery (capability negotiation) | Shows you understand that MCP tools are discovered at runtime, not hardcoded | MEDIUM | HIGH — part of MCP spec | On startup, agent queries the MCP server for its `tools/list` and registers them dynamically |
| MCP server health shown in observability dashboard | Shows operational thinking about external dependencies | LOW | HIGH | "MCP server: online/offline" in the provider health panel |
| Connection to a real public MCP server (if one is HTTP/SSE-compatible) | Shows ecosystem awareness | MEDIUM | MEDIUM — most public MCP servers use stdio | If a public server with HTTP transport exists, connecting to it > connecting to your own server |

### Anti-Features

| Feature | Why It Seems Good | Why to Avoid | Alternative |
|---------|-------------------|--------------|-------------|
| stdio transport MCP servers | Broader compatibility | Impossible on Vercel serverless — any stdio server will hang or crash | HTTP/SSE only; document this constraint explicitly in README as an engineering decision |
| Building MCP protocol from scratch | Shows protocol knowledge | The official `mcp` Python SDK exists and is maintained by Anthropic; not using it looks like NIH syndrome | Use `mcp` package; understand the spec, don't reimplement it |
| MCP resource/prompt primitives (beyond tools) | Full protocol coverage | Resources and prompts add significant complexity with minimal demo legibility | Tools only for v1 |
| Multi-server MCP routing (agent picks which MCP server) | Advanced orchestration | Needs a dispatcher layer; looks like multi-agent which is explicitly out of scope | Single MCP server consumed; agent treats all tools uniformly |

### Complexity Budget

The MCP pillar is the most novel and the most likely to have unexpected complexity (protocol
edge cases, session management, JSON-RPC framing). Budget extra time here. The companion Vercel
function MCP server is small but must correctly implement the MCP handshake (`initialize`,
`tools/list`, `tools/call`). Use the official Python SDK to avoid protocol bugs.

---

## Pillar 4: Observability / Evals

### Table Stakes

The existing system has partial observability (in-memory trace store, usage tracking per run,
eval harness with About page). Table stakes here means *persistence* and *visibility* — moving
from ephemeral to durable.

| Feature | Why Expected | Complexity | Free-Tier Feasibility | Notes |
|---------|--------------|------------|----------------------|-------|
| Persistent trace storage | The in-memory store (last 100 runs) is lost on every cold start. A recruiter who runs two queries and checks the trace view should see both. | LOW | HIGH — write AgentResponse to Supabase on run completion | Schema is already defined by the existing Step TypedDict |
| Trace detail view in UI | "Traces" as a concept means clickable run history with per-step expansion | MEDIUM | HIGH | Tab or panel: list of runs → click → full step-by-step trace |
| Per-step latency shown | elapsed_ms already exists in Step — surfacing it in the trace view is low effort, high signal | LOW | HIGH | Already tracked in Step TypedDict |
| Provider used per run (and fallback events) | Shows the multi-provider fallback *worked* — a recruiter can see "Run 1: Gemini, Run 2: Groq (Gemini failed)" | LOW | HIGH — add provider field to stored trace | Strong Platform/Infra signal |
| Eval results in UI (already partial) | The About page already surfaces baseline.json — the table-stakes version ensures it reflects the current baseline, not a stale snapshot | LOW | HIGH | Ensure /evals endpoint serves fresh data; consider a "run evals" button |

### Differentiators

| Feature | Portfolio Signal Value | Complexity | Free-Tier Feasibility | Notes |
|---------|----------------------|------------|----------------------|-------|
| Free-tier quota visualization | Shows cost/quota awareness — the single strongest Platform/Infra signal in this pillar | MEDIUM | HIGH — count tokens in Supabase, compare to known free limits | Bar chart: "Gemini: 847 / 1500 daily tokens (56%)" — makes the constraint visible and legible |
| Provider health / fallback timeline | Visual history of which provider served each request and when fallbacks triggered — shows reliability engineering thinking | MEDIUM | MEDIUM — requires storing provider_used and fallback_attempted per run | Timeline: "Last 10 runs: G G G [Groq fallback] G G..." |
| Eval trend over time (multiple baseline snapshots) | Shows the system is measured over time, not just point-in-time — strongest seniority signal in this pillar | HIGH | MEDIUM — store eval run results in Supabase with timestamps | Line chart: task success % over last 5 eval runs. Requires storing eval history, not just current baseline |
| Token cost estimation displayed per run | "This query cost ~0.003 USD equivalent (free tier)" — makes cost-awareness tangible | LOW | HIGH — already estimated in UsageTracker | Surface in run summary / telemetry strip |
| Rate-limit event logging | When a rate limit fires, log it as a trace event — "Gemini rate limited, falling back to Groq (attempt 2)" | MEDIUM | MEDIUM | Extend FreeModelFallback to emit a structured rate-limit event; store it in the trace |

### What Signals Seniority to an Infra/Platform Evaluator

**Does signal seniority:**
- Quota dashboards that compare usage to known free-tier limits (shows operational awareness)
- Eval trend over time (shows you measure your systems, not just build them)
- Provider fallback events in trace (shows reliability engineering, not just happy-path thinking)
- Cost-per-run estimation even at $0 (shows cost modeling is a habit)
- Graceful degradation when Supabase is paused (keep-alive + offline fallback)

**Does not signal seniority (looks junior):**
- Raw log dumps as "observability"
- A single static eval score with no trend
- Metrics that only exist in the README, not the live UI
- Tracing that only covers the final answer, not intermediate steps

### Anti-Features

| Feature | Why It Seems Good | Why to Avoid | Alternative |
|---------|-------------------|--------------|-------------|
| OpenTelemetry full instrumentation | Industry standard | Complex setup, high dependency weight, minimal demo legibility vs custom traces | Custom trace schema in Supabase; same data, simpler | 
| External APM (Sentry, Datadog) | Production-grade | Paid beyond free tiers; adds external dependency for what's already custom-built | Keep traces in Supabase; custom dashboard in frontend |
| Alerting / PagerDuty | Operational maturity | Nobody pages for a portfolio demo; signals wrong scope | Provider health indicator in UI is sufficient |
| A/B testing framework | Advanced experimentation | Requires traffic splitting infrastructure; zero recruiter legibility | Eval harness with labeled dataset is the right comparison mechanism |
| Distributed tracing across services | Microservices pattern | Single-service app; distributed tracing adds noise | Linear per-run trace with step-level detail is appropriate |
| Real-time metrics WebSocket | Fancy | SSE already used for run streaming; adding WS just for metrics adds a second connection | Polling the /metrics endpoint every 30s is sufficient for a dashboard |

---

## Cross-Pillar Feature Dependencies

```
Supabase connection (persistent)
    ├──required by──> Memory: session-keyed rows + pgvector
    ├──required by──> RAG: document/chunk storage + pgvector
    └──required by──> Observability: trace persistence + eval history

pgvector extension (Supabase)
    ├──required by──> Memory: semantic recall
    └──required by──> RAG: chunk retrieval

Gemini free embeddings (embedding-004)
    ├──required by──> Memory (if semantic retrieval used)
    └──required by──> RAG (chunk embedding)
    Note: shared rate-limit budget (15 RPM free) — ingestion and memory writes must coordinate

Document upload UI
    └──required by──> RAG (no RAG without documents)

Trace persistence (Supabase)
    └──enhances──> Observability: makes trace history possible
    └──enhances──> Eval trend: stores eval run history

MCP server (companion Vercel function)
    └──required by──> MCP consuming: need a server to connect to

Memory pillar
    └──enhances──> RAG: combined "what I know about you" + "what's in your documents"
    Note: this combination is a Phase 2+ enhancement, not v1

Rate-limit handling (shared concern)
    ├──required by──> RAG (ingestion batching)
    └──required by──> Memory (embedding writes)
```

### Dependency Notes

- **Supabase must be provisioned before Memory, RAG, or Observability.** The keep-alive Vercel
  cron (to prevent 7-day pause) is also a prerequisite for demo reliability.
- **pgvector must be enabled** in the Supabase project before either Memory or RAG can use
  vector similarity. One-time setup step.
- **Gemini embedding rate limit is shared** between Memory writes and RAG ingestion. Simultaneous
  ingestion + memory writes during a demo could hit 15 RPM. Design both to queue/batch.
- **MCP has no dependencies on Memory, RAG, or Observability.** It can be built in parallel or
  after the Supabase pillars if quota is a concern.
- **Observability's trace persistence depends only on Supabase** (same connection as Memory/RAG),
  not on Memory or RAG being complete.

---

## Feature Prioritization Matrix

Ordered by portfolio signal value relative to implementation cost, given the 2-minute recruiter
evaluation window.

| Feature | Pillar | Portfolio Signal | Implementation Cost | Priority |
|---------|--------|-----------------|---------------------|----------|
| Supabase persistence foundation | Infra | HIGH (enables all pillars) | LOW (config, schema) | P1 |
| Cross-session recall with agent reference | Memory | HIGH | LOW-MEDIUM | P1 |
| Ingestion pipeline with progress feedback | RAG | HIGH | MEDIUM | P1 |
| Source citations in RAG responses | RAG | HIGH | MEDIUM | P1 |
| Retrieval step in reasoning trace (both pillars) | Memory + RAG | HIGH | LOW (tool registration) | P1 |
| Persistent trace history + detail view | Observability | HIGH | MEDIUM | P1 |
| Provider used + fallback events in trace | Observability | HIGH | LOW | P1 |
| MCP tool call visible in reasoning trace | MCP | HIGH | MEDIUM | P1 |
| Session ID visible in UI | Memory | MEDIUM | LOW | P1 |
| Document list with ingestion stats | RAG | MEDIUM | LOW | P1 |
| Semantic memory retrieval (pgvector) | Memory | HIGH | MEDIUM | P2 |
| Quota visualization dashboard | Observability | HIGH | MEDIUM | P2 |
| Eval trend over time | Observability | HIGH | MEDIUM | P2 |
| Chunk-level citations with similarity score | RAG | MEDIUM | LOW | P2 |
| MCP bidirectional (expose own tools) | MCP | HIGH | HIGH | P2 |
| Memory type distinction | Memory | MEDIUM | LOW | P2 |
| Memory clear/reset | Memory | LOW | LOW | P2 |
| MCP dynamic tool discovery | MCP | MEDIUM | MEDIUM | P2 |
| Supabase keep-alive (Vercel cron) | Infra | HIGH (reliability) | LOW | P1 |
| Rate-limit event logging | Observability | MEDIUM | MEDIUM | P3 |
| Provider health timeline | Observability | MEDIUM | MEDIUM | P3 |
| "Not in document" graceful handling | RAG | MEDIUM | LOW | P2 |
| MCP server health in dashboard | MCP | LOW | LOW | P3 |

**Priority key:**
- P1: Must have — recruiter sees a broken or missing feature without it
- P2: Should have — differentiates from a junior implementation
- P3: Nice to have — adds depth but not legible in 2-minute evaluation

---

## MVP Recommendation Per Pillar

### Memory MVP (v1)
- Supabase `memories` table with session_id key
- `memory_read` and `memory_write` as registered agent tools (appear in reasoning trace)
- Agent references retrieved memories in responses
- Session ID visible in UI
- Memory clear button
- Defer: semantic/vector retrieval until v1.x (ship recency-based retrieval first)

### RAG MVP (v1)
- File upload (PDF + .txt) → text extraction → chunking → Gemini embedding → pgvector storage
- Ingestion progress shown in UI (chunk count, status)
- Document list per session
- `document_search` tool in agent registry
- Source citations in response (filename + chunk index)
- Defer: similarity scores in UI, multi-format support, drag-and-drop

### MCP MVP (v1)
- Companion MCP server (Vercel function, HTTP/SSE transport) with 1–2 real tools
- Agent connects to it on startup via HTTP/SSE MCP client
- Tools discovered dynamically, registered in TOOL_SCHEMAS
- Tool calls visible in reasoning trace
- README documents the architecture
- Defer: bidirectional (expose as MCP server) until v1.x

### Observability MVP (v1)
- Write completed runs to Supabase (AgentResponse schema)
- Trace history list in UI (last 20 runs, clickable)
- Trace detail view: per-step with elapsed_ms
- Provider used per run displayed
- Keep-alive Vercel cron for Supabase
- Defer: quota visualization, eval trend charts until v1.x

---

## Sources

Findings derived from:
- Existing codebase map (`.planning/codebase/ARCHITECTURE.md`, `STACK.md`)
- Project requirements (`.planning/PROJECT.md`)
- Domain knowledge: MCP spec (Anthropic, 2024–2025), pgvector patterns, Supabase free-tier limits,
  Gemini embedding-004 rate limits (15 RPM free tier), Vercel serverless constraints
- Portfolio evaluation heuristics: AI/Agent Engineer, LLM/ML Engineer, Platform/Infra hiring patterns

---

*Feature research for: ReAct Agent portfolio — Memory, RAG, MCP, Observability pillars*
*Researched: 2026-06-28*
