from __future__ import annotations

import importlib
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "apps"))

from sim.process import DEFAULT_DB, reset_history

reset_history(DEFAULT_DB, samples=900)
overview = importlib.import_module("overview")
app = overview.build_app()
if app.layout is None:
    raise SystemExit("overview layout missing")
rows = overview.read_rows(limit=60)
if len(rows) != 60:
    raise SystemExit(f"expected 60 historian rows, got {len(rows)}")
fig = overview.trend_figure(rows)
if len(fig.data) < 4:
    raise SystemExit("trend figure missing expected traces")
print("ot smoke OK")
