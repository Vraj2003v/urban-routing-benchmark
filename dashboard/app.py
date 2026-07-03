"""
app.py â€” Urban Routing Benchmark Dashboard v6
Tabs: Dashboard | About & Map
Usage: python dashboard/app.py  â†’  http://localhost:8050
"""

import sys, json, time
import pandas as pd
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
import dash
from dash import dcc, html, Input, Output, State
import dash_bootstrap_components as dbc
import plotly.graph_objects as go

BASE_DIR     = Path(__file__).resolve().parent.parent
RESULTS_DIR  = BASE_DIR / "results"
SNAPSHOT_DIR = BASE_DIR / "data" / "live_snapshots"
sys.path.insert(0, str(BASE_DIR))

TORONTO_TZ = ZoneInfo("America/Toronto")

app = dash.Dash(__name__, external_stylesheets=[dbc.themes.BOOTSTRAP],
                title="Urban Routing Benchmark",
                meta_tags=[{"name":"viewport","content":"width=device-width,initial-scale=1"}])
server = app.server

PG_COLOR  = "#185FA5"
N4J_COLOR = "#0F6E56"
REG_COLOR = "#D85A30"

# â”€â”€ Helpers â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

def list_files():
    """Scan the results directory for benchmark CSV files.
    
    Returns:
        list: Sorted list of CSV filenames excluding plan analysis files.
        
    Notes:
        Dashboard auto-refreshes every 15 seconds via dcc.Interval.
        New result files appear automatically without restarting the app.
        Files named with plan_ prefix are excluded as they are analysis outputs.
    """
    if not RESULTS_DIR.exists(): return []
    return sorted([f.name for f in RESULTS_DIR.glob("*.csv") if "plan" not in f.name])

def load_df(filename):
    path = RESULTS_DIR / filename
    if not path.exists(): return pd.DataFrame()
    try:
        df = pd.read_csv(path, parse_dates=["ts"])
        return df[df["latency_ms"] > 0].copy()
    except: return pd.DataFrame()

def is_run_active(filename):
    if not filename: return False
    path = RESULTS_DIR / filename
    if not path.exists(): return False
    return (time.time() - path.stat().st_mtime) < 5

def get_snapshot():
    if not SNAPSHOT_DIR.exists(): return None
    snaps = sorted(SNAPSHOT_DIR.glob("snapshot_*.json"), reverse=True)
    if not snaps: return None
    try:
        data = json.loads(snaps[0].read_text())
        return {
            "routes":    len(data.get("gtfs_rt_delays", {})),
            "incidents": data.get("on511_incidents", []),
            "delays":    data.get("gtfs_rt_delays", {}),
            "ts":        data.get("fetched_at","")[:19].replace("T"," "),
            "file":      snaps[0].name,
        }
    except: return None

# â”€â”€ Toronto incident hotspots (known locations) â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
TORONTO_HOTSPOTS = [
    (43.6426, -79.3871, "Gardiner Expressway", "Major"),
    (43.7731, -79.4137, "Hwy 401 / Allen Rd",  "Moderate"),
    (43.7060, -79.3986, "Yonge & Eglinton",    "Minor"),
    (43.6532, -79.3832, "DVP / Bloor",          "Major"),
    (43.8016, -79.3360, "Hwy 404 / Sheppard",  "Moderate"),
    (43.7640, -79.5488, "Hwy 427 / Finch",     "Minor"),
    (43.6950, -79.5470, "427 / Eglinton",       "Major"),
    (43.7280, -79.4620, "Allen Rd / Lawrence",  "Moderate"),
    (43.6629, -79.4197, "Gardiner / Spadina",   "Minor"),
    (43.7890, -79.2940, "Hwy 401 / Kennedy",   "Moderate"),
]

# â”€â”€ Build Toronto map using Plotly (no folium needed) â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

def build_map(snap, dark):
    bg = "#1A1D27" if dark else "#F4F5F7"
    map_style = "carto-darkmatter" if dark else "carto-positron"

    fig = go.Figure()

    # Toronto bounding box: 43.58,-79.64,43.86,-79.12
    # Draw OSM bounding box
    fig.add_trace(go.Scattermapbox(
        lat=[43.58, 43.86, 43.86, 43.58, 43.58],
        lon=[-79.64, -79.64, -79.12, -79.12, -79.64],
        mode="lines",
        line={"color": N4J_COLOR, "width": 2},
        name="OSM Data Region",
        hoverinfo="skip",
    ))

    # Incident hotspots from snapshot
    incidents = snap["incidents"] if snap else []
    if incidents:
        inc_lats = [i["lat"] for i in incidents]
        inc_lons = [i["lon"] for i in incidents]
        inc_text = [f"ðŸš¨ {i.get('type','Incident')}<br>Severity: {i.get('severity','Unknown')}"
                    for i in incidents]
        sev_color = {"Minor":"#ECC94B","Moderate":"#ED8936","Major":"#E53E3E","Critical":"#822727"}
        colors = [sev_color.get(i.get("severity","Minor"), "#ECC94B") for i in incidents]
        fig.add_trace(go.Scattermapbox(
            lat=inc_lats, lon=inc_lons,
            mode="markers",
            marker={"size":12, "color":colors, "opacity":0.9},
            text=inc_text,
            hovertemplate="%{text}<extra></extra>",
            name=f"511 ON Incidents ({len(incidents)})",
        ))

    # Known hotspot labels
    for lat, lon, name, sev in TORONTO_HOTSPOTS:
        col = {"Minor":"#ECC94B","Moderate":"#ED8936","Major":"#E53E3E"}.get(sev,"#888")
        fig.add_trace(go.Scattermapbox(
            lat=[lat], lon=[lon],
            mode="markers+text",
            marker={"size":14,"color":col,"opacity":0.7},
            text=[name],
            textposition="top right",
            textfont={"size":10,"color":col},
            hovertemplate=f"<b>{name}</b><br>Severity: {sev}<extra></extra>",
            name=name,
            showlegend=False,
        ))

    # TTC route markers (sample key stops)
    ttc_stops = [
        (43.6544, -79.3807, "Union Station"),
        (43.6709, -79.3870, "Bloor-Yonge"),
        (43.7075, -79.3987, "Eglinton"),
        (43.7282, -79.4000, "Lawrence"),
        (43.7614, -79.4111, "Sheppard-Yonge"),
        (43.7957, -79.4147, "Finch"),
        (43.6446, -79.4033, "Spadina"),
        (43.6481, -79.4413, "Kipling"),
        (43.7731, -79.2630, "Kennedy"),
    ]
    stop_lats = [s[0] for s in ttc_stops]
    stop_lons = [s[1] for s in ttc_stops]
    stop_text = [f"ðŸš‡ {s[2]}" for s in ttc_stops]
    fig.add_trace(go.Scattermapbox(
        lat=stop_lats, lon=stop_lons,
        mode="markers",
        marker={"size":10,"color":PG_COLOR,"opacity":0.8,"symbol":"rail"},
        text=stop_text,
        hovertemplate="%{text}<extra></extra>",
        name="TTC Key Stops",
    ))

    fig.update_layout(
        mapbox={"style": map_style, "center":{"lat":43.72,"lon":-79.38}, "zoom":10.5},
        paper_bgcolor="rgba(0,0,0,0)",
        margin={"l":0,"r":0,"t":0,"b":0},
        legend={"bgcolor":"rgba(255,255,255,0.85)","bordercolor":"#ddd",
                "borderwidth":1,"font":{"size":11},"x":0.01,"y":0.99},
        uirevision="map",
    )
    return fig

# â”€â”€ Layout â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

app.layout = html.Div([
    dcc.Store(id="dark-mode", data=False),
    dcc.Interval(id="interval", interval=2000, n_intervals=0),

    # â”€â”€ Navbar â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    html.Div([
        html.Div([
            html.Div([
                html.Span("â—ˆ", style={"color":N4J_COLOR,"fontSize":"22px","marginRight":"10px"}),
                html.Span("Urban Routing Benchmark",
                          style={"fontSize":"16px","fontWeight":"700","letterSpacing":"-0.3px"}),
                html.Span(" v6", style={"fontSize":"11px","color":"#888","marginLeft":"4px"}),
            ], style={"display":"flex","alignItems":"center"}),

            dcc.Dropdown(id="file-sel", placeholder="Select result fileâ€¦", clearable=False,
                         style={"width":"260px","fontSize":"13px"}),

            html.Div([
                html.Div(id="live-badge"),
                html.Div(id="run-status"),
                html.Button("ðŸŒ™", id="dark-btn", n_clicks=0,
                            style={"background":"none","border":"1px solid #ddd",
                                   "borderRadius":"8px","padding":"5px 10px",
                                   "cursor":"pointer","fontSize":"15px","marginLeft":"10px"}),
            ], style={"display":"flex","alignItems":"center"}),
        ], style={"display":"flex","justifyContent":"space-between","alignItems":"center",
                  "maxWidth":"1400px","margin":"0 auto","padding":"0 24px","height":"54px"}),
    ], id="navbar"),

    html.Div(id="status-bar"),

    # â”€â”€ Tabs â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    html.Div([
        dcc.Tabs(id="tabs", value="tab-dashboard",
                 style={"maxWidth":"1400px","margin":"0 auto","padding":"0 24px"},
                 children=[
            dcc.Tab(label="ðŸ“Š  Dashboard", value="tab-dashboard",
                    style={"fontWeight":"500","fontSize":"13px","padding":"10px 20px"},
                    selected_style={"fontWeight":"600","fontSize":"13px",
                                    "borderTop":f"3px solid {N4J_COLOR}","padding":"10px 20px"}),
            dcc.Tab(label="ðŸ—ºï¸  Map & About", value="tab-about",
                    style={"fontWeight":"500","fontSize":"13px","padding":"10px 20px"},
                    selected_style={"fontWeight":"600","fontSize":"13px",
                                    "borderTop":f"3px solid {PG_COLOR}","padding":"10px 20px"}),
        ]),
    ], style={"background":"#fff","borderBottom":"1px solid #e2e8f0"}),

    html.Div(id="tab-content"),

    # â”€â”€ Footer â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    html.Div([
        html.Span("Urban Routing Benchmark Â· Group 9 Â· University of Windsor",
                  style={"fontSize":"12px","color":"#888"}),
        html.Div(id="footer-ts", style={"fontSize":"12px","color":"#bbb"}),
    ], style={"display":"flex","justifyContent":"space-between",
              "padding":"14px 24px","borderTop":"1px solid #e2e8f0",
              "maxWidth":"1400px","margin":"0 auto"}),

], id="page-root",
   style={"minHeight":"100vh","background":"#F4F5F7",
          "fontFamily":"-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif"})


# â”€â”€ Dark mode â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
@app.callback(
    Output("dark-mode","data"),
    Input("dark-btn","n_clicks"),
    State("dark-mode","data"),
    prevent_initial_call=True,
)
def toggle_dark(n, current): return not current

@app.callback(
    Output("page-root","style"),
    Output("navbar","style"),
    Output("dark-btn","children"),
    Input("dark-mode","data"),
)
def apply_theme(dark):
    if dark:
        page = {"minHeight":"100vh","background":"#0F1117","color":"#F7FAFC",
                "fontFamily":"-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif"}
        nav  = {"background":"#1A1D27","borderBottom":"1px solid #2D3748",
                "position":"sticky","top":"0","zIndex":"100",
                "boxShadow":"0 1px 4px rgba(0,0,0,0.4)","color":"#F7FAFC"}
    else:
        page = {"minHeight":"100vh","background":"#F4F5F7","color":"#1A202C",
                "fontFamily":"-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif"}
        nav  = {"background":"#FFFFFF","borderBottom":"1px solid #E2E8F0",
                "position":"sticky","top":"0","zIndex":"100",
                "boxShadow":"0 1px 3px rgba(0,0,0,0.06)"}
    return page, nav, "â˜€ï¸" if dark else "ðŸŒ™"


# â”€â”€ File list â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
@app.callback(
    Output("file-sel","options"), Output("file-sel","value"),
    Input("interval","n_intervals"), State("file-sel","value"),
)
def refresh_files(n, current):
    files = list_files()
    opts  = [{"label":f,"value":f} for f in files]
    if current and current in files: return opts, current
    default = next((f for f in reversed(files) if "edt" in f),
                   next((f for f in reversed(files) if "live" in f),
                        files[-1] if files else None))
    return opts, default


# â”€â”€ Tab content router â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
@app.callback(
    Output("tab-content","children"),
    Input("tabs","value"),
    Input("file-sel","value"),
    Input("interval","n_intervals"),
    Input("dark-mode","data"),
    Input("window","value") if False else Input("tabs","value"),  # placeholder
)
def render_tab(tab, filename, n, dark, *args):
    if tab == "tab-about":
        return build_about_tab(dark)
    return build_dashboard_tab()

def build_dashboard_tab():
    return html.Div([
        html.Div(id="kpi-row",
                 style={"display":"grid","gridTemplateColumns":"repeat(6,1fr)",
                        "gap":"12px","padding":"16px 24px",
                        "maxWidth":"1400px","margin":"0 auto"}),
        html.Div(id="winner-row",
                 style={"padding":"0 24px 12px","maxWidth":"1400px","margin":"0 auto"}),
        html.Div([
            html.Div([
                html.Div([
                    html.Div([
                        html.Span("Query Latency Over Time",
                                  style={"fontSize":"13px","fontWeight":"600"}),
                        html.Span(" â€” rolling average",
                                  style={"fontSize":"12px","color":"#888","marginLeft":"6px"}),
                    ]),
                    html.Div([
                        html.Label("Window",style={"fontSize":"11px","color":"#888","marginRight":"6px"}),
                        html.Div(dcc.Slider(id="window",min=5,max=100,step=5,value=20,
                                   marks={5:"5",50:"50",100:"100"},
                                   tooltip={"always_visible":False}),
                                   style={"width":"130px","display":"inline-block","verticalAlign":"middle"}),
                        dcc.RadioItems(id="show-reg",
                            options=[{"label":" Regressions","value":"yes"},
                                     {"label":" Hide","value":"no"}],
                            value="yes",inline=True,
                            style={"fontSize":"12px","marginLeft":"14px","display":"inline-block"}),
                    ],style={"display":"flex","alignItems":"center","flexWrap":"wrap","gap":"4px"}),
                ],style={"display":"flex","justifyContent":"space-between","alignItems":"center",
                          "padding":"14px 16px 0","flexWrap":"wrap","gap":"8px"}),
                dcc.Graph(id="chart-latency",config={"displayModeBar":True},style={"height":"300px"}),
            ],id="card-lat",style={"flex":"1","borderRadius":"12px","overflow":"hidden",
                                    "border":"1px solid #e2e8f0","background":"#fff"}),
            html.Div([
                html.Div([html.Span("Latency Distribution",style={"fontSize":"13px","fontWeight":"600"})],
                         style={"padding":"14px 16px 0"}),
                dcc.Graph(id="chart-box",config={"displayModeBar":False},style={"height":"300px"}),
            ],id="card-box",style={"width":"300px","borderRadius":"12px","overflow":"hidden",
                                    "border":"1px solid #e2e8f0","background":"#fff"}),
        ],style={"display":"flex","gap":"14px","padding":"0 24px 14px","maxWidth":"1400px","margin":"0 auto"}),

        html.Div([
            html.Div([
                html.Div([html.Span("Plan Stability",style={"fontSize":"13px","fontWeight":"600"}),
                          html.Span(" â€” âœ• = optimizer replanned",style={"fontSize":"12px","color":"#888","marginLeft":"6px"})],
                         style={"padding":"14px 16px 0"}),
                dcc.Graph(id="chart-plan",config={"displayModeBar":False},style={"height":"200px"}),
            ],id="card-plan",style={"flex":"1","borderRadius":"12px","overflow":"hidden",
                                     "border":"1px solid #e2e8f0","background":"#fff"}),
            html.Div([
                html.Div([html.Span("Percentile Comparison",style={"fontSize":"13px","fontWeight":"600"}),
                          html.Span(" â€” P50/P75/P95/P99",style={"fontSize":"12px","color":"#888","marginLeft":"6px"})],
                         style={"padding":"14px 16px 0"}),
                dcc.Graph(id="chart-pct",config={"displayModeBar":False},style={"height":"200px"}),
            ],id="card-pct",style={"width":"360px","borderRadius":"12px","overflow":"hidden",
                                    "border":"1px solid #e2e8f0","background":"#fff"}),
        ],style={"display":"flex","gap":"14px","padding":"0 24px 14px","maxWidth":"1400px","margin":"0 auto"}),

        html.Div([
            html.Div(id="reg-table",style={"flex":"1","borderRadius":"12px","overflow":"hidden",
                                            "border":"1px solid #e2e8f0","background":"#fff"}),
            html.Div(id="summary-card",style={"width":"320px","borderRadius":"12px","overflow":"hidden",
                                               "border":"1px solid #e2e8f0","background":"#fff"}),
        ],style={"display":"flex","gap":"14px","padding":"0 24px 24px","maxWidth":"1400px","margin":"0 auto"}),
    ])

def build_about_tab(dark):
    bg    = "#0F1117" if dark else "#F4F5F7"
    surf  = "#1A1D27" if dark else "#FFFFFF"
    brd   = "#2D3748" if dark else "#E2E8F0"
    txt   = "#F7FAFC" if dark else "#1A202C"
    muted = "#A0AEC0" if dark else "#718096"

    snap = get_snapshot()
    n_routes   = snap["routes"]    if snap else 150
    n_incidents = len(snap["incidents"]) if snap else 24

    def card(icon, title, body, color="#185FA5"):
        return html.Div([
            html.Div([
                html.Span(icon, style={"fontSize":"28px"}),
                html.Span(title, style={"fontSize":"14px","fontWeight":"600","color":color,
                                         "marginLeft":"10px"}),
            ], style={"display":"flex","alignItems":"center","marginBottom":"10px"}),
            html.P(body, style={"fontSize":"13px","color":muted,"lineHeight":"1.7","margin":"0"}),
        ], style={"background":surf,"border":f"1px solid {brd}","borderRadius":"12px",
                  "padding":"18px 20px"})

    def step(num, title, body, color):
        return html.Div([
            html.Div([
                html.Div(str(num), style={"width":"28px","height":"28px","borderRadius":"50%",
                                           "background":color,"color":"#fff","display":"flex",
                                           "alignItems":"center","justifyContent":"center",
                                           "fontSize":"13px","fontWeight":"700","flexShrink":"0"}),
                html.Div([
                    html.P(title, style={"fontWeight":"600","fontSize":"13px","margin":"0 0 4px","color":txt}),
                    html.P(body,  style={"fontSize":"12px","color":muted,"margin":"0","lineHeight":"1.6"}),
                ], style={"marginLeft":"12px"}),
            ], style={"display":"flex","alignItems":"flex-start"}),
        ], style={"padding":"12px 0","borderBottom":f"1px solid {brd}"})

    return html.Div([

        # â”€â”€ Hero section â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
        html.Div([
            html.Div([
                html.H2("What is this project doing?",
                        style={"fontSize":"24px","fontWeight":"700","margin":"0 0 12px","color":txt}),
                html.P([
                    "This dashboard shows a live experiment comparing two different types of databases ",
                    "â€” ", html.Strong("Neo4j", style={"color":N4J_COLOR}), " and ",
                    html.Strong("PostgreSQL", style={"color":PG_COLOR}),
                    " â€” to find out which one is better at handling ",
                    html.Strong("real-time traffic routing"), " for a city like Toronto."
                ], style={"fontSize":"14px","color":muted,"lineHeight":"1.8","maxWidth":"700px"}),
            ], style={"flex":"1"}),
            html.Div([
                html.Div([
                    html.P("ðŸ™ï¸", style={"fontSize":"40px","margin":"0","textAlign":"center"}),
                    html.P("Toronto, ON", style={"fontWeight":"600","fontSize":"13px",
                                                  "margin":"8px 0 2px","textAlign":"center","color":txt}),
                    html.P("38,170 intersections\n99,638 road segments",
                           style={"fontSize":"12px","color":muted,"textAlign":"center","whiteSpace":"pre"}),
                ], style={"background":surf,"border":f"1px solid {brd}","borderRadius":"12px",
                          "padding":"16px 20px","minWidth":"160px"}),
            ]),
        ], style={"display":"flex","alignItems":"center","gap":"20px",
                  "padding":"24px 24px 16px","maxWidth":"1400px","margin":"0 auto"}),

        # â”€â”€ Explain cards â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
        html.Div([
            card("ðŸ—ƒï¸", "What is a Database?",
                 "A database is like a giant, super-organised filing cabinet that a computer uses to store and find information very quickly. In this project, the database stores a map of Toronto's roads â€” every street, intersection, and traffic detail.",
                 "#553C9A"),
            card("ðŸŸ ", "Neo4j â€” Graph Database",
                 "Neo4j thinks of roads like a web of connected dots (intersections) and lines (roads). It's designed specifically for networks, so finding the shortest route between two places feels natural. Think of it like Google Maps' internal brain.",
                 N4J_COLOR),
            card("ðŸ”µ", "PostgreSQL â€” Relational Database",
                 "PostgreSQL stores roads in spreadsheet-like tables (rows and columns). It's the world's most popular general-purpose database. We added a routing extension called pgRouting to make it handle map queries.",
                 PG_COLOR),
            card("ðŸš¦", "What are Edge Weights?",
                 "Every road segment has a 'cost' â€” how long it takes to drive through it. In real life this changes constantly: traffic jams, accidents, road closures. We call these changes 'dynamic edge-weight updates'. This is what we're testing!",
                 REG_COLOR),
        ], style={"display":"grid","gridTemplateColumns":"repeat(4,1fr)","gap":"12px",
                  "padding":"0 24px 16px","maxWidth":"1400px","margin":"0 auto"}),

        # â”€â”€ How it works steps â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
        html.Div([
            html.Div([
                html.P("How the experiment works",
                       style={"fontSize":"15px","fontWeight":"700","margin":"0 0 4px","color":txt}),
                html.P("Step by step â€” what's actually happening right now",
                       style={"fontSize":"12px","color":muted,"margin":"0 0 16px"}),
                step(1, "Real Toronto road map loaded",
                     f"We downloaded Toronto's entire road network from OpenStreetMap â€” {38170:,} intersections and {99638:,} road segments. Both databases have the same map loaded.",
                     "#553C9A"),
                step(2, "Live traffic data collected",
                     f"We collected {n_routes} TTC bus/streetcar routes with real delay data, and placed {n_incidents} traffic incident markers at known Toronto hotspots (Gardiner, Hwy 401, DVP, etc.).",
                     N4J_COLOR),
                step(3, "Road costs updated every 2 seconds",
                     "Every 2 seconds, we pick 50 random road segments and update their travel time based on how close they are to a real incident. A road near a major accident gets a 4Ã— cost penalty.",
                     REG_COLOR),
                step(4, "Shortest path queries fired at both databases",
                     "At the same time, we ask both databases 5 routing questions per second â€” 'what's the fastest route from point A to point B?' â€” and measure how long each database takes to answer.",
                     PG_COLOR),
                step(5, "Results measured and compared",
                     "We record every query's response time and whether the database had to recompute its strategy (called a 'plan regression'). The charts on the Dashboard tab show this in real time.",
                     "#0F6E56"),
            ], style={"background":surf,"border":f"1px solid {brd}","borderRadius":"12px",
                      "padding":"20px 24px","flex":"1"}),

            # What the numbers mean
            html.Div([
                html.P("What the numbers mean",
                       style={"fontSize":"15px","fontWeight":"700","margin":"0 0 16px","color":txt}),
                html.Div([
                    html.Div([
                        html.P("Median Latency", style={"fontSize":"11px","color":muted,"margin":"0 0 2px","fontWeight":"600","textTransform":"uppercase"}),
                        html.P("The typical response time. Lower = faster. Under 200ms feels instant to a user.", style={"fontSize":"12px","color":muted,"lineHeight":"1.6","margin":"0"}),
                    ], style={"padding":"10px 0","borderBottom":f"1px solid {brd}"}),
                    html.Div([
                        html.P("P95 / P99 Latency", style={"fontSize":"11px","color":muted,"margin":"0 0 2px","fontWeight":"600","textTransform":"uppercase"}),
                        html.P("The worst-case times (95th/99th percentile). High P99 means some users get very slow responses.", style={"fontSize":"12px","color":muted,"lineHeight":"1.6","margin":"0"}),
                    ], style={"padding":"10px 0","borderBottom":f"1px solid {brd}"}),
                    html.Div([
                        html.P("Plan Switches", style={"fontSize":"11px","color":muted,"margin":"0 0 2px","fontWeight":"600","textTransform":"uppercase"}),
                        html.P("How many times the database had to rethink its strategy. High number = the database is struggling with changing road costs.", style={"fontSize":"12px","color":muted,"lineHeight":"1.6","margin":"0"}),
                    ], style={"padding":"10px 0","borderBottom":f"1px solid {brd}"}),
                    html.Div([
                        html.P("Cache Hit Rate", style={"fontSize":"11px","color":muted,"margin":"0 0 2px","fontWeight":"600","textTransform":"uppercase"}),
                        html.P("How often the database reused its previous answer strategy. 100% = very efficient. 0% = always recomputing.", style={"fontSize":"12px","color":muted,"lineHeight":"1.6","margin":"0"}),
                    ], style={"padding":"10px 0"}),
                ]),

                html.Div([
                    html.P("Why does this matter?",
                           style={"fontSize":"14px","fontWeight":"700","margin":"0 0 10px","color":txt}),
                    html.P("Apps like Google Maps, Waze, or a city's emergency dispatch system need to find the fastest route in real time â€” while traffic is constantly changing. Choosing the wrong database could mean slower route calculations, which in an emergency could cost lives. This research helps city planners make the right choice.",
                           style={"fontSize":"12px","color":muted,"lineHeight":"1.7","margin":"0"}),
                ], style={"background":f"{N4J_COLOR}0d","border":f"1px solid {N4J_COLOR}25",
                          "borderRadius":"10px","padding":"14px","marginTop":"16px"}),

            ], style={"background":surf,"border":f"1px solid {brd}","borderRadius":"12px",
                      "padding":"20px 24px","width":"340px"}),
        ], style={"display":"flex","gap":"14px","padding":"0 24px 16px",
                  "maxWidth":"1400px","margin":"0 auto"}),

        # â”€â”€ Map â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
        html.Div([
            html.Div([
                html.P("ðŸ—ºï¸  Toronto Road Network & Live Incident Map",
                       style={"fontSize":"15px","fontWeight":"700","margin":"0 0 4px","color":txt}),
                html.P("Orange/red markers = traffic incidents Â· Blue markers = TTC key stations Â· Green box = OSM data region",
                       style={"fontSize":"12px","color":muted,"margin":"0"}),
            ], style={"padding":"16px 20px 0"}),
            dcc.Graph(id="map-chart", config={"displayModeBar":True,"scrollZoom":True},
                      style={"height":"480px"}),
        ], style={"background":surf,"border":f"1px solid {brd}","borderRadius":"12px",
                  "margin":"0 24px 24px","maxWidth":"1352px","marginLeft":"auto",
                  "marginRight":"auto","overflow":"hidden"}),

    ], style={"background":bg})


# â”€â”€ Tab router callback â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
@app.callback(
    Output("tab-content","children"),
    Input("tabs","value"),
    Input("dark-mode","data"),
)
def render_tab(tab, dark):
    if tab == "tab-about":
        return build_about_tab(dark)
    return build_dashboard_tab()


# â”€â”€ Map update â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
@app.callback(
    Output("map-chart","figure"),
    Input("interval","n_intervals"),
    Input("dark-mode","data"),
)
def update_map(n, dark):
    snap = get_snapshot()
    return build_map(snap, dark)


# â”€â”€ Status bar + badges â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
@app.callback(
    Output("status-bar","children"),
    Output("live-badge","children"),
    Output("run-status","children"),
    Output("footer-ts","children"),
    Input("interval","n_intervals"),
    Input("file-sel","value"),
    Input("dark-mode","data"),
)
def update_status(n, filename, dark):
    muted = "#A0AEC0" if dark else "#718096"
    snap = get_snapshot()
    if snap:
        has  = snap["routes"] > 0 or len(snap["incidents"]) > 0
        dc   = "#1D9E75" if has else "#BA7517"
        lbl  = "LIVE DATA ACTIVE" if has else "SYNTHETIC FALLBACK"
        det  = (f"{snap['routes']} TTC routes Â· {len(snap['incidents'])} incidents Â· "
                f"{snap['file']} Â· {snap['ts']} EDT")
        badge = html.Div([
            html.Span("â—",style={"color":dc,"fontSize":"10px","marginRight":"5px"}),
            html.Span(lbl,style={"fontSize":"11px","fontWeight":"700","color":dc,"letterSpacing":"0.4px"}),
        ],style={"display":"flex","alignItems":"center","padding":"3px 10px",
                  "background":f"{dc}18","borderRadius":"20px","border":f"1px solid {dc}35"})
        sbar = html.Div([
            html.Div([
                html.Span("â—",style={"color":dc,"fontSize":"11px","marginRight":"6px"}),
                html.Span(lbl+" Â· ",style={"fontSize":"12px","fontWeight":"700","color":dc}),
                html.Span(det,style={"fontSize":"12px","color":muted}),
            ],style={"display":"flex","alignItems":"center","maxWidth":"1400px","margin":"0 auto","flexWrap":"wrap"}),
        ],style={"padding":"7px 24px","background":f"{dc}0c","borderBottom":f"1px solid {dc}22"})
    else:
        badge = html.Div()
        sbar  = html.Div()

    active = is_run_active(filename) if filename else False
    run_pill = html.Div([
        html.Span("â¬¤ ",style={"color":"#E53E3E","fontSize":"9px"}),
        html.Span("RECORDING",style={"fontSize":"10px","fontWeight":"700",
                                      "color":"#E53E3E","letterSpacing":"0.4px"}),
    ],style={"display":"flex","alignItems":"center","padding":"3px 9px",
              "background":"#FFF5F5","borderRadius":"20px","border":"1px solid #FEB2B2",
              "marginLeft":"8px"}) if active else html.Div()

    ts = datetime.now(TORONTO_TZ).strftime("Updated %H:%M:%S EDT")
    return sbar, badge, run_pill, ts


# â”€â”€ Main dashboard data callback â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
@app.callback(
    Output("kpi-row","children"),
    Output("winner-row","children"),
    Output("chart-latency","figure"),
    Output("chart-box","figure"),
    Output("chart-plan","figure"),
    Output("chart-pct","figure"),
    Output("reg-table","children"),
    Output("summary-card","children"),
    Output("card-lat","style"),
    Output("card-box","style"),
    Output("card-plan","style"),
    Output("card-pct","style"),
    Output("reg-table","style"),
    Output("summary-card","style"),
    Input("file-sel","value"),
    Input("window","value"),
    Input("show-reg","value"),
    Input("dark-mode","data"),
    Input("interval","n_intervals"),
)
def update_dashboard(filename, window, show_reg, dark, n):
    if dark:
        bg,surf,brd = "#0F1117","#1A1D27","#2D3748"
        txt,muted,plot,grid = "#F7FAFC","#A0AEC0","#1A1D27","#2D3748"
    else:
        bg,surf,brd = "#F4F5F7","#FFFFFF","#E2E8F0"
        txt,muted,plot,grid = "#1A202C","#718096","#FAFAFA","#EDF2F7"

    card_s   = {"borderRadius":"12px","overflow":"hidden","border":f"1px solid {brd}","background":surf}
    lat_s    = dict(card_s,flex="1")
    box_s    = dict(card_s,width="300px")
    plan_s   = dict(card_s,flex="1")
    pct_s    = dict(card_s,width="360px")
    reg_s    = dict(card_s,flex="1")
    sum_s    = dict(card_s,width="320px")

    def efig(msg="Select a result file to begin"):
        f = go.Figure()
        f.update_layout(paper_bgcolor="rgba(0,0,0,0)",plot_bgcolor=plot,
                        margin={"l":0,"r":0,"t":0,"b":0},font={"color":txt},
                        xaxis={"visible":False},yaxis={"visible":False},
                        annotations=[{"text":msg,"showarrow":False,
                                       "font":{"size":13,"color":muted},"x":0.5,"y":0.5}])
        return f

    empty = ([],html.Div(),efig(),efig(),efig(),efig(),html.Div(),html.Div(),
             lat_s,box_s,plan_s,pct_s,reg_s,sum_s)

    if not filename: return empty
    df = load_df(filename)
    if df.empty: return empty

    pg  = df[df["system"]=="postgres"]
    n4j = df[df["system"]=="neo4j"]

    def q(s,p):   return s["latency_ms"].quantile(p/100) if len(s) else 0
    def mean_(s): return s["latency_ms"].mean() if len(s) else 0
    def med(s):   return f"{q(s,50):.1f} ms" if len(s) else "â€”"
    def p95(s):   return f"{q(s,95):.1f} ms" if len(s) else "â€”"
    def cnt(s):   return f"{len(s):,}"
    def pchg(s):
        if s.empty: return 0
        ss=s.sort_values("ts")
        return int((ss["plan_hash"]!=ss["plan_hash"].shift(1)).sum())

    pg_ch=pchg(pg); n4j_ch=pchg(n4j)
    n4j_wins = mean_(n4j)<mean_(pg) if len(pg) and len(n4j) else False

    def kpi(label,val,sub,col,hl=False):
        return html.Div([
            html.P(label,style={"fontSize":"10px","color":muted,"margin":"0 0 5px",
                                 "fontWeight":"600","textTransform":"uppercase","letterSpacing":"0.6px"}),
            html.P(val,style={"fontSize":"22px","fontWeight":"700","margin":"0","color":col,"lineHeight":"1"}),
            html.P(sub,style={"fontSize":"11px","color":muted,"margin":"3px 0 0"}),
        ],style={"background":surf,"border":f"{'2px' if hl else '1px'} solid {col if hl else brd}",
                  "borderRadius":"10px","padding":"14px 16px"})

    kpis=[
        kpi("PG Queries",cnt(pg),f"P95 Â· {p95(pg)}",PG_COLOR,not n4j_wins),
        kpi("Neo4j Queries",cnt(n4j),f"P95 Â· {p95(n4j)}",N4J_COLOR,n4j_wins),
        kpi("PG Median",med(pg),"milliseconds",PG_COLOR,not n4j_wins),
        kpi("Neo4j Median",med(n4j),"milliseconds",N4J_COLOR,n4j_wins),
        kpi("PG Replans",str(pg_ch),"cache misses",REG_COLOR if pg_ch>5 else muted),
        kpi("Neo4j Replans",str(n4j_ch),"cache misses",REG_COLOR if n4j_ch>5 else muted),
    ]

    if len(pg) and len(n4j):
        ratio=mean_(pg)/mean_(n4j) if mean_(n4j)>0 else 1
        wc=N4J_COLOR if n4j_wins else PG_COLOR
        wname="Neo4j" if n4j_wins else "PostgreSQL"
        wratio=f"{ratio:.1f}Ã—" if n4j_wins else f"{1/ratio:.1f}Ã—"
        winner=html.Div([
            html.Span("ðŸ† ",style={"fontSize":"15px"}),
            html.Span(f"{wname} is {wratio} faster  Â·  Neo4j {mean_(n4j):.0f} ms vs PostgreSQL {mean_(pg):.0f} ms mean  Â·  PG replans: {pg_ch}  Â·  Neo4j replans: {n4j_ch}",
                      style={"fontSize":"13px","fontWeight":"600","color":wc}),
        ],style={"padding":"10px 16px","background":f"{wc}0d","border":f"1px solid {wc}28",
                  "borderRadius":"10px","display":"flex","alignItems":"center"})
    else: winner=html.Div()

    BL=dict(paper_bgcolor="rgba(0,0,0,0)",plot_bgcolor=plot,font={"color":txt,"size":11},
            margin={"l":52,"r":16,"t":12,"b":48},
            xaxis={"showgrid":False,"color":muted,"linecolor":brd,"tickfont":{"size":10}},
            yaxis={"gridcolor":grid,"color":muted,"linecolor":brd,"tickfont":{"size":10}},
            hovermode="x unified",uirevision=filename,
            legend={"orientation":"h","y":-0.28,"font":{"size":11},"bgcolor":"rgba(0,0,0,0)"})

    fl=go.Figure()
    for sub,nm,col,ds in[(pg,"PostgreSQL",PG_COLOR,"solid"),(n4j,"Neo4j",N4J_COLOR,"dot")]:
        if sub.empty: continue
        s=sub.sort_values("ts"); r=s["latency_ms"].rolling(window,min_periods=1).mean()
        fl.add_trace(go.Scatter(x=s["ts"],y=r.round(2),mode="lines",name=nm,
                                 line={"color":col,"width":2.5,"dash":ds},
                                 hovertemplate=f"<b>{nm}</b>: %{{y:.1f}} ms<extra></extra>"))
        if show_reg=="yes":
            chg=s[s["plan_hash"]!=s["plan_hash"].shift(1)]
            if not chg.empty:
                fl.add_trace(go.Scatter(x=chg["ts"],y=r[chg.index].round(2),mode="markers",
                                         name=f"{nm} replan",
                                         marker={"color":REG_COLOR,"size":10,"symbol":"x",
                                                 "line":{"width":2.5,"color":REG_COLOR}},
                                         hovertemplate="<b>Replan</b> @ %{x}<extra></extra>"))
    fl.update_layout(**BL); fl.update_layout(yaxis_title="Latency (ms)")

    fb=go.Figure()
    for sub,nm,col in[(pg,"PostgreSQL",PG_COLOR),(n4j,"Neo4j",N4J_COLOR)]:
        if sub.empty: continue
        fb.add_trace(go.Box(y=sub["latency_ms"].round(2),name=nm,marker_color=col,line_color=col,
                             fillcolor="rgba(150,150,150,0.10)",boxmean="sd",boxpoints="outliers"))
    fb.update_layout(**BL); fb.update_layout(showlegend=False,yaxis_title="Latency (ms)",
                                               margin={"l":52,"r":16,"t":12,"b":28})

    fp=go.Figure()
    for sub,nm,col in[(n4j,"Neo4j",N4J_COLOR),(pg,"PostgreSQL",PG_COLOR)]:
        if sub.empty: continue
        s=sub.sort_values("ts")
        fp.add_trace(go.Scatter(x=s["ts"],y=[nm]*len(s),mode="markers",
                                 marker={"color":"rgba(150,150,150,0.13)","size":4},
                                 name=nm,showlegend=False))
        chg=s[s["plan_hash"]!=s["plan_hash"].shift(1)]
        if not chg.empty:
            fp.add_trace(go.Scatter(x=chg["ts"],y=[nm]*len(chg),mode="markers",
                                     name=f"{nm} replan ({len(chg)})",
                                     marker={"color":REG_COLOR,"size":11,"symbol":"x",
                                             "line":{"width":2.5,"color":REG_COLOR}},
                                     hovertemplate="<b>Replan</b> @ %{x}<extra></extra>"))
    fp.update_layout(**BL); fp.update_layout(margin={"l":100,"r":16,"t":12,"b":48})

    pcts=[50,75,95,99]
    pg_v=[round(q(pg,p),1) for p in pcts]; n4j_v=[round(q(n4j,p),1) for p in pcts]
    fpc=go.Figure()
    fpc.add_trace(go.Bar(name="PostgreSQL",x=[f"P{p}" for p in pcts],y=pg_v,
                          marker_color="rgba(24,95,165,0.85)",
                          text=[f"{v:.0f}" for v in pg_v],textposition="outside",
                          textfont={"size":10,"color":txt}))
    fpc.add_trace(go.Bar(name="Neo4j",x=[f"P{p}" for p in pcts],y=n4j_v,
                          marker_color="rgba(15,110,86,0.85)",
                          text=[f"{v:.0f}" for v in n4j_v],textposition="outside",
                          textfont={"size":10,"color":txt}))
    fpc.update_layout(**BL); fpc.update_layout(barmode="group",yaxis_title="ms",
                                                 margin={"l":45,"r":16,"t":22,"b":40})

    rows=[]
    for sub,nm,col in[(pg,"PostgreSQL",PG_COLOR),(n4j,"Neo4j",N4J_COLOR)]:
        if sub.empty: continue
        s=sub.sort_values("ts"); chg=s[s["plan_hash"]!=s["plan_hash"].shift(1)].head(5)
        for _,row in chg.iterrows():
            rows.append(html.Tr([
                html.Td(html.Span(nm,style={"color":col,"fontWeight":"600","fontSize":"11px"}),
                        style={"padding":"8px 14px","borderBottom":f"1px solid {brd}"}),
                html.Td(str(row["ts"])[:19],style={"padding":"8px 14px","fontSize":"11px",
                                                    "color":muted,"borderBottom":f"1px solid {brd}"}),
                html.Td(f"{row['latency_ms']:.1f} ms",style={"padding":"8px 14px","fontSize":"12px",
                                                              "fontWeight":"500","borderBottom":f"1px solid {brd}"}),
                html.Td(html.Span("REGRESSION",style={"fontSize":"9px","fontWeight":"700","color":REG_COLOR,
                                                        "background":f"{REG_COLOR}15","padding":"2px 7px",
                                                        "borderRadius":"4px","letterSpacing":"0.5px"}),
                        style={"padding":"8px 14px","borderBottom":f"1px solid {brd}"}),
            ]))

    th={"padding":"7px 14px","fontSize":"10px","color":muted,"fontWeight":"600",
        "textTransform":"uppercase","letterSpacing":"0.5px","borderBottom":f"2px solid {brd}",
        "textAlign":"left","background":bg}
    reg=html.Div([
        html.P("Plan Regression Events",style={"fontSize":"13px","fontWeight":"600",
               "padding":"14px 16px 8px","margin":"0","borderBottom":f"1px solid {brd}","color":txt}),
        html.Table([
            html.Thead(html.Tr([html.Th("System",th),html.Th("Timestamp",th),
                                 html.Th("Latency",th),html.Th("Event",th)])),
            html.Tbody(rows or [html.Tr([html.Td("No regression events detected âœ“",colSpan=4,
                style={"padding":"20px","textAlign":"center","color":muted,"fontSize":"12px"})])]),
        ],style={"width":"100%","borderCollapse":"collapse"}),
    ])

    def srow(label,vp,vn):
        return html.Div([
            html.Span(label,style={"fontSize":"11px","color":muted,"flex":"1"}),
            html.Span(vp,style={"fontSize":"12px","fontWeight":"600","color":PG_COLOR,"minWidth":"85px","textAlign":"right"}),
            html.Span(vn,style={"fontSize":"12px","fontWeight":"600","color":N4J_COLOR,"minWidth":"85px","textAlign":"right"}),
        ],style={"display":"flex","padding":"7px 14px","borderBottom":f"1px solid {brd}"})

    cache_pg  = "0%" if pg_ch>=len(pg) else f"{100*(1-pg_ch/max(len(pg),1)):.0f}%"
    cache_n4j = "100%" if n4j_ch<=1 else f"{100*(1-n4j_ch/max(len(n4j),1)):.0f}%"
    summ=html.Div([
        html.Div([
            html.Span("Run Summary",style={"fontSize":"13px","fontWeight":"600","color":txt}),
            html.Div([
                html.Span("PG",style={"fontSize":"10px","fontWeight":"700","color":PG_COLOR,"background":f"{PG_COLOR}18","padding":"2px 8px","borderRadius":"4px"}),
                html.Span(" vs ",style={"fontSize":"10px","color":muted,"margin":"0 4px"}),
                html.Span("N4J",style={"fontSize":"10px","fontWeight":"700","color":N4J_COLOR,"background":f"{N4J_COLOR}18","padding":"2px 8px","borderRadius":"4px"}),
            ],style={"display":"flex","alignItems":"center"}),
        ],style={"display":"flex","justifyContent":"space-between","alignItems":"center","padding":"14px 14px 10px","borderBottom":f"1px solid {brd}"}),
        srow("Queries",cnt(pg),cnt(n4j)),
        srow("Mean latency",f"{mean_(pg):.1f} ms",f"{mean_(n4j):.1f} ms"),
        srow("Median",med(pg),med(n4j)),
        srow("P95",p95(pg),p95(n4j)),
        srow("P99",f"{q(pg,99):.1f} ms",f"{q(n4j,99):.1f} ms"),
        srow("Std dev",f"{pg['latency_ms'].std():.1f} ms" if len(pg) else "â€”",
             f"{n4j['latency_ms'].std():.1f} ms" if len(n4j) else "â€”"),
        srow("Plan switches",str(pg_ch),str(n4j_ch)),
        srow("Cache hit rate",cache_pg,cache_n4j),
        html.Div([html.Span("Toronto OSM Â· 38,170 nodes Â· 99,638 edges",
                             style={"fontSize":"10px","color":muted})],
                 style={"padding":"10px 14px","borderTop":f"1px solid {brd}"}),
    ])

    return (kpis,winner,fl,fb,fp,fpc,reg,summ,lat_s,box_s,plan_s,pct_s,reg_s,sum_s)


if __name__ == "__main__":
    print("\n" + "="*50)
    print("  Urban Routing Benchmark Dashboard v6")
    print("  Open: http://localhost:8050")
    print("="*50 + "\n")
    app.run(debug=False, host="0.0.0.0", port=8050)
