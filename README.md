# ReAct Agent with Tool Use

Portfolio-ready AI Engineering project split into a FastAPI backend and a React frontend.

## Structure

```text
01-react-agent/
  backend/   FastAPI, LangChain/LangGraph agent, tools, tests
  api/       Vercel Python Function entrypoint for the FastAPI app
  frontend/  React, TypeScript, Vite, TailwindCSS portfolio UI
```

## Run Backend

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn api:app --reload
```

On Windows PowerShell:

```powershell
cd backend
.venv\Scripts\Activate.ps1
uvicorn api:app --reload
```

## Run Frontend

```bash
cd frontend
npm install
npm run dev
```

The frontend calls `VITE_API_URL` when configured. Local dev can point it at `http://localhost:8000`; production uses `/api` through Vercel Functions.

## Local Full-Stack Dev

To run the same Vercel routing locally, use the repo wrapper instead of calling
`npx vercel dev` directly from an activated Python venv:

```bash
npm run dev:vercel
```

The wrapper builds `frontend/dist` first, then clears `VIRTUAL_ENV` only for the
Vercel child process. That lets Vercel detect `.venv\Scripts\python.exe` by
itself instead of falling back to a global Python that does not have FastAPI
installed. It also binds Vercel to `127.0.0.1:3000` by default, which avoids
Windows `localhost` proxy quirks. If port `3000` is already occupied, it fails
before starting another Vercel process.
When Vercel's generated Python dev runtime is present, the wrapper disables its
repo-wide reload watcher; that watcher can leave the Vercel proxy alive while
the FastAPI child process has died.
If `@vercel/python` still exits before binding on Windows/Git Bash, the wrapper
falls back to `uvicorn api.index:app` on the same `127.0.0.1:3000` address.
That keeps the same FastAPI app, `/api/*` routes, and built frontend available
for local testing.
In Git Bash/MINGW, the wrapper skips `@vercel/python` and uses this uvicorn path
directly because the Vercel Python dev process can exit with Windows control
code `3221225786` before binding.

Direct `npx vercel dev` also works if no Python venv is activated:

```bash
deactivate 2>/dev/null || true
npx vercel dev
```

Open `http://127.0.0.1:3000`. The frontend and FastAPI API are served through
the Vercel local router, including `/api/health`, `/api/config`, and `/api/run`.

## Deploy

```bash
vercel
```

Vercel builds the Vite frontend from `frontend/` and serves the FastAPI app through `api/index.py`.

## Validate

```bash
cd backend && python -m unittest discover -s tests -v
cd frontend && npm run lint && npm run build
```

Before publishing changes, run the local secret scan:

```powershell
.\scripts\check-secrets.ps1
```

The scan ignores real `.env` files and dependency/build folders, then checks source, docs, and config for common provider token formats.
