"""
3I/ATLAS Web App — Interactive
Author: Rishi

Run locally:
  pip install dash plotly astroquery astropy numpy pandas openpyxl
  python app.py
Then open http://127.0.0.1:8050
"""

import os
from datetime import datetime
from functools import lru_cache

import numpy as np
import pandas as pd

# Plotly / Dash
import dash
from dash import Dash, dcc, html, Input, Output, State
import plotly.graph_objects as go

# Astroquery (Horizons)
from astroquery.jplhorizons import Horizons
from astroquery.exceptions import RemoteServiceError

# Flask for download route
from flask import send_from_directory

# -------------------------
# Constants & setup
# -------------------------
AU_TO_KM = 149_597_870.7
DAY_TO_S = 86400.0

DEFAULT_ID = "C/2025 N1"  # 3I/ATLAS
DEFAULT_START = "2025-07-01"
DEFAULT_STOP = "2026-01-01"
DEFAULT_STEP = "1d"

EXPORT_DIR = os.environ.get("EXPORT_DIR", "exports")
os.makedirs(EXPORT_DIR, exist_ok=True)

REMOTE_TIMEOUT_S = int(os.environ.get("REMOTE_TIMEOUT_S", "60"))  # network timeout (s)

# -------------------------
# Helper: format dates for animation sliders (date only, no time)
# -------------------------
def format_dates_for_slider(dates_str_array, out_fmt="%Y-%m-%d"):
    """
    Convert Horizons 'datetime_str' entries like 'A.D. 2025-Jul-01 00:00:00.0000'
    to clean date-only labels, e.g. '2025-07-01'.
    Robust to presence/absence of 'A.D.' and fractional seconds.
    """
    cleaned = []
    for d in dates_str_array:
        s = str(d).replace("A.D. ", "").strip()  # '2025-Jul-01 00:00:00.0000'
        # Try the common Horizons format with fractional seconds
        for fmt in ("%Y-%b-%d %H:%M:%S.%f", "%Y-%b-%d %H:%M:%S", "%Y-%b-%d"):
            try:
                dt = datetime.strptime(s, fmt)
                cleaned.append(dt.strftime(out_fmt))
                break
            except ValueError:
                continue
        else:
            # Fallback: just take the first token before space (date-like part)
            cleaned.append(s.split()[0])
    return np.array(cleaned)

# -------------------------
# Helper: fetch ephemeris & derived metrics (cached)
# -------------------------
@lru_cache(maxsize=16)
def fetch_ephemeris(comet_id: str, start: str, stop: str, step: str):
    """
    Horizons queries with a small LRU cache keyed by (comet_id, start, stop, step).
    Returns numpy arrays + Python datetimes. Only computes what's needed for kept plots.
    """
    epochs = {'start': start, 'stop': stop, 'step': step}

    try:
        # Comet heliocentric (for orbit shape/animations)
        eph_helio = Horizons(id=comet_id, location='@sun', epochs=epochs)
        eph_helio.TIMEOUT = REMOTE_TIMEOUT_S
        helio = eph_helio.vectors()
        x, y, z = helio['x'].data, helio['y'].data, helio['z'].data
        dates_str = helio['datetime_str'].data

        # Earth heliocentric (true Earth orbit & marker)
        earth_helio = Horizons(id='399', location='@sun', epochs=epochs)
        earth_helio.TIMEOUT = REMOTE_TIMEOUT_S
        evec = earth_helio.vectors()
        ex, ey, ez = evec['x'].data, evec['y'].data, evec['z'].data

        # Geocentric distance (Earth-centered)
        eph_geo = Horizons(id=comet_id, location='399', epochs=epochs)
        eph_geo.TIMEOUT = REMOTE_TIMEOUT_S
        gvec = eph_geo.vectors()
        gdist_au = gvec['range'].data
        gdist_km = gdist_au * AU_TO_KM

    except RemoteServiceError as e:
        raise RuntimeError(f"Horizons service error: {e}") from e
    except Exception as e:
        raise RuntimeError(f"Failed to fetch ephemeris. Check ID/range/step. Details: {e}") from e

    # Dates & closest approach
    date_objs = [datetime.strptime(str(d).replace("A.D. ", ""), "%Y-%b-%d %H:%M:%S.%f") for d in dates_str]
    min_idx = int(np.argmin(gdist_au))

    data = {
        'dates_str': dates_str,
        'dates': date_objs,
        'x': x, 'y': y, 'z': z,           # comet heliocentric
        'ex': ex, 'ey': ey, 'ez': ez,     # Earth heliocentric
        'gdist_au': gdist_au,             # geocentric distance
        'gdist_km': gdist_km,
        'closest_idx': min_idx,
        'closest_au': float(gdist_au[min_idx]),
        'closest_km': float(gdist_km[min_idx]),
        'closest_date': str(dates_str[min_idx]),
        'epochs': epochs,
        'comet_id': comet_id
    }
    return data

# -------------------------
# Plot builders (Plotly, dark) — kept
# -------------------------
def fig_2d_helio(data):
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=data['ex'], y=data['ey'], mode="lines",
        name="Earth Orbit (Horizons)", line=dict(color="#44D3FF", width=1, dash="dash")
    ))
    fig.add_trace(go.Scatter(
        x=data['x'], y=data['y'], mode="lines",
        name=f"{data['comet_id']} Trajectory", line=dict(color="white", width=2)
    ))
    fig.add_trace(go.Scatter(
        x=[0], y=[0], mode="markers", name="Sun",
        marker=dict(color="yellow", size=10)
    ))
    i = data['closest_idx']
    fig.add_trace(go.Scatter(
        x=[data['x'][i]], y=[data['y'][i]], mode="markers",
        name="Closest Approach", marker=dict(color="white", size=8, symbol="x")
    ))
    fig.update_layout(
        template="plotly_dark",
        title=f"{data['comet_id']} — 2D Heliocentric Trajectory",
        xaxis_title="X (AU)", yaxis_title="Y (AU)",
        xaxis=dict(scaleanchor="y", scaleratio=1),
        plot_bgcolor="black", paper_bgcolor="black",
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
    )
    return fig

def fig_3d_helio(data):
    fig = go.Figure()
    fig.add_trace(go.Scatter3d(
        x=data['ex'], y=data['ey'], z=data['ez'], mode="lines",
        name="Earth Orbit (Horizons)", line=dict(color="#44D3FF", width=2, dash="dash"), opacity=0.7
    ))
    fig.add_trace(go.Scatter3d(
        x=data['x'], y=data['y'], z=data['z'], mode="lines",
        name=f"{data['comet_id']} 3D Trajectory", line=dict(color="white", width=4), opacity=0.95
    ))
    fig.add_trace(go.Scatter3d(
        x=[0], y=[0], z=[0], mode="markers",
        name="Sun", marker=dict(color="yellow", size=5)
    ))
    i = data['closest_idx']
    fig.add_trace(go.Scatter3d(
        x=[data['x'][i]], y=[data['y'][i]], z=[data['z'][i]],
        mode="markers", name="Closest Approach",
        marker=dict(color="white", size=4, symbol="x")
    ))
    fig.update_layout(
        template="plotly_dark",
        title=f"{data['comet_id']} — 3D Heliocentric Trajectory",
        scene=dict(xaxis_title="X (AU)", yaxis_title="Y (AU)", zaxis_title="Z (AU)", bgcolor="black"),
        plot_bgcolor="black", paper_bgcolor="black",
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        margin=dict(l=0, r=0, b=0, t=40),
    )
    return fig

def fig_distance(data):
    i = data['closest_idx']
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=data['dates'], y=data['gdist_au'], mode="lines",
        name="Distance to Earth (AU)", line=dict(color="white", width=2)
    ))
    fig.add_trace(go.Scatter(
        x=[data['dates'][i]], y=[data['gdist_au'][i]], mode="markers+text",
        name="Closest Approach", marker=dict(color="white", size=9, symbol="x"),
        text=[f"{data['closest_au']:.3f} AU"], textposition="bottom center", textfont=dict(size=10)
    ))
    fig.update_layout(
        template="plotly_dark",
        title=f"{data['comet_id']} — Distance from Earth (Geocentric)",
        xaxis_title="Date (UTC)", yaxis_title="Distance (AU)",
        plot_bgcolor="black", paper_bgcolor="black"
    )
    return fig

# -------------------------
# Animated 3D/2D builders (Plotly frames) — dates-only slider labels
# -------------------------
def fig_3d_animated(data, frame_step: int = 2, trail_len: int = 25):
    x, y, z = np.array(data['x']), np.array(data['y']), np.array(data['z'])
    ex, ey, ez = np.array(data['ex']), np.array(data['ey']), np.array(data['ez'])
    dates_labels = format_dates_for_slider(data['dates_str'], out_fmt="%Y-%m-%d")

    idx = np.arange(len(x))[::max(1, frame_step)]
    if idx[-1] != len(x)-1:
        idx = np.append(idx, len(x)-1)

    static_traces = [
        go.Scatter3d(x=ex, y=ey, z=ez, mode="lines",
                     name="Earth Orbit (Horizons)",
                     line=dict(color="#44D3FF", width=2, dash="dash"), opacity=0.7),
        go.Scatter3d(x=[0], y=[0], z=[0], mode="markers",
                     name="Sun", marker=dict(color="yellow", size=5))
    ]

    base_dynamic = [
        go.Scatter3d(x=[x[0]], y=[y[0]], z=[z[0]], mode="lines",
                     name=f"{data['comet_id']} Trail", line=dict(color="white", width=4), opacity=0.95),
        go.Scatter3d(x=[x[0]], y=[y[0]], z=[z[0]], mode="markers",
                     name="Comet", marker=dict(color="white", size=5, symbol="circle")),
        go.Scatter3d(x=[ex[0]], y=[ey[0]], z=[ez[0]], mode="markers",
                     name="Earth", marker=dict(color="#44D3FF", size=5, symbol="circle"))
    ]

    frames = []
    for k, i in enumerate(idx):
        start = max(0, i - trail_len)
        frame_data = [
            go.Scatter3d(x=x[start:i+1], y=y[start:i+1], z=z[start:i+1],
                         mode="lines", line=dict(color="white", width=4), opacity=0.95,
                         name=f"{data['comet_id']} Trail"),
            go.Scatter3d(x=[x[i]], y=[y[i]], z=[z[i]], mode="markers",
                         marker=dict(color="white", size=5), name="Comet"),
            go.Scatter3d(x=[ex[i]], y=[ey[i]], z=[ez[i]], mode="markers",
                         marker=dict(color="#44D3FF", size=5), name="Earth")
        ]
        frames.append(go.Frame(data=frame_data, name=str(k), traces=[2, 3, 4]))

    play_button = dict(
        type="buttons",
        buttons=[
            dict(label="▶ Play", method="animate",
                 args=[[f.name for f in frames],
                       {"frame": {"duration": 80, "redraw": True},
                        "fromcurrent": True, "transition": {"duration": 0}}]),
            dict(label="⏸ Pause", method="animate",
                 args=[[None], {"frame": {"duration": 0, "redraw": False}, "mode": "immediate"}])
        ],
        direction="left", pad={"r": 10, "t": 70}, x=0.05, y=0.0, xanchor="left", yanchor="bottom"
    )

    slider = [dict(
        active=0, pad={"t": 55},
        steps=[dict(label=dates_labels[i], method="animate",
                    args=[[str(k)], {"frame": {"duration": 0, "redraw": True}, "mode": "immediate"}])
               for k, i in enumerate(idx)]
    )]

    fig = go.Figure(
        data=static_traces + base_dynamic,
        frames=frames,
        layout=go.Layout(
            template="plotly_dark",
            title=f"{data['comet_id']} — 3D Animated Trajectory (Play ▶)",
            scene=dict(xaxis_title="X (AU)", yaxis_title="Y (AU)", zaxis_title="Z (AU)", bgcolor="black"),
            updatemenus=[play_button], sliders=slider,
            paper_bgcolor="black", plot_bgcolor="black",
            margin=dict(l=0, r=0, b=0, t=60),
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
        )
    )
    return fig

def fig_2d_animated(data, frame_step: int = 2, trail_len: int = 25):
    x, y = np.array(data['x']), np.array(data['y'])
    ex, ey = np.array(data['ex']), np.array(data['ey'])
    dates_labels = format_dates_for_slider(data['dates_str'], out_fmt="%Y-%m-%d")

    idx = np.arange(len(x))[::max(1, frame_step)]
    if idx[-1] != len(x)-1:
        idx = np.append(idx, len(x)-1)

    static_traces = [
        go.Scatter(x=ex, y=ey, mode="lines",
                   name="Earth Orbit (Horizons)", line=dict(color="#44D3FF", width=2, dash="dash")),
        go.Scatter(x=[0], y=[0], mode="markers", name="Sun",
                   marker=dict(color="yellow", size=10))
    ]

    base_dynamic = [
        go.Scatter(x=[x[0]], y=[y[0]], mode="lines",
                   name=f"{data['comet_id']} Trail", line=dict(color="white", width=3)),
        go.Scatter(x=[x[0]], y=[y[0]], mode="markers",
                   name="Comet", marker=dict(color="white", size=8, symbol="circle")),
        go.Scatter(x=[ex[0]], y=[ey[0]], mode="markers",
                   name="Earth", marker=dict(color="#44D3FF", size=8, symbol="circle"))
    ]

    frames = []
    for k, i in enumerate(idx):
        start = max(0, i - trail_len)
        frame_data = [
            go.Scatter(x=x[start:i+1], y=y[start:i+1], mode="lines",
                       line=dict(color="white", width=3), name=f"{data['comet_id']} Trail"),
            go.Scatter(x=[x[i]], y=[y[i]], mode="markers",
                       marker=dict(color="white", size=9), name="Comet"),
            go.Scatter(x=[ex[i]], y=[ey[i]], mode="markers",
                       marker=dict(color="#44D3FF", size=9), name="Earth")
        ]
        frames.append(go.Frame(data=frame_data, name=str(k), traces=[2, 3, 4]))

    play_button = dict(
        type="buttons",
        buttons=[
            dict(label="▶ Play", method="animate",
                 args=[[f.name for f in frames],
                       {"frame": {"duration": 80, "redraw": True},
                        "fromcurrent": True, "transition": {"duration": 0}}]),
            dict(label="⏸ Pause", method="animate",
                 args=[[None], {"frame": {"duration": 0, "redraw": False}, "mode": "immediate"}])
        ],
        direction="left", pad={"r": 10, "t": 65}, x=0.05, y=0.0, xanchor="left", yanchor="bottom"
    )

    slider = [dict(
        active=0, pad={"t": 50},
        steps=[dict(label=dates_labels[i], method="animate",
                    args=[[str(k)], {"frame": {"duration": 0, "redraw": True}, "mode": "immediate"}])
               for k, i in enumerate(idx)]
    )]

    fig = go.Figure(
        data=static_traces + base_dynamic,
        frames=frames,
        layout=go.Layout(
            template="plotly_dark",
            title=f"{data['comet_id']} — 2D Animated Trajectory (Play ▶)",
            xaxis_title="X (AU)", yaxis_title="Y (AU)",
            xaxis=dict(scaleanchor="y", scaleratio=1, showgrid=True, gridcolor="rgba(255,255,255,0.15)"),
            yaxis=dict(showgrid=True, gridcolor="rgba(255,255,255,0.15)"),
            updatemenus=[play_button], sliders=slider,
            paper_bgcolor="black", plot_bgcolor="black",
            margin=dict(l=0, r=0, b=0, t=60),
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
        )
    )
    return fig

# -------------------------
# Excel export
# -------------------------
def export_excel(data):
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    fname = f"3i_atlas_data_{ts}.xlsx"
    fpath = os.path.join(EXPORT_DIR, fname)

    df = pd.DataFrame({
        'Date_UTC_str': data['dates_str'],
        'Heliocentric_X_AU': data['x'],
        'Heliocentric_Y_AU': data['y'],
        'Heliocentric_Z_AU': data['z'],
        'EarthHelio_X_AU': data['ex'],
        'EarthHelio_Y_AU': data['ey'],
        'EarthHelio_Z_AU': data['ez'],
        'Distance_Earth_AU': data['gdist_au'],
        'Distance_Earth_km': data['gdist_km'],
    })

    with pd.ExcelWriter(fpath, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name='Ephemeris')
        meta = pd.DataFrame({
            'Field': ['Comet ID', 'Start (UTC)', 'Stop (UTC)', 'Step',
                      'Closest approach AU', 'Closest approach km', 'Closest approach date (UTC)'],
            'Value': [data['comet_id'], data['epochs']['start'], data['epochs']['stop'], data['epochs']['step'],
                      f"{data['closest_au']:.6f}", f"{data['closest_km']:,.0f}", data['closest_date']]
        })
        meta.to_excel(writer, index=False, sheet_name='Metadata')

    return fname, fpath

# -------------------------
# Dash App
# -------------------------
app: Dash = dash.Dash(__name__)
server = app.server  # for deployment

app.layout = html.Div(
    style={"backgroundColor": "black", "color": "white", "fontFamily": "Inter, system-ui, Segoe UI"},
    children=[
        html.H2("3I/ATLAS — Interactive Web App (Dash)", style={"margin":"16px 16px 0 16px"}),

        # Controls
        html.Div([
            html.Div([
                html.Label("Comet/Target ID (Horizons)"),
                dcc.Input(id="in-id", type="text", value=DEFAULT_ID,
                          style={"width":"100%", "background":"#111", "color":"white", "border":"1px solid #333"}),
            ], style={"flex":"2", "marginRight":"12px"}),
            html.Div([
                html.Label("Start (UTC, YYYY-MM-DD)"),
                dcc.Input(id="in-start", type="text", value=DEFAULT_START,
                          style={"width":"100%", "background":"#111", "color":"white", "border":"1px solid #333"}),
            ], style={"flex":"1", "marginRight":"12px"}),
            html.Div([
                html.Label("Stop (UTC, YYYY-MM-DD)"),
                dcc.Input(id="in-stop", type="text", value=DEFAULT_STOP,
                          style={"width":"100%", "background":"#111", "color":"white", "border":"1px solid #333"}),
            ], style={"flex":"1", "marginRight":"12px"}),
            html.Div([
                html.Label("Step (e.g., 1d, 12h)"),
                dcc.Input(id="in-step", type="text", value=DEFAULT_STEP,
                          style={"width":"100%", "background":"#111", "color":"white", "border":"1px solid #333"}),
            ], style={"flex":"1"}),
        ], style={"display":"flex", "gap":"12px", "padding":"16px"}),

        html.Div([
            html.Button("Generate / Update Plots", id="btn-update",
                        style={"background":"#1976d2", "border":"none", "padding":"10px 16px", "color":"white",
                               "borderRadius":"8px", "cursor":"pointer"}),
            html.Span(id="status", style={"marginLeft":"12px", "opacity":0.9}),
        ], style={"padding":"0 16px 8px 16px"}),

        # Download link appears after successful run
        html.Div(id="download-area", style={"padding":"0 16px 8px 16px"}),

        # Static interactive figures (slimmed)
        html.Div([
            dcc.Graph(id="fig-2d", style={"height":"500px"}),
            dcc.Graph(id="fig-3d", style={"height":"520px"}),
            dcc.Graph(id="fig-dist", style={"height":"380px"}),
        ], style={"padding":"0 16px 0 16px"}),

        html.Hr(style={"borderColor":"#333"}),

        # Animated section
        html.Div([
            html.H3("2D & 3D Trajectory — Animations", style={"margin":"8px 16px"}),
            html.Div("Use ▶ Play under each plot to animate the comet and Earth.",
                     style={"opacity":0.85, "margin":"0 16px 8px 16px"}),
            dcc.Graph(id="fig-2d-anim", style={"height":"520px", "margin":"0 16px 16px 16px"}),
            dcc.Graph(id="fig-3d-anim", style={"height":"640px", "margin":"0 16px 16px 16px"}),
        ])
    ]
)

@app.callback(
    [
        Output("fig-2d", "figure"),
        Output("fig-3d", "figure"),
        Output("fig-dist", "figure"),
        Output("fig-2d-anim", "figure"),
        Output("fig-3d-anim", "figure"),
        Output("status", "children"),
        Output("download-area", "children")
    ],
    Input("btn-update", "n_clicks"),
    [
        State("in-id", "value"),
        State("in-start", "value"),
        State("in-stop", "value"),
        State("in-step", "value"),
    ],
    prevent_initial_call=True
)
def on_update(n, comet_id, start, stop, step):
    try:
        data = fetch_ephemeris(comet_id.strip(), start.strip(), stop.strip(), step.strip())

        f2d = fig_2d_helio(data)
        f3d = fig_3d_helio(data)
        fdist = fig_distance(data)
        f2d_anim = fig_2d_animated(data, frame_step=2, trail_len=25)
        f3d_anim = fig_3d_animated(data, frame_step=2, trail_len=25)

        fname, _ = export_excel(data)
        link = html.A("Download Excel (Ephemeris + Metadata)",
                      href=f"/download/{fname}",
                      style={"color":"#64b5f6", "textDecoration":"none"})
        dl_area = html.Div([
            html.Div(f"Closest approach: {data['closest_au']:.6f} AU ({data['closest_km']:,.0f} km) on {data['closest_date']}",
                     style={"marginBottom":"4px", "opacity":0.9}),
            link
        ])

        status_done = f"Done. Frames — 2D: {len(f2d_anim.frames)} | 3D: {len(f3d_anim.frames)} | Points: {len(data['dates'])}."
        return f2d, f3d, fdist, f2d_anim, f3d_anim, status_done, dl_area

    except Exception as e:
        err = f"Error: {e}"
        empty = go.Figure(layout=go.Layout(template="plotly_dark", paper_bgcolor="black", plot_bgcolor="black"))
        return empty, empty, empty, empty, empty, err, html.Div(err, style={"color":"#ef9a9a"})

# Simple download route (serves files from EXPORT_DIR)
@server.route("/download/<path:filename>")
def download_file(filename):
    return send_from_directory(EXPORT_DIR, filename, as_attachment=True)

# -------------------------
# Entrypoint
# -------------------------
if __name__ == "__main__":
    print("=== 3I/ATLAS Dash Web App (Dates-only slider) ===")
    port = int(os.environ.get("PORT", 8050))
    host = os.environ.get("HOST", "0.0.0.0")
    print(f"Listening on http://{host}:{port}")
    print(f"Default target: {DEFAULT_ID} | Range: {DEFAULT_START} → {DEFAULT_STOP} | Step: {DEFAULT_STEP}")
    app.run(debug=False, host=host, port=port)
