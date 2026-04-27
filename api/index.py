from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"

sys.path.insert(0, str(BACKEND))

spec = importlib.util.spec_from_file_location("react_agent_backend", BACKEND / "api.py")
if spec is None or spec.loader is None:
    raise RuntimeError("Unable to load backend FastAPI app.")

module = importlib.util.module_from_spec(spec)
sys.modules["react_agent_backend"] = module
spec.loader.exec_module(module)

app = module.app
