# ☄️ 3I/ATLAS — Interactive Orbit Visualizer (Python + Dash)

A fully interactive and animated **3D + 2D orbit visualizer** for comets and asteroids, built in **Python** using **Plotly Dash**.  
It fetches live ephemeris data directly from **NASA JPL Horizons**, allowing users to visualize trajectories, orbital paths, and closest approaches to Earth in real time.

---

## 🚀 Features

- **3D + 2D Animated Orbits** with play/pause slider and date scrubber  
- **Comet** dynamically updated per frame  
- **Earth & Sun markers** for reference  
- **Excel export** of ephemeris data  
- **Responsive Dash web app** — runs locally or on any hosting service  
- **Hosting-ready entrypoint** (binds to `0.0.0.0` and respects `PORT` env var)

---

## 🧠 About

This project visualizes the path of **Interstellar Comet 3I/ATLAS (C/2025 N1)** — one of the rare known interstellar visitors to our solar system.  
You can modify the script to visualize any other comet or asteroid by changing the **NASA Horizons ID**.

---

## ⚙️ Installation & Setup

### 1️⃣ Clone the repository

```bash
git clone https://github.com/yourusername/3i-atlas-orbit-visualizer.git
cd 3i-atlas-orbit-visualizer
