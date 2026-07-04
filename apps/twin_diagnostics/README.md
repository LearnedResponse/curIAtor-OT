# Tank 42 Twin Diagnostics

This app dogfoods curIAtor's `engine-backed` mount:

- `engine.py` is the managed backend sidecar.
- `server.py` is the proxied HMI/diagnostic surface.
- `models/TankProcess.mo` is the intended OpenModelica source.

The current sidecar is a deterministic Python implementation of the same tank process shape so the
gallery can run in a fresh clone without extra system packages. FMU export is intentionally not claimed
until `omc` is available; `smoke.py` reports that blocker instead of failing the public quickstart.

Run standalone:

```bash
python engine.py --port 8842
python server.py --port 8742 --engine-url http://127.0.0.1:8842
```
