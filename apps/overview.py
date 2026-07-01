from __future__ import annotations

import sqlite3
from pathlib import Path

import dash
from dash import Input, Output, dcc, html
import plotly.graph_objects as go

from sim.process import DEFAULT_DB, ensure_history

APP_STYLE = {"fontFamily": "system-ui, sans-serif", "padding": "16px", "background": "#101827", "minHeight": "100vh", "color": "white"}
CARD = {"borderRadius": "6px", "padding": "12px", "boxShadow": "0 2px 10px rgba(0,0,0,.25)"}


def read_rows(limit: int = 720, db: Path = DEFAULT_DB) -> list[dict]:
    ensure_history(db)
    con = sqlite3.connect(db)
    con.row_factory = sqlite3.Row
    try:
        rows = con.execute("select * from samples order by t desc limit ?", (limit,)).fetchall()
    finally:
        con.close()
    return [dict(r) for r in reversed(rows)]


def metric_card(label: str, value: str, color: str, detail: str = "") -> html.Div:
    return html.Div(
        style={**CARD, "background": color, "minHeight": "88px"},
        children=[
            html.Div(label, style={"fontSize": "12px", "fontWeight": 700, "textTransform": "uppercase"}),
            html.Div(value, style={"fontSize": "30px", "fontWeight": 800, "lineHeight": 1.15}),
            html.Div(detail, style={"fontSize": "12px", "opacity": 0.88}),
        ],
    )


def trend_figure(rows: list[dict]) -> go.Figure:
    x = [r["t"] / 60 for r in rows]
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=x, y=[r["level"] for r in rows], name="level", line=dict(color="#ff00f5", width=3)))
    fig.add_trace(go.Scatter(x=x, y=[r["setpoint"] for r in rows], name="setpoint", line=dict(color="#00ffff", dash="dash", width=2)))
    fig.add_trace(go.Scatter(x=x, y=[r["flow_in"] for r in rows], name="flow in", line=dict(color="#00ff00", width=2)))
    fig.add_trace(go.Scatter(x=x, y=[r["flow_out"] for r in rows], name="flow out", line=dict(color="#ffff00", width=2)))
    fig.update_layout(
        height=330,
        margin=dict(l=40, r=20, t=28, b=34),
        paper_bgcolor="#1f2937",
        plot_bgcolor="#111827",
        font=dict(color="white"),
        legend=dict(orientation="h", y=1.15, x=0),
        xaxis_title="minutes",
        yaxis_title="process values",
    )
    return fig


def tank_figure(row: dict) -> go.Figure:
    level = row["level"]
    fig = go.Figure()
    fig.add_shape(type="rect", x0=0.25, x1=0.75, y0=0, y1=100, line=dict(color="#ffffff", width=4), fillcolor="#1e40af")
    fig.add_shape(type="rect", x0=0.25, x1=0.75, y0=0, y1=level, line=dict(color="#00ffff", width=1), fillcolor="#00ffff")
    fig.add_annotation(x=0.5, y=level + 6, text=f"{level:.1f}%", showarrow=False, font=dict(size=22, color="#ffff00"))
    fig.add_annotation(x=0.02, y=83, text="IN", showarrow=False, font=dict(color="#00ff00", size=18))
    fig.add_annotation(x=0.98, y=18, text="OUT", showarrow=False, font=dict(color="#ff00f5", size=18))
    fig.update_xaxes(visible=False, range=[0, 1])
    fig.update_yaxes(visible=False, range=[0, 100])
    fig.update_layout(height=330, margin=dict(l=10, r=10, t=10, b=10), paper_bgcolor="#7c3aed", plot_bgcolor="#7c3aed")
    return fig


def alarm_items(row: dict) -> list[html.Div]:
    alarms = [
        ("LOW LEVEL SWITCH CHATTER", row["alarm_low"], "#00e5ff"),
        ("HI LEVEL", row["alarm_high"], "#ff0000"),
        ("PUMP STATUS NORMAL", row["pump_status"] == "running", "#00ff00"),
        ("TEMP HIGH", row["alarm_temp_high"], "#ff7a00"),
    ]
    out = []
    for name, active, color in alarms:
        out.append(html.Div(name, style={**CARD, "background": color if active else "#3b82f6", "marginBottom": "8px", "fontWeight": 800}))
    return out


def build_app() -> dash.Dash:
    app = dash.Dash(__name__)
    app.title = "Rainbow Tank HMI"
    app.layout = html.Div(style=APP_STYLE, children=[
        html.H2("Tank 42 Level Control - Rainbow Baseline", style={"margin": "0 0 10px", "color": "#facc15"}),
        html.Div(id="metrics", style={"display": "grid", "gridTemplateColumns": "repeat(4, minmax(140px, 1fr))", "gap": "10px", "marginBottom": "12px"}),
        html.Div(style={"display": "grid", "gridTemplateColumns": "1.2fr 1fr 0.9fr", "gap": "12px"}, children=[
            html.Div(style={**CARD, "background": "#be185d"}, children=[html.H3("Trend", style={"marginTop": 0}), dcc.Graph(id="trend", config={"displayModeBar": False})]),
            html.Div(style={**CARD, "background": "#7c3aed"}, children=[html.H3("Mimic", style={"marginTop": 0}), dcc.Graph(id="tank", config={"displayModeBar": False})]),
            html.Div(style={**CARD, "background": "#2563eb"}, children=[html.H3("Alarm List", style={"marginTop": 0}), html.Div(id="alarms")]),
        ]),
        dcc.Interval(id="tick", interval=1000, n_intervals=0),
    ])

    @app.callback(Output("metrics", "children"), Output("trend", "figure"), Output("tank", "figure"), Output("alarms", "children"), Input("tick", "n_intervals"))
    def refresh(_n):
        rows = read_rows()
        row = rows[-1]
        metrics = [
            metric_card("level", f"{row['level']:.1f}%", "#ff00f5", "PV"),
            metric_card("setpoint", f"{row['setpoint']:.1f}%", "#00ffff", "SP"),
            metric_card("valve", f"{row['valve_pct']:.0f}%", "#00ff00", "inlet valve"),
            metric_card("temperature", f"{row['temp']:.1f} F", "#ff7a00", row["pump_status"]),
        ]
        return metrics, trend_figure(rows), tank_figure(row), alarm_items(row)

    return app


app = build_app()
