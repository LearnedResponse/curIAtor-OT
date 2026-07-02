from __future__ import annotations

import sqlite3
import time
from pathlib import Path

import dash
from dash import Input, Output, dcc, html
import plotly.graph_objects as go

from sim.process import DEFAULT_DB, ensure_history

APP_STYLE = {
    "fontFamily": "system-ui, sans-serif",
    "padding": "16px",
    "background": "#e5e7eb",
    "minHeight": "100vh",
    "color": "#1f2937",
}
CARD = {
    "borderRadius": "6px",
    "padding": "12px",
    "boxShadow": "0 1px 4px rgba(15,23,42,.12)",
    "border": "1px solid #cbd5e1",
}
PANEL = {**CARD, "background": "#f8fafc"}
NORMAL_CARD = {**CARD, "background": "#ffffff", "minHeight": "88px"}
ALARM_COLORS = {"high": "#b91c1c", "medium": "#c2410c", "low": "#b45309"}


def read_rows(limit: int = 3600, db: Path = DEFAULT_DB) -> list[dict]:
    ensure_history(db, min_rows=limit)
    con = sqlite3.connect(db)
    con.row_factory = sqlite3.Row
    try:
        rows = con.execute("select * from samples order by t desc limit ?", (limit,)).fetchall()
    finally:
        con.close()
    return [dict(r) for r in reversed(rows)]


def metric_card(label: str, value: str, detail: str = "", severity: str | None = None) -> html.Div:
    accent = ALARM_COLORS.get(severity, "#64748b")
    return html.Div(
        style={**NORMAL_CARD, "borderLeft": f"8px solid {accent}"},
        children=[
            html.Div(
                label,
                style={"fontSize": "12px", "fontWeight": 700, "textTransform": "uppercase", "color": "#475569"},
            ),
            html.Div(value, style={"fontSize": "30px", "fontWeight": 800, "lineHeight": 1.15, "color": "#111827"}),
            html.Div(detail, style={"fontSize": "12px", "color": accent if severity else "#64748b"}),
        ],
    )


def trend_figure(rows: list[dict]) -> go.Figure:
    x = [r["t"] / 60 for r in rows]
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=x, y=[r["level"] for r in rows], name="level", line=dict(color="#334155", width=3)))
    fig.add_trace(
        go.Scatter(x=x, y=[r["setpoint"] for r in rows], name="setpoint", line=dict(color="#64748b", dash="dash", width=2))
    )
    fig.add_trace(go.Scatter(x=x, y=[r["flow_in"] for r in rows], name="flow in", line=dict(color="#64748b", width=2)))
    fig.add_trace(go.Scatter(x=x, y=[r["flow_out"] for r in rows], name="flow out", line=dict(color="#94a3b8", width=2)))
    fig.update_layout(
        height=330,
        margin=dict(l=40, r=20, t=28, b=34),
        paper_bgcolor="#f8fafc",
        plot_bgcolor="#ffffff",
        font=dict(color="#1f2937"),
        legend=dict(orientation="h", y=1.15, x=0),
        xaxis_title="minutes",
        yaxis_title="process values",
    )
    fig.update_xaxes(gridcolor="#e2e8f0", zerolinecolor="#cbd5e1")
    fig.update_yaxes(gridcolor="#e2e8f0", zerolinecolor="#cbd5e1")
    return fig


def sparkline_figure(rows: list[dict], field: str, color: str = "#334155") -> go.Figure:
    x = [r["t"] / 60 for r in rows]
    y = [r[field] for r in rows]
    fig = go.Figure(go.Scatter(x=x, y=y, mode="lines", line=dict(color=color, width=2), hoverinfo="skip"))
    fig.update_layout(
        height=92,
        margin=dict(l=8, r=8, t=8, b=8),
        paper_bgcolor="#ffffff",
        plot_bgcolor="#ffffff",
        showlegend=False,
    )
    fig.update_xaxes(visible=False)
    fig.update_yaxes(visible=False)
    return fig


def sparkline_card(label: str, rows: list[dict], field: str, unit: str, color: str = "#334155") -> html.Div:
    start = rows[0][field]
    end = rows[-1][field]
    delta = end - start
    if abs(delta) < 0.05:
        direction = "steady"
    else:
        direction = "rising" if delta > 0 else "falling"
    return html.Div(
        style={**PANEL, "background": "#ffffff"},
        children=[
            html.Div(label, style={"fontSize": "12px", "fontWeight": 700, "textTransform": "uppercase", "color": "#475569"}),
            html.Div(
                f"{end:.1f}{unit} | {direction} {abs(delta):.1f}{unit} over last hour",
                style={"fontSize": "13px", "color": "#334155", "marginBottom": "4px"},
            ),
            dcc.Graph(figure=sparkline_figure(rows, field, color), config={"displayModeBar": False}),
        ],
    )


def tank_figure(row: dict) -> go.Figure:
    level = row["level"]
    setpoint = row["setpoint"]
    normal_low = max(0, setpoint - 8)
    normal_high = min(100, setpoint + 8)
    alarm = row["alarm_high"] or row["alarm_low"]
    liquid = ALARM_COLORS["high"] if alarm else "#94a3b8"
    label_color = ALARM_COLORS["high"] if alarm else "#1f2937"
    fig = go.Figure()
    fig.add_shape(type="rect", x0=0.25, x1=0.75, y0=0, y1=100, line=dict(color="#334155", width=3), fillcolor="#f1f5f9")
    fig.add_shape(type="rect", x0=0.25, x1=0.75, y0=normal_low, y1=normal_high, line=dict(width=0), fillcolor="#dbeafe")
    fig.add_shape(type="rect", x0=0.25, x1=0.75, y0=0, y1=level, line=dict(color=liquid, width=1), fillcolor=liquid)
    fig.add_shape(type="line", x0=0.20, x1=0.80, y0=setpoint, y1=setpoint, line=dict(color="#1f2937", width=3, dash="dash"))
    fig.add_annotation(x=0.84, y=setpoint, text=f"SP {setpoint:.0f}%", showarrow=False, xanchor="left", font=dict(size=13, color="#1f2937"))
    fig.add_annotation(x=0.18, y=(normal_low + normal_high) / 2, text="normal", showarrow=False, xanchor="right", font=dict(size=12, color="#475569"))
    fig.add_annotation(x=0.5, y=min(level + 6, 96), text=f"{level:.1f}%", showarrow=False, font=dict(size=20, color=label_color))
    fig.update_xaxes(visible=False, range=[0, 1])
    fig.update_yaxes(visible=False, range=[0, 100])
    fig.update_layout(height=330, margin=dict(l=10, r=10, t=10, b=10), paper_bgcolor="#f8fafc", plot_bgcolor="#f8fafc")
    return fig


def alarm_items(row: dict) -> html.Div:
    alarms = [
        {
            "priority": 1,
            "name": "HI LEVEL",
            "active": row["alarm_high"],
            "severity": "high",
            "consequence": "risk of tank overflow and downstream carryover",
            "response": "reduce inlet valve, verify outlet pump running",
        },
        {
            "priority": 2,
            "name": "TEMP HIGH",
            "active": row["alarm_temp_high"],
            "severity": "medium",
            "consequence": "thermal stress on product and equipment",
            "response": "check cooling and reduce heat input",
        },
        {
            "priority": 3,
            "name": "LOW LEVEL SWITCH CHATTER",
            "active": row["alarm_low"],
            "severity": "low",
            "consequence": "pump suction margin may be reduced",
            "response": "confirm level trend before switching pump state",
        },
    ]
    active = sorted((alarm for alarm in alarms if alarm["active"]), key=lambda alarm: alarm["priority"])
    if active:
        alarm_cards = [
            html.Div(
                [
                    html.Div(f"P{alarm['priority']} - {alarm['name']}", style={"fontWeight": 800, "marginBottom": "4px"}),
                    html.Div(f"Consequence: {alarm['consequence']}", style={"fontSize": "12px", "fontWeight": 600}),
                    html.Div(f"First response: {alarm['response']}", style={"fontSize": "12px", "fontWeight": 600}),
                ],
                style={
                    **CARD,
                    "background": ALARM_COLORS[alarm["severity"]],
                    "color": "#ffffff",
                    "borderColor": ALARM_COLORS[alarm["severity"]],
                    "marginBottom": "8px",
                },
            )
            for alarm in active
        ]
    else:
        alarm_cards = [
            html.Div(
                "No active alarms",
                style={**CARD, "background": "#e2e8f0", "color": "#334155", "borderColor": "#cbd5e1", "marginBottom": "8px"},
            )
        ]
    pump = str(row.get("pump_status") or "unknown").lower()
    known = pump in {"running", "standby"}
    pump_label = pump.upper() if known else "STALE / UNKNOWN"
    pump_detail = "historian value present" if known else "no valid pump_status in latest historian row"
    equipment = html.Div(
        [
            html.Div("Equipment state", style={"fontSize": "12px", "fontWeight": 700, "color": "#475569", "marginBottom": "6px"}),
            html.Div(
                [
                    html.Div("Pump", style={"fontSize": "12px", "fontWeight": 700, "color": "#475569", "textTransform": "uppercase"}),
                    html.Div(pump_label, style={"fontSize": "24px", "fontWeight": 800, "color": "#111827"}),
                    html.Div(pump_detail, style={"fontSize": "12px", "color": "#64748b"}),
                ],
                style={**CARD, "background": "#ffffff", "color": "#1f2937", "borderColor": "#cbd5e1"},
            ),
        ],
        style={"marginTop": "14px"},
    )
    return html.Div([
        html.Div("Active alarms", style={"fontSize": "12px", "fontWeight": 700, "color": "#475569", "marginBottom": "6px"}),
        *alarm_cards,
        equipment,
    ])


def freshness_card(_row: dict, db: Path = DEFAULT_DB) -> html.Div:
    try:
        age_seconds = max(0, int(time.time() - db.stat().st_mtime))
    except OSError:
        age_seconds = 9999
    if age_seconds <= 5:
        state = "LIVE"
        detail = f"historian file updated {age_seconds}s ago"
        severity = None
    elif age_seconds <= 30:
        state = "STALE"
        detail = f"historian file updated {age_seconds}s ago - check sim process"
        severity = "medium"
    else:
        state = "HISTORIAN STALE"
        detail = f"historian file updated {age_seconds}s ago - sim may have stopped"
        severity = "high"
    return metric_card("historian", state, detail, severity)


def operating_state_panel(row: dict, rows: list[dict]) -> html.Div:
    level = row["level"]
    setpoint = row["setpoint"]
    high_limit = setpoint + 13
    low_limit = setpoint - 17
    window = rows[-300:] if len(rows) >= 300 else rows
    delta = level - window[0]["level"]
    direction = "steady" if abs(delta) < 0.25 else ("rising" if delta > 0 else "falling")
    if row["alarm_high"]:
        state = "HIGH LEVEL ALARM"
        severity = "high"
        constraint = f"above {high_limit:.0f}% high constraint"
    elif row["alarm_low"]:
        state = "LOW LEVEL ALARM"
        severity = "low"
        constraint = f"below {low_limit:.0f}% low constraint"
    elif low_limit <= level <= high_limit:
        state = "NORMAL OPERATING RANGE"
        severity = None
        constraint = f"constraints {low_limit:.0f}% to {high_limit:.0f}%"
    else:
        state = "APPROACHING CONSTRAINT"
        severity = "medium"
        constraint = f"outside target band around {setpoint:.0f}% SP"
    accent = ALARM_COLORS.get(severity, "#64748b")
    return html.Div(
        style={**PANEL, "background": "#ffffff", "borderLeft": f"8px solid {accent}", "marginBottom": "12px"},
        children=[
            html.Div("Operating state", style={"fontSize": "12px", "fontWeight": 700, "textTransform": "uppercase", "color": "#475569"}),
            html.Div(state, style={"fontSize": "24px", "fontWeight": 800, "color": "#111827"}),
            html.Div(
                f"Level {level:.1f}% vs SP {setpoint:.0f}% | {direction} {abs(delta):.1f}% over five minutes | {constraint}",
                style={"fontSize": "13px", "color": "#334155"},
            ),
        ],
    )


def level_severity(row: dict) -> str | None:
    if row["alarm_high"]:
        return "high"
    if row["alarm_low"]:
        return "low"
    return None


def build_app() -> dash.Dash:
    app = dash.Dash(__name__)
    app.title = "Rainbow Tank HMI"
    app.layout = html.Div(style=APP_STYLE, children=[
        html.H2("Tank 42 Level Control - Baseline HMI", style={"margin": "0 0 10px", "color": "#1f2937"}),
        html.Div(
            id="metrics",
            style={"display": "grid", "gridTemplateColumns": "repeat(5, minmax(140px, 1fr))", "gap": "10px", "marginBottom": "12px"},
        ),
        html.Div(
            id="sparklines",
            style={"display": "grid", "gridTemplateColumns": "repeat(2, minmax(220px, 1fr))", "gap": "10px", "marginBottom": "12px"},
        ),
        html.Div(id="state-summary"),
        html.Div(style={"display": "grid", "gridTemplateColumns": "1.2fr 1fr 0.9fr", "gap": "12px"}, children=[
            html.Div(style=PANEL, children=[html.H3("Trend", style={"marginTop": 0}), dcc.Graph(id="trend", config={"displayModeBar": False})]),
            html.Div(style=PANEL, children=[html.H3("Level Constraints", style={"marginTop": 0}), dcc.Graph(id="tank", config={"displayModeBar": False})]),
            html.Div(style=PANEL, children=[html.H3("Alarms and Equipment", style={"marginTop": 0}), html.Div(id="alarms")]),
        ]),
        dcc.Interval(id="tick", interval=1000, n_intervals=0),
    ])

    @app.callback(
        Output("metrics", "children"),
        Output("sparklines", "children"),
        Output("state-summary", "children"),
        Output("trend", "figure"),
        Output("tank", "figure"),
        Output("alarms", "children"),
        Input("tick", "n_intervals"),
    )
    def refresh(_n):
        rows = read_rows()
        row = rows[-1]
        metrics = [
            metric_card("level", f"{row['level']:.1f}%", "PV", level_severity(row)),
            metric_card("setpoint", f"{row['setpoint']:.1f}%", "SP"),
            metric_card("valve", f"{row['valve_pct']:.0f}%", "inlet valve"),
            metric_card("temperature", f"{row['temp']:.1f} F", row["pump_status"], "medium" if row["alarm_temp_high"] else None),
            freshness_card(row),
        ]
        sparklines = [
            sparkline_card("level one-hour trend", rows, "level", "%", "#334155"),
            sparkline_card("outlet flow one-hour trend", rows, "flow_out", "", "#475569"),
        ]
        return metrics, sparklines, operating_state_panel(row, rows), trend_figure(rows), tank_figure(row), alarm_items(row)

    return app


app = build_app()
