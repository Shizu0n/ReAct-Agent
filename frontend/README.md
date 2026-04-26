# ReAct Agent Frontend

React + TypeScript + Vite frontend for the ReAct Agent with Tool Use project.

## What It Shows

- Landing page with stack badges and portfolio CTAs.
- Demo console that calls `POST /agent/invoke`.
- ReAct trace timeline: thought, action, observation, final answer.
- Tool call cards with name, input, output, and status.
- Architecture and API contract sections for reviewers.

## Run

```bash
npm install
npm run dev
```

By default the UI calls `http://localhost:8000/agent/invoke`.

Optional `.env.local`:

```bash
VITE_API_BASE_URL=http://localhost:8000
VITE_GITHUB_URL=https://github.com/<user>/<repo>
```

## Validate

```bash
npm run lint
npm run build
```
