from __future__ import annotations

import shutil

from engine import TankTwin
from server import fetch_snapshot


def main() -> int:
    twin = TankTwin()
    twin.advance(12.0)
    snapshot = twin.snapshot()
    required = {
        "level",
        "setpoint",
        "level_error",
        "flow_in",
        "flow_out",
        "cavitation_margin",
        "control_margin",
        "alarms",
        "history",
        "fmu_status",
    }
    missing = required - snapshot.keys()
    if missing:
        raise SystemExit(f"snapshot missing keys: {sorted(missing)}")
    if not snapshot["history"]:
        raise SystemExit("snapshot history is empty")
    if not isinstance(fetch_snapshot("http://127.0.0.1:1"), dict):
        raise SystemExit("front-end engine fetch fallback did not return a payload")
    status = "available" if shutil.which("omc") else "blocked: omc not installed"
    print(f"twin diagnostics smoke OK; fmu export {status}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
