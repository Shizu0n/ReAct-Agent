# Coding Conventions

**Analysis Date:** 2026-06-29

## Naming Patterns

### Python

**Files:**
- Test files: `test_*.py` (e.g., `backend/tests/test_agent.py`, `backend/tests/test_api.py`)
- Modules: `snake_case.py` (e.g., `backend/agent/tools.py`, `backend/agent/graph.py`)
- Packages: lowercase (e.g., `agent/`, `evals/`)

**Functions:**
- Public: `snake_case` (e.g., `normalize_python_code_input`, `configured_model_info`)
- Private/internal: leading underscore + `snake_case` (e.g., `_last_user_message`, `_strip_executor_status_annotations`, `_safe_exception_message`)
- Const patterns: UPPER_SNAKE_CASE (e.g., `MAX_ITERATIONS`, `DEFAULT_TAVILY_MAX_RESULTS`, `WEB_SEARCH_GATE_DISABLE_ENV`)

**Classes:**
- Public: `PascalCase` (e.g., `FreeModelFallback`, `MaxIterationsError`, `SecretRedactionTests`)
- Private/internal: leading underscore + `PascalCase` (e.g., `_PythonExecutorValidator`)
- Test classes: `<Feature>Tests` suffix (e.g., `ToolTests`, `SecretRedactionTests`, `LlmSelectionTests`)

**Type Aliases:**
- `PascalCase` (e.g., `ProviderCall = Callable[[...], AIMessage]`)

**Variables:**
- Local scope: `snake_case`
- Instance/module scope: `snake_case`

### TypeScript/JavaScript

**Files:**
- Components: `PascalCase.tsx` (e.g., `App.tsx`, `ChatWorkspace.tsx`)
- Hooks: `use<Name>.ts` (e.g., `useAgent.ts`)
- Types: `index.ts` (located in `types/` directory)
- Utilities: `snake_case.ts`

**Functions:**
- Regular: `camelCase` (e.g., `submitQuery`, `toggleReasoningTrace`, `timestamp`)
- Event handlers: `handle<Action>` prefix (e.g., `handleTraceOpenChange`, `handleMobileTraceOpenChange`, `handlePointerMove`, `stopResize`)
- Helper utilities: `camelCase` (e.g., `readShellState`, `writeShellState`, `isRecord`, `persistedMessages`)

**Components:**
- `PascalCase` (e.g., `App`, `ChatWorkspace`, `ChatPanel`, `ReasoningPanel`)

**Types and Interfaces:**
- All public types: `PascalCase` (e.g., `StepType`, `ActiveTab`, `TraceOpenUpdate`, `PersistedShellState`)
- Interfaces: `PascalCase` (e.g., `Usage`, `Step`, `AgentResponse`, `Message`, `RunSummary`, `AgentState`, `ModelInfo`, `AgentConfig`)
- Type unions: `camelCase` or literal strings in discriminated unions

**Variables and Constants:**
- Local/state variables: `camelCase` (e.g., `sidebarOpen`, `setSidebarOpen`, `leftSidebarWidth`)
- Module-level constants: `UPPER_SNAKE_CASE` (e.g., `LEFT_SIDEBAR_MIN`, `LEFT_SIDEBAR_MAX`, `LEFT_SIDEBAR_DEFAULT`)
- Const objects (non-global): `camelCase` (e.g., `navItems`, `loadingLabels`, `fallbackSuggestions`)

## Code Style

**Formatting:**
- Python: No Prettier/Black config found; follows PEP 8 conventions (observed in source)
- TypeScript: No Prettier config found; ESLint enforces formatting
- Line length: Not explicitly constrained (Python files range 80–120 chars)

**Linting:**

Python:
- No explicit linter config found (no `pylintrc`, `setup.cfg`, `.flake8`)
- Source code follows PEP 8: 4-space indentation, snake_case, docstrings on public functions

TypeScript:
- ESLint (`frontend/eslint.config.js`)
- Extends: `@eslint/js` recommended, `typescript-eslint` recommended, `react-hooks`, `react-refresh`
- Config: flat config style (ESLint v9 compatible)
- No TypeScript strict mode enforced in config, but `tsconfig.json` likely strict (not inspected)

## Import Organization

**Python order:**
1. `__future__` annotations (if using forward refs)
2. Standard library (`import os`, `import re`, `import asyncio`, etc.)
3. Third-party (`from langchain_core.messages import ...`, `from pydantic import ...`)
4. Local relative imports (`from agent.graph import ...`, `from agent.state import ...`)

Example from `backend/api.py`:
```python
from __future__ import annotations

import asyncio
import json
import logging
import time
import uuid
from collections import deque
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, AsyncIterator, Literal

from fastapi import FastAPI, HTTPException, Request
from pydantic import BaseModel, Field

from agent.graph import TOOLS, build_graph
```

**TypeScript order:**
1. React imports (`import { useState } from 'react'`)
2. Type imports (`import type { ... } from 'react'`)
3. Third-party imports (`import { Code2, ExternalLink } from 'lucide-react'`)
4. Local imports (relative, e.g., `from './components/...'`, `from './hooks/...'`)
5. Type imports from local (`import type { AgentState } from '../types'`)

Example from `frontend/src/App.tsx`:
```typescript
import { useState } from 'react'
import type { CSSProperties, PointerEvent as ReactPointerEvent } from 'react'
import { Code2, ExternalLink, Info, Menu, X } from 'lucide-react'
import { ChatWorkspace } from './components/ChatWorkspace'
import { useAgent } from './hooks/useAgent'
```

**Path Aliases:**
- Python: Relative to package root; `backend/` is inserted to `sys.path` (see `api/index.py`), so `from agent.graph import ...` works from anywhere
- TypeScript: No path aliases configured (uses relative `./` and `../` paths)

## Error Handling

**Python patterns:**

Custom exceptions:
- Define as classes inheriting from `Exception` (e.g., `MaxIterationsError` in `backend/agent/state.py`)
- Raised explicitly with descriptive messages

Exception handling in API:
- `try`/`except` in streaming (e.g., `backend/api.py` lines 259–297)
- `HTTPException` from FastAPI for API-level errors
- Graceful degradation: Fall back to safe defaults (e.g., suggestions fallback to static list)
- Secrets redaction on exception messages (via `redact_secrets` in all error logs)

Example from `backend/api.py` (`_stream_agent`):
```python
try:
    graph = build_graph(tracker=tracker)
    for state in graph.stream(...):
        ...
except MaxIterationsError:
    # Handle max iterations, yield error event
    ...
```

**TypeScript patterns:**

Null coalescing and optional chaining:
- Null checks in render (e.g., `state.config?.active_model`)
- Fallback values: `value || defaultValue`
- Array checks: `if (!Array.isArray(value)) return []`

Type guards:
- `isRecord(value): value is Record<string, unknown>` – validates objects
- `persistedMessages(value): Message[]` – filters and validates arrays
- Used before JSON parsing and localStorage reads

Error display:
- UI state tracks `error: string | null` in `AgentState`
- Connection states include `'error'` (in `connectionStatus`)
- No throw statements in frontend; errors are stored in state and displayed

Example from `frontend/src/hooks/useAgent.ts`:
```typescript
function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null
}

function persistedMessages(value: unknown): Message[] {
  if (!Array.isArray(value)) return []
  return value.filter((message): message is Message => {
    if (!isRecord(message)) return false
    return (
      typeof message.id === 'string' &&
      (message.role === 'user' || message.role === 'assistant') &&
      typeof message.content === 'string'
    )
  })
}
```

## Logging

**Python framework:**
- Standard `logging` module
- Logger names follow module paths: `logger = logging.getLogger("react_agent.api")`
- Log levels:
  - `logger.info()` for request/response and milestone events (line 114 in `backend/api.py`)
  - `logger.exception()` for error context (line 107)
  - `logger.warning()` quieted for noisy loggers (httpx, uvicorn.access)
- Secrets redaction: All log records are scrubbed at the logging level via `configure_secure_logging()` (called once at startup)

Example from `backend/api.py`:
```python
logger = logging.getLogger("react_agent.api")
logger.info(
    "%s %s -> %s %.4fs",
    request.method,
    request.url.path,
    response.status_code,
    elapsed,
)
```

**TypeScript:**
- No logging framework observed (no winston, pino, etc.)
- Console usage is absent (no `console.log` in production code)
- Only browser APIs and error state management used for debugging

## Comments

**When to comment:**

Python:
- Complex algorithms: e.g., `_normalize_flattened_python_code` (complex regex replacements)
- Non-obvious intent: e.g., "Year mentions only count as a current-fact signal in temporal phrasing" (line 124 in `backend/agent/graph.py`)
- Design decisions: e.g., tool schema descriptions (lines 43–115)
- Invariants: e.g., "OpenAI-style tool schemas" (line 43)

TypeScript:
- Sparse; code is largely self-documenting (short, clear function names and types)
- Comments only on non-obvious behavior (e.g., localStorage fallback, mock mode detection)

Example from `backend/agent/graph.py`:
```python
# OpenAI-style tool schemas. The descriptions are deliberately directive: tool
# selection is driven by these strings, so they tell the model to call the tool
# rather than reason the answer out itself.
TOOL_SCHEMAS = [...]
```

**JSDoc/TSDoc:**
- Not used in frontend (no `/**` docstrings)
- Not used in Python backend (no docstrings except for tool functions)
- Type signatures are sufficient for clarity

## Function Design

**Size:**
- Typical Python functions: 10–30 lines (e.g., `_initial_state`, `_store_response`)
- Larger: Complex tools validation (e.g., `normalize_python_code_input` ~40 lines)
- TypeScript event handlers: 5–15 lines (e.g., `submitQuery`, `toggleReasoningTrace`)
- Larger: Component render or effects (e.g., `ChatWorkspace` – ~250 lines for full JSX)

**Parameters:**
- Python: Explicit parameters, type hints (e.g., `def _initial_state(query: str, history: list[ChatMessageRequest] | None = None)`)
- TypeScript: Props destructured, types via interface (e.g., `function ChatWorkspace({ state, sendQuery, ... }: ChatWorkspaceProps)`)
- Avoid `*args`, `**kwargs` (not observed in this codebase)

**Return values:**
- Python: Explicit return type hints (e.g., `-> dict` or `-> AgentResponse`)
- TypeScript: Inferred from implementation; `void` for event handlers
- Consistent types: Return same structure for caller predictability

## Module Design

**Exports:**

Python:
- Modules export public functions/classes at module level
- Import pattern: `from agent.tools import calculator, python_executor, web_search`
- Private functions (leading `_`) are not exported

TypeScript:
- Default exports: Used for React components (e.g., `export function ChatWorkspace(...)`)
- Named exports: Used for hooks and utilities (e.g., `export function useAgent() { ... }`)
- Type exports: `export interface`, `export type` (from `frontend/src/types/index.ts`)

Example from `backend/agent/graph.py`:
```python
from agent.tools import (
    calculator,
    normalize_python_code_input,
    python_executor,
    web_search,
)

# Not imported:
# - _SYMPY_AVAILABLE, _NUMPY_AVAILABLE (private constants)
# - _strip_executor_status_annotations (private function)
```

**Barrel files:**
- TypeScript: `frontend/src/types/index.ts` re-exports all types
- Python: No barrel files (no `__all__` lists observed)

**Circular dependencies:**
- Not detected in exploration
- Import order (standard lib → third-party → local) minimizes risk

## Pydantic Models

All request/response models follow PascalCase + naming convention:

Request/Response suffixes:
- `<Feature>Request` (e.g., `ChatMessageRequest`, `QueryRequest`, `SuggestionsRequest`)
- `<Feature>Response` (e.g., `AgentResponse`, `ModelInfoResponse`, `SuggestionsResponse`)
- Intermediate data models: Just `<Feature>` (e.g., `AgentState`, `Step`, `Usage`)

Fields use `snake_case`:
```python
class AgentResponse(BaseModel):
    result: str
    trace: list[dict[str, Any]]
    total_time: float
    run_id: str
    answer: str
    steps: list[dict[str, Any]]
    tools_used: list[str]
    latency_ms: int
    status: str
```

## TypeScript Interfaces

All interfaces use PascalCase, all fields use `camelCase`:
```typescript
export interface AgentState {
  messages: Message[]
  steps: Step[]
  isLoading: boolean
  error: string | null
  config: AgentConfig | null
  runSummary: RunSummary | null
  connectionStatus: 'checking' | 'online' | 'mock' | 'error'
  suggestions: string[]
}
```

---

*Convention analysis: 2026-06-29*
