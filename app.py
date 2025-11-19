# app.py
import dash
from dash import html, dcc
from dash.dependencies import Input, Output
import plotly.graph_objects as go
import plotly.express as px

from recession_model import compute_recession_probability

app = dash.Dash(__name__)

# -----------------------------------------------------------
# Layout
# -----------------------------------------------------------

app.layout = html.Div([
    html.H1("Recession Probability Dashboard (2026–27)", style={"textAlign": "center"}),

    html.Button("Refresh Signals", id="refresh", n_clicks=0),

    html.Div([
        dcc.Graph(id="probability_gauge", style={"width": "40%", "display": "inline-block"}),
        dcc.Graph(id="zscore_table", style={"width": "55%", "display": "inline-block"}),
    ]),

    html.H2("Underlying Indicator Charts", style={"marginTop": "40px"}),

    dcc.Graph(id="chart_spread"),
    dcc.Graph(id="chart_hy"),
    dcc.Graph(id="chart_unrate"),
    dcc.Graph(id="chart_cape"),
])

# -----------------------------------------------------------
# Callbacks
# -----------------------------------------------------------

@app.callback(
    [
        Output("probability_gauge", "figure"),
        Output("zscore_table", "figure"),
        Output("chart_spread", "figure"),
        Output("chart_hy", "figure"),
        Output("chart_unrate", "figure"),
        Output("chart_cape", "figure")
    ],
    Input("refresh", "n_clicks")
)
def update_dashboard(_):

    result = compute_recession_probability()

    p = result["probability"] * 100
    z = result["z"]
    raw = result["raw"]
    # -----------------------------
    # Gauge Chart
    # -----------------------------
    fig_gauge = go.Figure(go.Indicator(
        mode="gauge+number",
        value=p,
        title={"text": "Recession Probability (%)"},
        gauge={
            "axis": {"range": [0, 100]},
            "bar": {"color": "red"},
            "steps": [
                {"range": [0, 30], "color": "lightgreen"},
                {"range": [30, 60], "color": "yellow"},
                {"range": [60, 100], "color": "red"}
            ]
        }
    ))

    # -----------------------------
    # Z-Score Table
    # -----------------------------
    fig_table = go.Figure(
        data=[
            go.Table(
                header=dict(values=["Signal", "Z-Score"], fill_color="lightgrey"),
                cells=dict(values=[
                    list(z.keys()),
                    [f"{v:.2f}" for v in z.values()]
                ])
            )
        ]
    )

    # -----------------------------
    # Raw charts
    # -----------------------------

    fig_spread = px.line(raw["spread"], title="Yield Curve (2Y – 3M)")
    fig_hy = px.line(raw["hy"], title="HY OAS")
    fig_un = px.line(raw["unrate"], title="Unemployment Rate")
    fig_cape = px.line(raw["cape"], title="CAPE Ratio")

    return fig_gauge, fig_table, fig_spread, fig_hy, fig_un, fig_cape


# -----------------------------------------------------------
# Run app
# -----------------------------------------------------------

if __name__ == "__main__":
    app.run(debug=True)
