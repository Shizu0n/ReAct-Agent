# ReAct Agent with Tool Use

Portfolio-ready AI Engineering project split into a FastAPI backend and a React frontend.

## Structure

```text
01-react-agent/
  backend/   FastAPI, LangChain/LangGraph agent, tools, tests, Dockerfile
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

The frontend calls `http://localhost:8000/agent/invoke` by default. Configure `frontend/.env.local` if the backend runs elsewhere.

## Validate

```bash
cd backend && python -m unittest discover -s tests -v
cd frontend && npm run lint && npm run build
```
