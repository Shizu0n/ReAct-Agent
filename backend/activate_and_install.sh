#!/bin/bash
set -e

if [ -f .venv/bin/activate ]; then
  source .venv/bin/activate
elif [ -f .venv/Scripts/activate ]; then
  source .venv/Scripts/activate
else
  python3.13 -m venv .venv
  if [ -f .venv/bin/activate ]; then
    source .venv/bin/activate
  else
    source .venv/Scripts/activate
  fi
fi

if [ -f .venv/bin/python ]; then
  PYTHON_BIN=.venv/bin/python
elif [ -f .venv/Scripts/python.exe ]; then
  PYTHON_BIN=.venv/Scripts/python.exe
else
  PYTHON_BIN=python
fi

"$PYTHON_BIN" -m pip install --upgrade pip
"$PYTHON_BIN" -m pip install langchain==0.3.7 langchain-community==0.3.7 langgraph==0.2.45 \
                         fastapi==0.115.4 uvicorn==0.32.0 python-dotenv==1.0.1 \
                         tavily-python==0.5.0 slowapi==0.1.9 sse-starlette==2.1.3
"$PYTHON_BIN" -m pip freeze > requirements.txt
echo "✓ react-agent workspace ready"
