# 3i-atlas-orbit-visualizer
# 3I/ATLAS — Interactive Orbit Visualizer (Dash)

A Python + Dash + Plotly web app that visualizes the orbit of **Comet 3I/ATLAS (C/2025 N1)** in **2D and 3D** using **NASA JPL Horizons** ephemeris.  
You can animate the trajectory, see Earth and Sun markers, inspect closest approach, and export a full **Excel dataset** (ephemeris + metadata).

https://github.com/<your-username>/3i-atlas-orbit-visualizer

---

## Features

- Fetches **real ephemeris** from **NASA JPL Horizons**
- **2D + 3D** heliocentric views (Sun/Earth/comet)
- **Animated** trajectories with play/pause + date-only slider labels
- **Closest approach** annotation (AU + km + date)
- **Excel export** (Ephemeris + Metadata)
- Dark theme, responsive layout

---

## Quickstart

```bash
# 1) Create and activate a virtual env (recommended)
python -m venv .venv
# Windows: .venv\Scripts\activate
# macOS/Linux:
source .venv/bin/activate

# 2) Install deps
pip install -r requirements.txt

# 3) Run
python app.py
