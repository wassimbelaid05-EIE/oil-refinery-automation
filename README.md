# 🏭 Oil Refinery Automation System

[![Python](https://img.shields.io/badge/Python-3.10+-blue?logo=python)](https://python.org)
[![License](https://img.shields.io/badge/License-MIT-green)](LICENSE)
[![Status](https://img.shields.io/badge/Status-Active-brightgreen)]()

> Automated control system for an oil refinery — PLC logic simulation, HMI dashboard, predictive maintenance and real-time process monitoring.

Inspired by a real industrial automation project implemented at **Cevital (Béjaia, Algeria)**, achieving **+12% productivity** and **−10% operational costs**.

---

## 📐 System Architecture

```
┌─────────────────────────────────────────────────────────┐
│                  OIL REFINERY PROCESS                   │
│                                                         │
│  [Raw Oil Tank] → [Heater] → [Distillation] → [Output] │
│       ↑               ↑            ↑              ↑     │
│    Sensors          Sensors     Sensors         Sensors  │
└──────────────────────────────────────────────────────────┘
           ↓               ↓            ↓
┌─────────────────────────────────────────────────────────┐
│                     PLC CONTROLLER                      │
│         (Simulated TIA Portal logic in Python)          │
│  • Sequence control    • Alarm management               │
│  • PID regulation      • Safety interlocks              │
└─────────────────────────────────────────────────────────┘
           ↓
┌─────────────────────────────────────────────────────────┐
│                   HMI DASHBOARD (Streamlit)             │
│  • Real-time process visualization                      │
│  • Alarm panel   • Trend charts   • KPI display         │
└─────────────────────────────────────────────────────────┘
```

---

## 🚀 Features

- **PLC Logic Simulation** — Sequence control, interlocks, PID loops (TIA Portal–style in Python)
- **Real-time HMI Dashboard** — Live process visualization with Streamlit
- **Alarm Management** — Priority-based alarm system with acknowledgement
- **Predictive Maintenance** — Anomaly detection using statistical analysis
- **GRAFCET / SFC** — Sequential Function Chart simulator
- **Data Logging** — Process historian with CSV/SQLite export

---

## 📁 Project Structure

```
oil-refinery-automation/
├── plc/                    # PLC logic simulation
│   ├── controller.py       # Main PLC controller
│   ├── pid.py              # PID regulator
│   ├── sequencer.py        # GRAFCET/SFC sequencer
│   ├── alarms.py           # Alarm management
│   └── interlocks.py       # Safety interlocks
├── hmi/                    # HMI Dashboard
│   ├── app.py              # Streamlit main app
│   ├── pages/
│   │   ├── overview.py     # Process overview page
│   │   ├── alarms.py       # Alarm panel page
│   │   └── trends.py       # Historical trends page
│   └── assets/
│       └── style.css
├── simulation/             # Process simulation
│   ├── process.py          # Refinery process model
│   ├── sensors.py          # Sensor simulation + noise
│   └── actuators.py        # Pump, valve, heater models
├── docs/                   # Documentation
│   ├── GRAFCET.md          # Sequence diagrams
│   ├── PID_TUNING.md       # PID tuning guide
│   └── images/
├── tests/                  # Unit tests
│   ├── test_pid.py
│   ├── test_alarms.py
│   └── test_sequencer.py
├── requirements.txt
├── run.py                  # Entry point
└── README.md
```

---

## ⚡ Quick Start

```bash
# 1. Clone the repository
git clone https://github.com/wassimbelaid05-EIE/oil-refinery-automation.git
cd oil-refinery-automation

# 2. Install dependencies
pip install -r requirements.txt

# 3. Run the simulation + HMI
python run.py

# 4. Open the dashboard
# → http://localhost:8501
```

---

## 🔧 PLC Modules

### PID Controller
```python
from plc.pid import PIDController

pid = PIDController(kp=1.2, ki=0.5, kd=0.1, setpoint=85.0)
output = pid.compute(current_temperature=80.0, dt=0.1)
```

### Alarm System
```python
from plc.alarms import AlarmManager, AlarmPriority

alarms = AlarmManager()
alarms.add_alarm("HIGH_TEMP", priority=AlarmPriority.CRITICAL, threshold=120.0)
alarms.check("HIGH_TEMP", value=125.0)  # triggers alarm
```

### Sequencer (GRAFCET)
```python
from plc.sequencer import GrafcetSequencer

seq = GrafcetSequencer()
seq.add_step(0, "IDLE",    action=lambda: print("Waiting..."))
seq.add_step(1, "HEATING", action=heater.on)
seq.add_step(2, "DISTILL", action=distillation.start)
seq.add_transition(0 -> 1, condition=lambda: start_btn and temp > 40)
```

---

## 📊 KPIs Monitored

| KPI | Target | Unit |
|-----|--------|------|
| Throughput | > 95% | % |
| Temperature stability | ±2°C | °C |
| Unplanned downtime | < 2h/month | hours |
| Alarm rate | < 5/hour | alarms |
| Energy consumption | baseline | kWh/ton |

---

## 🗂️ GRAFCET — Main Sequence

```
[S0] IDLE
  ↓  T0: start_cmd AND tank_level > 20%
[S1] FILLING
  ↓  T1: tank_level >= 80%
[S2] HEATING
  ↓  T2: temperature >= 85°C
[S3] DISTILLATION
  ↓  T3: output_flow < 0.1 L/min (end of batch)
[S4] DRAINING
  ↓  T4: tank_level <= 5%
[S0] IDLE
```

---

## 🛡️ Safety Interlocks

| Condition | Action |
|-----------|--------|
| Temperature > 130°C | Emergency shutdown |
| Pressure > 8 bar | Relief valve open |
| Tank level < 5% | Pump stop |
| Flow = 0 + pump ON | Dry-run alarm |

---

## 📈 Results (Real Project Reference)

This simulation is based on a real automation project at Cevital oil refinery:
- ✅ **+12% productivity** through optimized sequencing
- ✅ **−10% operational costs** via predictive maintenance
- ✅ Significant reduction in unplanned downtime

---

## 🧪 Tests

```bash
pytest tests/ -v
```

---

## 📜 License

MIT License — feel free to use and adapt for educational purposes.

---

## 👤 Author

**Wassim BELAID**  
MSc Electrical Engineering — HES-SO Lausanne, Switzerland  
[LinkedIn](https://linkedin.com/in/wassimbelaid) · [GitHub](https://github.com/wassimbelaid05-EIE)
