from __future__ import annotations

import sqlite3
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


def read_rows(limit: int = 720, db: Path = DEFAULT_DB) -> list[dict]:
    ensure_history(db)
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
    fig.add_annotation(x=0.02, y=83, text="IN", showarrow=False, font=dict(color="#475569", size=16))
    fig.add_annotation(x=0.98, y=18, text="OUT", showarrow=False, font=dict(color="#475569", size=16))
    fig.update_xaxes(visible=False, range=[0, 1])
    fig.update_yaxes(visible=False, range=[0, 100])
    fig.update_layout(height=330, margin=dict(l=10, r=10, t=10, b=10), paper_bgcolor="#f8fafc", plot_bgcolor="#f8fafc")
    return fig


def alarm_items(row: dict) -> list[html.Div]:
    alarms = [
        ("HI LEVEL", row["alarm_high"], "high"),
        ("TEMP HIGH", row["alarm_temp_high"], "medium"),
        ("LOW LEVEL SWITCH CHATTER", row["alarm_low"], "low"),
        ("PUMP STATUS NORMAL", False, None),
    ]
    out = []
    for name, active, severity in alarms:
        color = ALARM_COLORS.get(severity, "#64748b") if active else "#e2e8f0"
        text = "#ffffff" if active else "#334155"
        border = ALARM_COLORS.get(severity, "#94a3b8") if active else "#cbd5e1"
        out.append(
            html.Div(
                name,
                style={
                    **CARD,
                    "background": color,
                    "color": text,
                    "borderColor": border,
                    "marginBottom": "8px",
                    "fontWeight": 800,
                },
            )
        )
    return out


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
            style={"display": "grid", "gridTemplateColumns": "repeat(4, minmax(140px, 1fr))", "gap": "10px", "marginBottom": "12px"},
        ),
        html.Div(style={"display": "grid", "gridTemplateColumns": "1.2fr 1fr 0.9fr", "gap": "12px"}, children=[
            html.Div(style=PANEL, children=[html.H3("Trend", style={"marginTop": 0}), dcc.Graph(id="trend", config={"displayModeBar": False})]),
            html.Div(style=PANEL, children=[html.H3("Mimic", style={"marginTop": 0}), dcc.Graph(id="tank", config={"displayModeBar": False})]),
            html.Div(style=PANEL, children=[html.H3("Alarm List", style={"marginTop": 0}), html.Div(id="alarms")]),
        ]),
        dcc.Interval(id="tick", interval=1000, n_intervals=0),
    ])

    @app.callback(
        Output("metrics", "children"),
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
        ]
        return metrics, trend_figure(rows), tank_figure(row), alarm_items(row)

    return app


app = build_app()
