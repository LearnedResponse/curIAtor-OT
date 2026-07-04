# curIAtor OT

A public v1 OT/HMI-maintenance example collection for curIAtor.

The collection demonstrates the release story without a broker stack: a deterministic tank process sim writes to a local SQLite historian, and a deliberately rough Dash HMI reads that historian. Operator feedback should move the HMI from a rainbow mimic toward a High-Performance-HMI / ISA-101 style operating display.

It also includes a v2 dogfood app, `twin_diagnostics`, that runs as an `engine-backed` mount: curIAtor starts a managed tank-twin sidecar and then proxies a diagnostic HMI over it. The checked-in `models/TankProcess.mo` source is the OpenModelica target; FMU export is blocked in this environment because `omc` is not installed.

## Run

```bash
python sim/process.py --samples 2400
curiator up        # http://127.0.0.1:8430
```

For live appending data in another terminal:

```bash
python sim/process.py --live
```

To run the v2 diagnostics app standalone:

```bash
cd apps/twin_diagnostics
python engine.py --port 8842
python server.py --port 8742 --engine-url http://127.0.0.1:8842
```

To dogfood the maintenance loop:

```bash
curiator seed seed/feedback.yaml
curiator watch
```

## Scope

v1 is intentionally boring infrastructure: sim -> SQLite historian -> Dash HMI. The v2 twin app proves the runner-side engine-backed shape locally, while the true FMU substrate waits on OpenModelica. A future MING stack can add Mosquitto, Telegraf, and InfluxDB without changing the curation story.

This is a simulation only. It makes no PLC, control, safety, or production HMI claims.
