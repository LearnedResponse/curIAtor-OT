# curIAtor OT

A public v1 OT/HMI-maintenance example collection for curIAtor.

The collection demonstrates the release story without a broker stack: a deterministic tank process sim writes to a local SQLite historian, and a deliberately rough Dash HMI reads that historian. Operator feedback should move the HMI from a rainbow mimic toward a High-Performance-HMI / ISA-101 style operating display.

## Run

```bash
python sim/process.py --samples 2400
curiator up        # http://127.0.0.1:8430
```

For live appending data in another terminal:

```bash
python sim/process.py --live
```

To dogfood the maintenance loop:

```bash
curiator seed seed/feedback.yaml
curiator watch
```

## Scope

v1 is intentionally boring infrastructure: sim -> SQLite historian -> Dash HMI. The future v2 MING stack can add Mosquitto, Telegraf, and InfluxDB without changing the curation story.

This is a simulation only. It makes no PLC, control, safety, or production HMI claims.
