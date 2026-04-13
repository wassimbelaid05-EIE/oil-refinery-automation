"""
Oil Refinery Process Simulation
Models physical behaviour of tanks, heater, distillation column.

Author: Wassim BELAID
"""

import math
import random
import time
from dataclasses import dataclass, field
from typing import List


# ── Actuator models ──────────────────────────────────────────────────────────

class Valve:
    def __init__(self, name: str, initial_position: float = 0.0):
        self.name = name
        self._position = initial_position   # 0–100%
        self.is_open = initial_position > 0

    def open(self, position: float = 100.0):
        self._position = max(0.0, min(100.0, position))
        self.is_open = self._position > 0

    def close(self):
        self._position = 0.0
        self.is_open = False

    @property
    def position(self) -> float:
        return self._position

    def __repr__(self):
        return f"Valve({self.name}, {self._position:.0f}%)"


class Pump:
    def __init__(self, name: str, max_flow: float = 100.0):
        self.name = name
        self.max_flow = max_flow
        self.running = False
        self.speed = 0.0    # 0–100%

    def start(self, speed: float = 100.0):
        self.running = True
        self.speed = max(0.0, min(100.0, speed))

    def stop(self):
        self.running = False
        self.speed = 0.0

    @property
    def flow(self) -> float:
        return (self.speed / 100.0) * self.max_flow if self.running else 0.0


class Heater:
    def __init__(self, name: str, power_kw: float = 500.0):
        self.name = name
        self.power_kw = power_kw
        self.enabled = False
        self.setpoint = 85.0
        self.output_pct = 0.0   # from PID

    def enable(self):
        self.enabled = True

    def disable(self):
        self.enabled = False
        self.output_pct = 0.0

    @property
    def power_actual(self) -> float:
        return (self.output_pct / 100.0) * self.power_kw if self.enabled else 0.0


# ── Sensor with noise ────────────────────────────────────────────────────────

class Sensor:
    def __init__(self, name: str, noise_std: float = 0.1, fail_rate: float = 0.0):
        self.name = name
        self.noise_std = noise_std
        self.fail_rate = fail_rate   # probability of random spike
        self._value = 0.0

    def read(self, true_value: float) -> float:
        if random.random() < self.fail_rate:
            return true_value * random.uniform(1.5, 2.0)   # simulated fault
        noise = random.gauss(0, self.noise_std)
        return true_value + noise

    def set(self, value: float):
        self._value = value


# ── Main process model ───────────────────────────────────────────────────────

@dataclass
class ProcessState:
    # Tank
    tank_level: float = 0.0          # % (0–100)
    tank_volume_liters: float = 0.0

    # Temperature
    temperature: float = 20.0        # °C
    temperature_setpoint: float = 85.0

    # Pressure
    pressure: float = 1.013          # bar (atmospheric)

    # Flow
    inlet_flow: float = 0.0          # L/min
    output_flow: float = 0.0         # L/min

    # Electrical
    power_consumption: float = 0.0   # kW

    # Batch
    batch_number: int = 0
    batch_yield: float = 0.0         # L of refined oil produced

    # Flags
    start_command: bool = False
    emergency_stop: bool = False

    # History for trending
    history: List[dict] = field(default_factory=list)


class OilRefineryProcess:
    """
    Physics-based simulation of an oil refinery process.
    Suitable for testing PLC logic and HMI display.

    Tank capacity: 10,000 L
    Heater: 500 kW
    Operating temp: 85°C distillation
    """

    TANK_CAPACITY_L = 10_000
    AMBIENT_TEMP    = 20.0
    DT              = 0.1    # simulation step (seconds)

    def __init__(self):
        self.state = ProcessState()

        # Actuators
        self.inlet_valve     = Valve("INLET_V01")
        self.outlet_valve    = Valve("OUTLET_V01")
        self.heater          = Heater("HEATER_E01", power_kw=500)
        self.feed_pump       = Pump("PUMP_P01", max_flow=200)   # L/min
        self.product_pump    = Pump("PUMP_P02", max_flow=150)

        # Sensors
        self.temp_sensor     = Sensor("TT-101", noise_std=0.3)
        self.level_sensor    = Sensor("LT-101", noise_std=0.2)
        self.pressure_sensor = Sensor("PT-101", noise_std=0.02)
        self.flow_sensor     = Sensor("FT-101", noise_std=0.5)

        self._last_tick = time.time()

    # ── Step methods (called by GRAFCET) ─────────────────────────────────────

    def set_all_off(self):
        self.inlet_valve.close()
        self.outlet_valve.close()
        self.heater.disable()
        self.feed_pump.stop()
        self.product_pump.stop()

    def update_level(self):
        """Called during FILLING step."""
        self.feed_pump.start(speed=80)
        inflow = self.feed_pump.flow * self.DT / 60   # L per step
        self.state.tank_volume_liters = min(
            self.TANK_CAPACITY_L,
            self.state.tank_volume_liters + inflow
        )
        self._update_derived()

    def regulate_temperature(self):
        """Called during HEATING step — thermal model."""
        if not self.heater.enabled:
            return
        # Simple first-order thermal model: τ = 120s
        tau = 120.0
        q_in  = self.heater.power_actual * 1000   # W
        q_out = 0.05 * (self.state.temperature - self.AMBIENT_TEMP)   # heat loss
        delta_t = (q_in - q_out) / (self.TANK_CAPACITY_L * 2.0)       # J → °C (simplified)
        self.state.temperature += delta_t * self.DT
        self._update_derived()

    def run_distillation(self):
        """Called during DISTILLATION step."""
        if self.state.temperature >= 85.0:
            # Distillation produces output flow
            efficiency = min(1.0, (self.state.temperature - 85) / 20 + 0.7)
            out_lmin = efficiency * 80.0   # L/min
            produced = out_lmin * self.DT / 60
            self.state.tank_volume_liters = max(0, self.state.tank_volume_liters - produced)
            self.state.batch_yield += produced
            self.state.output_flow = out_lmin
        self._update_derived()

    def drain(self):
        """Called during DRAINING step."""
        self.outlet_valve.open(100)
        drained = 50 * self.DT / 60   # 50 L/min drain rate
        self.state.tank_volume_liters = max(0, self.state.tank_volume_liters - drained)
        self._update_derived()

    # ── Sensor readings (with noise) ─────────────────────────────────────────

    def read_temperature(self) -> float:
        return self.temp_sensor.read(self.state.temperature)

    def read_level(self) -> float:
        return self.level_sensor.read(self.state.tank_level)

    def read_pressure(self) -> float:
        return self.pressure_sensor.read(self.state.pressure)

    def read_flow_out(self) -> float:
        return self.flow_sensor.read(self.state.output_flow)

    def snapshot(self) -> dict:
        """Return current process values as dict (for HMI / logging)."""
        return {
            "t": time.time(),
            "tank_level_pct": round(self.read_level(), 2),
            "temperature_c": round(self.read_temperature(), 2),
            "pressure_bar": round(self.read_pressure(), 3),
            "output_flow_lmin": round(self.read_flow_out(), 2),
            "heater_output_pct": round(self.heater.output_pct, 1),
            "heater_power_kw": round(self.heater.power_actual, 1),
            "batch_yield_l": round(self.state.batch_yield, 1),
            "batch_number": self.state.batch_number,
        }

    # ── Internal ─────────────────────────────────────────────────────────────

    def _update_derived(self):
        self.state.tank_level = (
            self.state.tank_volume_liters / self.TANK_CAPACITY_L * 100
        )
        # Pressure rises slightly with temperature (ideal gas approximation)
        self.state.pressure = 1.013 * (1 + (self.state.temperature - 20) / 500)

        # Log snapshot
        snap = self.snapshot()
        self.state.history.append(snap)
        if len(self.state.history) > 5000:
            self.state.history.pop(0)

    @property
    def tank_level(self) -> float:
        return self.state.tank_level

    @property
    def temperature(self) -> float:
        return self.state.temperature

    @property
    def output_flow(self) -> float:
        return self.state.output_flow

    @property
    def start_command(self) -> bool:
        return self.state.start_command

    @property
    def emergency_stop(self) -> bool:
        return self.state.emergency_stop
