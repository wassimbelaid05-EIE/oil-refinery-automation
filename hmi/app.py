"""
HMI Dashboard — Oil Refinery Automation
Real-time process monitoring using Streamlit.

Run with:  streamlit run hmi/app.py

Author: Wassim BELAID
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import time
import random
import math
import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
from datetime import datetime

# ── Page config ──────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Oil Refinery HMI",
    page_icon="🏭",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Custom CSS ───────────────────────────────────────────────────────────────
st.markdown("""
<style>
    .main { background-color: #0e1117; }
    .metric-card {
        background: #1e2130;
        border-radius: 8px;
        padding: 16px;
        border-left: 4px solid #cc0000;
        margin: 4px 0;
    }
    .alarm-critical { background: #3d0000; border-left: 4px solid #ff0000; padding: 8px; border-radius: 4px; margin: 4px 0; }
    .alarm-warning  { background: #3d2200; border-left: 4px solid #ff8c00; padding: 8px; border-radius: 4px; margin: 4px 0; }
    .alarm-info     { background: #003d1a; border-left: 4px solid #00cc66; padding: 8px; border-radius: 4px; margin: 4px 0; }
    .step-active    { background: #cc0000; color: white; padding: 6px 14px; border-radius: 4px; font-weight: bold; display: inline-block; }
    .step-inactive  { background: #2a2a2a; color: #888; padding: 6px 14px; border-radius: 4px; display: inline-block; }
    div[data-testid="metric-container"] { background: #1e2130; border-radius: 8px; padding: 12px; }
</style>
""", unsafe_allow_html=True)

# ── Simulation state (session) ───────────────────────────────────────────────
if "history" not in st.session_state:
    st.session_state.history = []
    st.session_state.tick = 0
    st.session_state.sequence_step = "IDLE"
    st.session_state.start_cmd = False
    st.session_state.e_stop = False
    st.session_state.batch_num = 1
    st.session_state.batch_yield = 0.0
    st.session_state.alarms = []

# ── Simulate one process tick ────────────────────────────────────────────────
def simulate_tick(tick: int, step: str, start: bool, e_stop: bool) -> dict:
    """Lightweight process simulation for demo purposes."""
    t = tick * 0.5  # seconds

    if e_stop:
        return {
            "tick": tick, "step": "EMERGENCY_STOP",
            "temp": 20.0, "level": 0.0, "pressure": 1.013,
            "flow_out": 0.0, "heater_pct": 0.0, "power_kw": 0.0,
        }

    # Simple state machine
    cycle = tick % 400
    if not start or cycle < 20:
        step_name, temp, level, pressure, flow = "IDLE", 20.0, max(0, 50 - cycle * 0.5), 1.013, 0.0
        heater_pct = 0.0
    elif cycle < 80:
        step_name = "FILLING"
        level = min(80, (cycle - 20) * 80 / 60)
        temp = 20.0 + random.gauss(0, 0.3)
        pressure = 1.013
        flow = 0.0
        heater_pct = 0.0
    elif cycle < 160:
        step_name = "HEATING"
        level = 80.0 + random.gauss(0, 0.2)
        temp = 20 + 65 * (1 - math.exp(-(cycle - 80) / 40)) + random.gauss(0, 0.5)
        pressure = 1.013 + (temp - 20) / 500
        flow = 0.0
        heater_pct = min(100, (1 - math.exp(-(cycle - 80) / 30)) * 80)
    elif cycle < 300:
        step_name = "DISTILLATION"
        level = max(5, 80 - (cycle - 160) * 0.5)
        temp = 85.0 + random.gauss(0, 0.8)
        pressure = 1.013 + 0.065 + random.gauss(0, 0.005)
        flow = 70.0 + random.gauss(0, 2.0)
        heater_pct = 40.0 + random.gauss(0, 3)
    else:
        step_name = "DRAINING"
        level = max(0, 80 - (cycle - 160) * 0.5 - (cycle - 300) * 1.0)
        temp = max(20, 85 - (cycle - 300) * 0.3)
        pressure = 1.013 + random.gauss(0, 0.003)
        flow = 0.0
        heater_pct = 0.0

    return {
        "tick": tick,
        "step": step_name,
        "temp": round(temp, 2),
        "level": round(max(0, min(100, level)), 2),
        "pressure": round(pressure, 4),
        "flow_out": round(max(0, flow), 2),
        "heater_pct": round(max(0, min(100, heater_pct)), 1),
        "power_kw": round(heater_pct * 5.0, 1),
    }

def check_alarms(data: dict) -> list:
    alarms = []
    if data["temp"] > 120:
        alarms.append({"tag": "TEMP_HIGH_CRIT", "msg": f"Temperature CRITIQUE: {data['temp']:.1f}°C", "level": "critical"})
    elif data["temp"] > 100:
        alarms.append({"tag": "TEMP_HIGH_WARN", "msg": f"Température haute: {data['temp']:.1f}°C", "level": "warning"})
    if data["pressure"] > 6.0:
        alarms.append({"tag": "PRES_HIGH", "msg": f"Pression haute: {data['pressure']:.2f} bar", "level": "warning"})
    if data["level"] > 90:
        alarms.append({"tag": "LEVEL_HIGH", "msg": f"Niveau cuve élevé: {data['level']:.1f}%", "level": "warning"})
    if data["level"] < 5 and data["step"] not in ("IDLE", "DRAINING"):
        alarms.append({"tag": "LEVEL_LOW", "msg": f"Niveau cuve bas: {data['level']:.1f}%", "level": "critical"})
    return alarms

# ── Advance simulation ───────────────────────────────────────────────────────
st.session_state.tick += 1
data = simulate_tick(
    st.session_state.tick,
    st.session_state.sequence_step,
    st.session_state.start_cmd,
    st.session_state.e_stop,
)
st.session_state.sequence_step = data["step"]
st.session_state.alarms = check_alarms(data)

# Track batch yield
if data["step"] == "DISTILLATION":
    st.session_state.batch_yield += data["flow_out"] * 0.5 / 60

# Keep history (last 200 points)
st.session_state.history.append({
    "time": datetime.now().strftime("%H:%M:%S"),
    **data
})
if len(st.session_state.history) > 200:
    st.session_state.history.pop(0)

df = pd.DataFrame(st.session_state.history)

# ── SIDEBAR — Controls ───────────────────────────────────────────────────────
with st.sidebar:
    st.image("https://upload.wikimedia.org/wikipedia/commons/f/f3/Flag_of_Switzerland.svg", width=60)
    st.title("🏭 Refinery Control")
    st.divider()

    st.subheader("⚙️ Commandes")
    col1, col2 = st.columns(2)
    with col1:
        if st.button("▶ DÉMARRER", use_container_width=True, type="primary"):
            st.session_state.start_cmd = True
            st.session_state.e_stop = False
    with col2:
        if st.button("⬛ ARRÊTER", use_container_width=True):
            st.session_state.start_cmd = False

    if st.button("🚨 ARRÊT URGENCE", use_container_width=True, type="secondary"):
        st.session_state.e_stop = True
        st.session_state.start_cmd = False

    st.divider()
    st.subheader("🔧 PID Température")
    sp = st.slider("Consigne (°C)", 60, 120, 85)
    st.caption(f"PV: {data['temp']:.1f}°C  |  Sortie: {data['heater_pct']:.0f}%")

    st.divider()
    st.subheader("📊 Batch en cours")
    st.metric("N° batch", f"#{st.session_state.batch_num}")
    st.metric("Huile produite", f"{st.session_state.batch_yield:.0f} L")

    refresh = st.slider("Rafraîchissement (s)", 0.5, 5.0, 1.0, 0.5)

# ── HEADER ───────────────────────────────────────────────────────────────────
st.markdown("## 🏭 Oil Refinery — Système de Supervision HMI")
st.caption(f"Dernière mise à jour : {datetime.now().strftime('%H:%M:%S')}  |  Scan #{st.session_state.tick}")

# ── STEP INDICATOR ───────────────────────────────────────────────────────────
steps = ["IDLE", "FILLING", "HEATING", "DISTILLATION", "DRAINING"]
cols = st.columns(len(steps))
for i, (col, step) in enumerate(zip(cols, steps)):
    active = step == data["step"]
    with col:
        st.markdown(
            f'<div class="{"step-active" if active else "step-inactive"}">S{i}: {step}</div>',
            unsafe_allow_html=True
        )

st.divider()

# ── KPI METRICS ──────────────────────────────────────────────────────────────
c1, c2, c3, c4, c5 = st.columns(5)

prev = st.session_state.history[-2] if len(st.session_state.history) > 1 else data

c1.metric("🌡️ Température", f"{data['temp']:.1f} °C",
          f"{data['temp'] - prev['temp']:+.1f}", delta_color="inverse")
c2.metric("📊 Niveau cuve", f"{data['level']:.1f} %",
          f"{data['level'] - prev['level']:+.1f}")
c3.metric("⚡ Pression", f"{data['pressure']:.3f} bar",
          f"{data['pressure'] - prev['pressure']:+.4f}", delta_color="inverse")
c4.metric("💧 Débit sortie", f"{data['flow_out']:.1f} L/min",
          f"{data['flow_out'] - prev['flow_out']:+.1f}")
c5.metric("⚡ Puissance chauffe", f"{data['power_kw']:.0f} kW",
          f"{data['power_kw'] - prev['power_kw']:+.0f}", delta_color="inverse")

st.divider()

# ── CHARTS ───────────────────────────────────────────────────────────────────
col_left, col_right = st.columns([2, 1])

with col_left:
    tab1, tab2, tab3 = st.tabs(["🌡️ Température & Consigne", "📊 Niveau & Débit", "⚡ Puissance"])

    with tab1:
        if len(df) > 1:
            fig = go.Figure()
            fig.add_trace(go.Scatter(x=df["time"], y=df["temp"], name="Température (°C)",
                                      line=dict(color="#cc0000", width=2)))
            fig.add_hline(y=sp, line_dash="dash", line_color="orange",
                          annotation_text=f"Consigne {sp}°C")
            fig.add_hline(y=130, line_dash="dot", line_color="red",
                          annotation_text="Limite critique 130°C")
            fig.update_layout(template="plotly_dark", height=280,
                              margin=dict(l=0, r=0, t=20, b=0))
            st.plotly_chart(fig, use_container_width=True)

    with tab2:
        if len(df) > 1:
            fig = go.Figure()
            fig.add_trace(go.Scatter(x=df["time"], y=df["level"], name="Niveau (%)",
                                      line=dict(color="#2196F3", width=2), fill="tozeroy",
                                      fillcolor="rgba(33,150,243,0.1)"))
            fig.add_trace(go.Scatter(x=df["time"], y=df["flow_out"], name="Débit (L/min)",
                                      line=dict(color="#4CAF50", width=2), yaxis="y2"))
            fig.update_layout(template="plotly_dark", height=280,
                              yaxis2=dict(overlaying="y", side="right"),
                              margin=dict(l=0, r=0, t=20, b=0))
            st.plotly_chart(fig, use_container_width=True)

    with tab3:
        if len(df) > 1:
            fig = go.Figure()
            fig.add_trace(go.Scatter(x=df["time"], y=df["power_kw"], name="Puissance (kW)",
                                      line=dict(color="#FF9800", width=2), fill="tozeroy",
                                      fillcolor="rgba(255,152,0,0.1)"))
            fig.update_layout(template="plotly_dark", height=280,
                              margin=dict(l=0, r=0, t=20, b=0))
            st.plotly_chart(fig, use_container_width=True)

with col_right:
    st.subheader("🚨 Panneau d'alarmes")
    alarms = st.session_state.alarms
    if alarms:
        for al in alarms:
            css = f"alarm-{al['level']}"
            icon = "🔴" if al["level"] == "critical" else "🟠"
            st.markdown(f'<div class="{css}">{icon} <b>{al["tag"]}</b><br>{al["msg"]}</div>',
                        unsafe_allow_html=True)
    else:
        st.markdown('<div class="alarm-info">✅ Aucune alarme active</div>',
                    unsafe_allow_html=True)

    st.divider()
    st.subheader("📋 État des équipements")
    equip = {
        "Pompe alimentation P01": data["step"] == "FILLING",
        "Chauffe-eau E01":        data["step"] in ("HEATING", "DISTILLATION"),
        "Colonne distillation":   data["step"] == "DISTILLATION",
        "Vanne entrée V01":       data["step"] == "FILLING",
        "Vanne sortie V02":       data["step"] == "DRAINING",
    }
    for name, running in equip.items():
        icon = "🟢" if running else "⚫"
        st.markdown(f"{icon} {name}")

# ── Auto-refresh ─────────────────────────────────────────────────────────────
time.sleep(refresh)
st.rerun()
