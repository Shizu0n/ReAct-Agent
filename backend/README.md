# ReAct Agent Backend

API FastAPI para um agente ReAct com LangGraph, modelos free/freemium configuraveis, ferramentas controladas e trace auditavel por run.

![Python 3.11](https://img.shields.io/badge/Python-3.11-blue)
![FastAPI](https://img.shields.io/badge/FastAPI-0.115.4-009688)
![LangGraph](https://img.shields.io/badge/LangGraph-0.2.45-purple)
![Railway](https://img.shields.io/badge/Railway-ready-black)

## Architecture

```text
User Query -> [Agent Node: LLM Reasoning]
                    |
                    v
              Thought + Action
                    |
                    v
             [Tool Node: Execute Tool]
                    |
                    v
                Observation
                    |
                    v
          [Agent Node: LLM Reasoning]
                    |
                    v
          ... (max 10 iterations)
                    |
                    v
          [Final Answer] -> User
```

Antes de montar o grafo, a API tenta um fast path local para tarefas deterministicas simples: aritmetica, juros compostos e estatistica basica com lista explicita. Quando bate, a resposta preserva `trace/steps`, mas nao chama nenhum provedor de LLM.

`agent_node` chama o LLM com o `SYSTEM_PROMPT`, interpreta a resposta no formato ReAct e registra `Thought`, `Action`, `Action Input` ou `Final Answer`.

`tool_node` executa a ferramenta escolhida, cria um `Step` com `thought`, `action`, `action_input`, `observation` e `timestamp`, depois incrementa `iteration_count`.

`should_continue` e o router do grafo: manda para `tool_node` quando existe `Action`, encerra quando existe `Final Answer`, e levanta `MaxIterationsError` ao atingir 10 iteracoes. Sem isso, agente ruim vira while loop com autoestima.

## Tools

| Tool | Description | API |
| --- | --- | --- |
| `web_search` | Busca web via Tavily e retorna resultados compactos com titulo, URL e snippet truncado. Defaults: `TAVILY_MAX_RESULTS=2`, `TAVILY_SNIPPET_CHARS=360`. | Tavily API (`TAVILY_API_KEY`) |
| `python_executor` | Executa `exec()` com globals restritos a `math`, `json`, `re` e `print`, capturando stdout. | Local Python sandbox leve |
| `calculator` | Avalia expressoes matematicas com `eval()` sem builtins e com validacao AST. | Local `math` module |

## Model Providers

O agente nao usa OpenAI nem Anthropic. A cadeia default usa apenas provedores configurados no `.env`, nesta ordem:

1. `GEMINI_API_KEY` com `GEMINI_MODEL`, default `gemini-2.5-flash`
2. `GROQ_API_KEY` com `GROQ_MODEL`, default `llama-3.3-70b-versatile`
3. `GITHUB_MODELS_TOKEN` + `GITHUB_MODELS_MODEL`
4. `OPENROUTER_API_KEY` com `OPENROUTER_MODEL`, default `meta-llama/llama-3.1-8b-instruct:free`
5. `CF_ACCOUNT_ID` + `CF_WORKERS_AI_TOKEN` com `CF_WORKERS_AI_MODEL`, default `@cf/meta/llama-3-8b-instruct`

Esses provedores podem ter quotas, termos e limites proprios. Para custo zero absoluto, rode um modelo local e adapte `agent/llms.py`; API cloud gratuita ainda e API cloud, nao milagre contratual.

## Quick Start

```bash
git clone <repo-url> && cd 01-react-agent/backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env  # fill keys
python main.py
```

## API Usage

Sync run:

```bash
curl -X POST http://localhost:8000/agent/invoke \
  -H "Content-Type: application/json" \
  -d '{"query":"Calculate 12 * 8 + 5","stream":false}'
```

Streaming run:

```bash
curl -N -X POST http://localhost:8000/agent/invoke \
  -H "Content-Type: application/json" \
  -d '{"query":"Use Python to compute 6!, then divide it by 9","stream":true}'
```

Trace lookup:

```bash
curl http://localhost:8000/trace/<run_id>
```

Streaming emits SSE payloads in this shape:

```json
{"type":"thought|action|observation|final","content":"...","step":1}
```

## Problem

LLM agents usually fail in the boring places: invisible reasoning, unbounded loops, mixed tool side effects, and APIs that return only the final answer. That is cute in a demo and radioactive in anything operational.

## Solution

This project wraps a ReAct loop in LangGraph, exposes it through FastAPI, and stores the last 100 runs in memory for trace lookup. `/agent/invoke` is the portfolio-facing endpoint, `/run` remains as a backward-compatible alias, `/health` lists available tools, and `/trace/{run_id}` returns the stored `AgentResponse`.

## Why This Solves It

LangGraph makes control flow explicit: reason, route, execute tool, observe, repeat, stop. Each tool call becomes a `Step`, so debugging is not archaeology. SSE exposes progress while the run is happening, which matters when a user needs to see whether the agent is thinking, acting, or stuck writing fanfic about acting.

## Metrics

| Metric | Value |
| --- | --- |
| Max ReAct iterations | `10` |
| Stored traces | Last `100` runs |
| Rate limit | `10 req/min/IP` |
| Local shortcuts | Arithmetic, compound growth, basic statistics |
| Web search context | `2` results, `360` chars per snippet by default |
| Tools available | `3` |
| API modes | Sync JSON + SSE streaming |
| Test coverage in repo | Unit tests for tools, graph flow, health, run, stream, and trace |

## Key Decisions

**Why LangGraph over AgentExecutor:** LangGraph gives explicit nodes, router logic, state transitions, and a hard iteration boundary. `AgentExecutor` is convenient, but the control flow is more implicit. Implicit agent control flow is how debugging becomes interpretive dance.

**Why SSE:** The agent already produces sequential events: thought, action, observation, final. SSE maps to that shape without WebSocket ceremony. One request, ordered events, easy `curl -N`, done.

**How MaxIterationsError works:** `should_continue` checks `iteration_count` before routing back into tools. At `10`, it raises `MaxIterationsError` instead of letting the loop continue. This makes runaway reasoning fail loudly instead of charging rent in your process.

## What I Learned

- Version pins matter: `sse-starlette` latest pulled an incompatible `starlette`, so the dependency tree needed a real compatibility check.
- Streaming is only useful when each intermediate state is structured; otherwise it is just logs wearing a blazer.
- A ReAct agent without trace storage is a debugging trap. The final answer alone is not evidence; it is a press release.
