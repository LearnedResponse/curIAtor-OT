from __future__ import annotations

import argparse
import json
import math
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any


class TankTwin:
    """Small deterministic tank twin used until OpenModelica export is available."""

    def __init__(self) -> None:
        self.t = 0.0
        self.level = 52.0
        self.temp = 74.0
        self.valve_pct = 50.0
        self.last_wall = time.monotonic()
        self.history: list[dict[str, float]] = []

    @staticmethod
    def _clamp(value: float, low: float, high: float) -> float:
        return max(low, min(high, value))

    def _disturbance(self) -> tuple[float, float, float]:
        cycle = self.t % 900.0
        inlet_bias = 0.0
        outlet_bias = 0.0
        heat_load = 0.0
        if 180.0 <= cycle < 360.0:
            outlet_bias += 8.0 * math.sin((cycle - 180.0) / 180.0 * math.pi)
        if 480.0 <= cycle < 620.0:
            inlet_bias -= 7.0 * math.sin((cycle - 480.0) / 140.0 * math.pi)
        if 650.0 <= cycle < 790.0:
            heat_load += 9.0 * math.sin((cycle - 650.0) / 140.0 * math.pi)
        return inlet_bias, outlet_bias, heat_load

    def advance(self, seconds: float) -> None:
        seconds = self._clamp(seconds, 0.0, 30.0)
        if seconds <= 0.0:
            return
        steps = max(1, min(120, int(math.ceil(seconds / 0.25))))
        dt = seconds / steps
        for _ in range(steps):
            inlet_bias, outlet_bias, heat_load = self._disturbance()
            setpoint = self.setpoint
            error = setpoint - self.level
            self.valve_pct = self._clamp(48.0 + 2.15 * error + 4.5 * math.sin(self.t / 45.0), 0.0, 100.0)
            inlet = max(0.0, 11.5 + 0.86 * self.valve_pct + inlet_bias)
            outlet = max(0.0, 45.0 + 0.18 * math.sqrt(max(self.level, 0.0)) + outlet_bias)
            self.level = self._clamp(self.level + (inlet - outlet) / 38.0 * dt, 0.0, 95.0)
            ambient = 72.0 + 2.0 * math.sin(self.t / 320.0)
            self.temp += ((ambient + heat_load) - self.temp) / 180.0 * dt
            self.t += dt
            self._append_history(inlet, outlet)

    @property
    def setpoint(self) -> float:
        return 55.0 + (4.0 if 300.0 <= (self.t % 900.0) < 520.0 else 0.0)

    def _append_history(self, inlet: float, outlet: float) -> None:
        if self.history and self.t - self.history[-1]["t"] < 2.0:
            return
        self.history.append({
            "t": round(self.t, 2),
            "level": round(self.level, 3),
            "setpoint": round(self.setpoint, 3),
            "inlet": round(inlet, 3),
            "outlet": round(outlet, 3),
        })
        if len(self.history) > 80:
            self.history = self.history[-80:]

    def snapshot(self) -> dict[str, Any]:
        now = time.monotonic()
        self.advance(now - self.last_wall)
        self.last_wall = now
        inlet_bias, outlet_bias, heat_load = self._disturbance()
        inlet = max(0.0, 11.5 + 0.86 * self.valve_pct + inlet_bias)
        outlet = max(0.0, 45.0 + 0.18 * math.sqrt(max(self.level, 0.0)) + outlet_bias)
        level_error = self.setpoint - self.level
        cavitation_margin = 18.0 - max(0.0, outlet - 48.0) * 0.45 - max(0.0, self.temp - 80.0) * 0.3
        control_margin = min(self.valve_pct, 100.0 - self.valve_pct)
        mass_balance = inlet - outlet - (38.0 * (level_error / max(abs(level_error), 1.0)) * 0.0)
        alarms = []
        if self.level > 68.0:
            alarms.append("high level")
        if self.level < 38.0:
            alarms.append("low level")
        if cavitation_margin < 5.0:
            alarms.append("low cavitation margin")
        if self.temp > 82.0:
            alarms.append("high process temperature")
        if not alarms:
            alarms.append("normal operating envelope")
        return {
            "t": round(self.t, 2),
            "level": round(self.level, 2),
            "setpoint": round(self.setpoint, 2),
            "level_error": round(level_error, 2),
            "flow_in": round(inlet, 2),
            "flow_out": round(outlet, 2),
            "mass_balance": round(mass_balance, 2),
            "temperature": round(self.temp, 2),
            "valve_pct": round(self.valve_pct, 2),
            "cavitation_margin": round(cavitation_margin, 2),
            "control_margin": round(control_margin, 2),
            "heat_load": round(heat_load, 2),
            "alarms": alarms,
            "history": self.history[-48:],
            "modelica_source": "../../models/TankProcess.mo",
            "fmu_status": "blocked: OpenModelica omc is not installed in this environment",
        }


class Handler(BaseHTTPRequestHandler):
    server: "TwinServer"

    def do_GET(self) -> None:  # noqa: N802 - http.server API
        if self.path.startswith("/health"):
            self._send_json({"ok": True})
            return
        if self.path.startswith("/snapshot"):
            self._send_json(self.server.twin.snapshot())
            return
        self.send_error(404, "not found")

    def log_message(self, fmt: str, *args: object) -> None:
        return

    def _send_json(self, payload: dict[str, Any]) -> None:
        body = json.dumps(payload, sort_keys=True).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


class TwinServer(ThreadingHTTPServer):
    def __init__(self, server_address: tuple[str, int]) -> None:
        super().__init__(server_address, Handler)
        self.twin = TankTwin()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Tank 42 digital-twin sidecar.")
    parser.add_argument("--port", "--engine-port", dest="port", type=int, default=8842)
    args = parser.parse_args(argv)
    server = TwinServer(("127.0.0.1", args.port))
    print(f"tank twin engine listening on {args.port}", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        return 0
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
