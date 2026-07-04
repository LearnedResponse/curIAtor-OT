from __future__ import annotations

import argparse
import html
import json
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any


PAGE = """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Tank 42 twin diagnostics</title>
  <style>
    :root {
      color-scheme: light;
      font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      color: #24313a;
      background: #f5f7f8;
    }
    body { margin: 0; padding: 24px 28px; }
    main { max-width: 1180px; margin: 0 auto; }
    header { display: flex; align-items: end; justify-content: space-between; gap: 20px; margin-bottom: 18px; }
    h1 { margin: 0; font-size: 28px; line-height: 1.1; letter-spacing: 0; }
    .subtle { color: #68747c; font-size: 14px; }
    .status { display: inline-flex; align-items: center; gap: 8px; font-size: 13px; color: #50606a; }
    .dot { width: 9px; height: 9px; border-radius: 50%; background: #2fa36b; }
    .grid { display: grid; grid-template-columns: repeat(4, minmax(150px, 1fr)); gap: 10px; margin: 14px 0; }
    .kpi { background: #fff; border: 1px solid #d8dee2; border-radius: 6px; padding: 12px; min-height: 84px; }
    .label { display: block; color: #6f7b84; font-size: 12px; text-transform: uppercase; }
    .value { display: block; font-size: 26px; font-weight: 700; margin-top: 4px; }
    .unit { color: #7b8790; font-size: 13px; margin-left: 4px; }
    .panel { background: #fff; border: 1px solid #d8dee2; border-radius: 6px; padding: 14px; margin-top: 12px; }
    .panel h2 { font-size: 16px; margin: 0 0 8px; }
    .two { display: grid; grid-template-columns: minmax(0, 2fr) minmax(260px, 1fr); gap: 12px; align-items: stretch; }
    svg { width: 100%; height: 280px; background: #eef3f6; border: 1px solid #d6dee3; border-radius: 4px; }
    .alarm-list { display: grid; gap: 8px; margin-top: 10px; }
    .alarm { border-left: 4px solid #2fa36b; background: #f3faf6; padding: 8px 10px; border-radius: 4px; }
    .alarm.warn { border-left-color: #cf7b00; background: #fff8ed; }
    code { background: #edf1f4; border-radius: 4px; padding: 2px 5px; font-size: 12px; }
    @media (max-width: 920px) {
      body { padding: 18px; }
      header, .two { display: block; }
      .grid { grid-template-columns: repeat(2, minmax(140px, 1fr)); }
      .panel { margin-top: 10px; }
    }
  </style>
</head>
<body>
<main>
  <header>
    <div>
      <h1>Tank 42 twin diagnostics</h1>
      <div class="subtle">Engine-backed HMI over a live sidecar twin; FMU export is the next toolchain step.</div>
    </div>
    <div class="status"><span class="dot" id="dot"></span><span id="status">connecting</span></div>
  </header>

  <section class="grid">
    <div class="kpi"><span class="label">Level</span><span class="value"><span id="level">--</span><span class="unit">%</span></span></div>
    <div class="kpi"><span class="label">Setpoint error</span><span class="value"><span id="level_error">--</span><span class="unit">pt</span></span></div>
    <div class="kpi"><span class="label">Cavitation margin</span><span class="value"><span id="cavitation_margin">--</span><span class="unit">psi</span></span></div>
    <div class="kpi"><span class="label">Control margin</span><span class="value"><span id="control_margin">--</span><span class="unit">%</span></span></div>
  </section>

  <section class="two">
    <div class="panel">
      <h2>Level response</h2>
      <svg id="trend" viewBox="0 0 720 280" role="img" aria-label="recent level trend"></svg>
    </div>
    <div class="panel">
      <h2>Alarm rationale</h2>
      <div class="alarm-list" id="alarms"></div>
      <p class="subtle">Model source: <code>models/TankProcess.mo</code></p>
      <p class="subtle" id="fmu_status"></p>
    </div>
  </section>

  <section class="grid">
    <div class="kpi"><span class="label">Inflow</span><span class="value"><span id="flow_in">--</span><span class="unit">m3/h</span></span></div>
    <div class="kpi"><span class="label">Outflow</span><span class="value"><span id="flow_out">--</span><span class="unit">m3/h</span></span></div>
    <div class="kpi"><span class="label">Valve</span><span class="value"><span id="valve_pct">--</span><span class="unit">%</span></span></div>
    <div class="kpi"><span class="label">Temperature</span><span class="value"><span id="temperature">--</span><span class="unit">F</span></span></div>
  </section>
</main>
<script>
const path = window.location.pathname.endsWith("/") ? window.location.pathname : window.location.pathname + "/";
const api = path + "api/snapshot";
const ids = ["level", "level_error", "cavitation_margin", "control_margin", "flow_in", "flow_out", "valve_pct", "temperature"];

function setText(id, value) {
  const node = document.getElementById(id);
  if (node) node.textContent = Number(value).toFixed(1);
}

function drawTrend(history) {
  const svg = document.getElementById("trend");
  if (!svg) return;
  const rows = Array.isArray(history) ? history : [];
  const w = 720, h = 280, pad = 28;
  svg.innerHTML = "";
  const grid = document.createElementNS("http://www.w3.org/2000/svg", "g");
  for (const y of [35, 55, 75]) {
    const yy = h - pad - ((y - 25) / 60) * (h - 2 * pad);
    const line = document.createElementNS("http://www.w3.org/2000/svg", "line");
    line.setAttribute("x1", pad); line.setAttribute("x2", w - pad);
    line.setAttribute("y1", yy); line.setAttribute("y2", yy);
    line.setAttribute("stroke", y === 55 ? "#9aa9b2" : "#d4dde3");
    grid.appendChild(line);
  }
  svg.appendChild(grid);
  if (rows.length < 2) return;
  const t0 = rows[0].t, t1 = rows[rows.length - 1].t || t0 + 1;
  function x(row) { return pad + ((row.t - t0) / Math.max(1, t1 - t0)) * (w - 2 * pad); }
  function y(value) { return h - pad - ((value - 25) / 60) * (h - 2 * pad); }
  for (const key of ["setpoint", "level"]) {
    const poly = document.createElementNS("http://www.w3.org/2000/svg", "polyline");
    poly.setAttribute("fill", "none");
    poly.setAttribute("stroke", key === "level" ? "#245f73" : "#cf7b00");
    poly.setAttribute("stroke-width", key === "level" ? "4" : "2");
    poly.setAttribute("points", rows.map(row => `${x(row)},${y(row[key])}`).join(" "));
    svg.appendChild(poly);
  }
}

async function refresh() {
  const status = document.getElementById("status");
  const dot = document.getElementById("dot");
  try {
    const response = await fetch(api, {cache: "no-store"});
    const data = await response.json();
    ids.forEach(id => setText(id, data[id]));
    drawTrend(data.history);
    document.getElementById("fmu_status").textContent = data.fmu_status || "";
    const alarms = document.getElementById("alarms");
    alarms.innerHTML = "";
    (data.alarms || []).forEach(text => {
      const div = document.createElement("div");
      div.className = text.includes("normal") ? "alarm" : "alarm warn";
      div.textContent = text;
      alarms.appendChild(div);
    });
    status.textContent = `engine t=${Number(data.t).toFixed(1)}s`;
    dot.style.background = "#2fa36b";
  } catch (err) {
    status.textContent = "engine unavailable";
    dot.style.background = "#c74343";
  }
}

refresh();
setInterval(refresh, 1200);
</script>
</body>
</html>
"""


class Handler(BaseHTTPRequestHandler):
    server: "FrontendServer"

    def do_GET(self) -> None:  # noqa: N802 - http.server API
        if self.path.startswith("/health"):
            self._send_json({"ok": True, "engine_url": self.server.engine_url})
            return
        if self.path.startswith("/api/snapshot"):
            self._send_json(fetch_snapshot(self.server.engine_url))
            return
        self._send_html(PAGE)

    def log_message(self, fmt: str, *args: object) -> None:
        return

    def _send_html(self, text: str) -> None:
        body = text.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _send_json(self, payload: dict[str, Any]) -> None:
        body = json.dumps(payload, sort_keys=True).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


class FrontendServer(ThreadingHTTPServer):
    def __init__(self, server_address: tuple[str, int], engine_url: str) -> None:
        super().__init__(server_address, Handler)
        self.engine_url = engine_url.rstrip("/")


def fetch_snapshot(engine_url: str) -> dict[str, Any]:
    try:
        with urllib.request.urlopen(f"{engine_url.rstrip('/')}/snapshot", timeout=2.0) as response:
            payload = json.loads(response.read().decode("utf-8"))
            if isinstance(payload, dict):
                return payload
    except (OSError, urllib.error.URLError, json.JSONDecodeError) as exc:
        return {"error": html.escape(str(exc)), "alarms": ["engine unavailable"]}
    return {"error": "invalid engine payload", "alarms": ["engine unavailable"]}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Tank 42 diagnostics front-end.")
    parser.add_argument("--port", type=int, default=8742)
    parser.add_argument("--engine-url", default="http://127.0.0.1:8842")
    args = parser.parse_args(argv)
    server = FrontendServer(("127.0.0.1", args.port), args.engine_url)
    print(f"tank twin diagnostics listening on {args.port}; engine={args.engine_url}", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        return 0
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
