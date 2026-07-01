from __future__ import annotations

import argparse
import math
import sqlite3
import time
from pathlib import Path

DEFAULT_DB = Path(__file__).resolve().parents[1] / "data" / "historian.sqlite"

SCHEMA = """
create table if not exists samples (
    t integer primary key,
    level real not null,
    setpoint real not null,
    flow_in real not null,
    flow_out real not null,
    temp real not null,
    valve_pct real not null,
    pump_status text not null,
    alarm_high integer not null,
    alarm_low integer not null,
    alarm_temp_high integer not null
)
"""


def deterministic_sample(t: int) -> dict:
    """A deterministic tank loop with scripted disturbances.

    The numbers are intentionally simple. This is demo data for an HMI, not a plant model.
    """
    phase = t / 60.0
    level = 51 + 11 * math.sin(phase / 5.4) + 4 * math.sin(phase / 1.7)
    if 420 <= t < 720:
        level += 14 * math.sin((t - 420) / 300 * math.pi)
    if 1180 <= t < 1480:
        level -= 12 * math.sin((t - 1180) / 300 * math.pi)
    setpoint = 55.0
    error = setpoint - level
    valve_pct = max(0, min(100, 54 + 1.8 * error + 9 * math.sin(phase / 3.1)))
    pump_status = "running" if t % 900 < 820 else "standby"
    flow_out_base = 52 if pump_status == "running" else 20
    flow_in = max(0, 0.8 * valve_pct + 12 + 3 * math.sin(phase / 2.0))
    flow_out = max(0, flow_out_base + 7 * math.sin(phase / 4.5))
    temp = 74 + 3.5 * math.sin(phase / 9.0) + (7 if 1620 <= t < 1900 else 0)
    alarm_high = int(level > 68)
    alarm_low = int(level < 38)
    alarm_temp_high = int(temp > 80)
    return {
        "t": t,
        "level": round(level, 3),
        "setpoint": setpoint,
        "flow_in": round(flow_in, 3),
        "flow_out": round(flow_out, 3),
        "temp": round(temp, 3),
        "valve_pct": round(valve_pct, 3),
        "pump_status": pump_status,
        "alarm_high": alarm_high,
        "alarm_low": alarm_low,
        "alarm_temp_high": alarm_temp_high,
    }


def connect(db: Path = DEFAULT_DB) -> sqlite3.Connection:
    db.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(db)
    con.execute(SCHEMA)
    return con


def reset_history(db: Path = DEFAULT_DB, samples: int = 2400) -> None:
    con = connect(db)
    with con:
        con.execute("delete from samples")
        con.executemany(
            "insert into samples values (:t, :level, :setpoint, :flow_in, :flow_out, :temp, :valve_pct, :pump_status, :alarm_high, :alarm_low, :alarm_temp_high)",
            (deterministic_sample(t) for t in range(samples)),
        )
    con.close()


def ensure_history(db: Path = DEFAULT_DB, min_rows: int = 1800) -> None:
    con = connect(db)
    try:
        rows = con.execute("select count(*) from samples").fetchone()[0]
    finally:
        con.close()
    if rows < min_rows:
        reset_history(db, max(min_rows, 2400))


def append_live(db: Path = DEFAULT_DB, period: float = 1.0) -> None:
    con = connect(db)
    row = con.execute("select max(t) from samples").fetchone()[0]
    t = int(row or 0) + 1
    try:
        while True:
            with con:
                con.execute(
                    "insert or replace into samples values (:t, :level, :setpoint, :flow_in, :flow_out, :temp, :valve_pct, :pump_status, :alarm_high, :alarm_low, :alarm_temp_high)",
                    deterministic_sample(t),
                )
            t += 1
            time.sleep(period)
    finally:
        con.close()


def main() -> int:
    parser = argparse.ArgumentParser(description="Deterministic tank historian for the curIAtor OT demo.")
    parser.add_argument("--db", type=Path, default=DEFAULT_DB)
    parser.add_argument("--samples", type=int, default=2400)
    parser.add_argument("--live", action="store_true", help="append one sample per second until interrupted")
    args = parser.parse_args()
    if args.live:
        ensure_history(args.db, min_rows=args.samples)
        append_live(args.db)
    else:
        reset_history(args.db, samples=args.samples)
        print(f"wrote {args.samples} samples to {args.db}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
