"""
PID Controller — Oil Refinery Automation
Simulates TIA Portal PID_Compact block behaviour.

Author: Wassim BELAID
"""

import time
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class PIDConfig:
    """PID tuning parameters."""
    kp: float = 1.0          # Proportional gain
    ki: float = 0.0          # Integral gain
    kd: float = 0.0          # Derivative gain
    setpoint: float = 0.0    # Target value
    output_min: float = 0.0  # Output clamp min (e.g. 0% valve)
    output_max: float = 100.0 # Output clamp max (e.g. 100% valve)
    deadband: float = 0.0    # Ignore error within ±deadband
    anti_windup: bool = True  # Anti integral windup


@dataclass
class PIDState:
    """Runtime state of the PID controller."""
    integral: float = 0.0
    prev_error: float = 0.0
    prev_measurement: float = 0.0
    output: float = 0.0
    error: float = 0.0
    saturated: bool = False
    history: list = field(default_factory=list)


class PIDController:
    """
    Discrete PID controller — position form with:
    - Anti-windup (clamping)
    - Derivative on measurement (avoids derivative kick on setpoint change)
    - Output clamping
    - Deadband
    - Mode: AUTO / MANUAL

    Usage:
        pid = PIDController(kp=1.2, ki=0.5, kd=0.1, setpoint=85.0)
        output = pid.compute(measurement=80.0, dt=0.1)
    """

    def __init__(
        self,
        kp: float = 1.0,
        ki: float = 0.0,
        kd: float = 0.0,
        setpoint: float = 0.0,
        output_min: float = 0.0,
        output_max: float = 100.0,
        deadband: float = 0.0,
        anti_windup: bool = True,
        name: str = "PID",
    ):
        self.config = PIDConfig(
            kp=kp, ki=ki, kd=kd,
            setpoint=setpoint,
            output_min=output_min,
            output_max=output_max,
            deadband=deadband,
            anti_windup=anti_windup,
        )
        self.state = PIDState()
        self.name = name
        self.manual_mode = False
        self.manual_output = 0.0
        self._enabled = True

    # ── Public API ──────────────────────────────────────────────────────────

    def compute(self, measurement: float, dt: float) -> float:
        """
        Compute PID output.

        Args:
            measurement: Current process value (PV)
            dt: Time step in seconds

        Returns:
            Control output in [output_min, output_max]
        """
        if not self._enabled:
            return 0.0

        if self.manual_mode:
            self.state.output = self._clamp(self.manual_output)
            return self.state.output

        if dt <= 0:
            return self.state.output

        cfg = self.config
        st = self.state

        # Error
        error = cfg.setpoint - measurement

        # Deadband
        if abs(error) < cfg.deadband:
            error = 0.0

        st.error = error

        # Proportional
        p_term = cfg.kp * error

        # Integral (with anti-windup)
        if cfg.anti_windup and st.saturated:
            # Stop integrating when output is saturated and error pushes further
            if (st.saturated and error * st.output > 0):
                pass  # don't integrate
            else:
                st.integral += error * dt
        else:
            st.integral += error * dt

        i_term = cfg.ki * st.integral

        # Derivative on measurement (not on error → avoids kick)
        d_measurement = (measurement - st.prev_measurement) / dt
        d_term = -cfg.kd * d_measurement

        # Raw output
        raw_output = p_term + i_term + d_term

        # Clamp
        output = self._clamp(raw_output)
        st.saturated = (output != raw_output)

        # Save state
        st.prev_error = error
        st.prev_measurement = measurement
        st.output = output

        # Log history (keep last 1000 points)
        st.history.append({
            "t": time.time(),
            "sp": cfg.setpoint,
            "pv": measurement,
            "error": error,
            "p": p_term,
            "i": i_term,
            "d": d_term,
            "output": output,
        })
        if len(st.history) > 1000:
            st.history.pop(0)

        return output

    def set_setpoint(self, sp: float) -> None:
        self.config.setpoint = sp

    def set_manual(self, output: float) -> None:
        """Switch to manual mode and set fixed output."""
        self.manual_mode = True
        self.manual_output = output

    def set_auto(self) -> None:
        """Switch back to automatic mode (bumpless transfer)."""
        self.manual_mode = False
        # Bumpless: pre-load integral so output starts at current manual value
        if self.config.ki != 0:
            self.state.integral = self.manual_output / self.config.ki

    def reset(self) -> None:
        """Reset PID state."""
        self.state = PIDState()

    def enable(self) -> None:
        self._enabled = True

    def disable(self) -> None:
        self._enabled = False
        self.state.output = 0.0

    def status(self) -> dict:
        return {
            "name": self.name,
            "setpoint": self.config.setpoint,
            "output": self.state.output,
            "error": self.state.error,
            "integral": self.state.integral,
            "mode": "MANUAL" if self.manual_mode else "AUTO",
            "saturated": self.state.saturated,
        }

    # ── Internal ────────────────────────────────────────────────────────────

    def _clamp(self, value: float) -> float:
        return max(self.config.output_min, min(self.config.output_max, value))

    def __repr__(self) -> str:
        return (
            f"PIDController(name={self.name!r}, "
            f"kp={self.config.kp}, ki={self.config.ki}, kd={self.config.kd}, "
            f"sp={self.config.setpoint})"
        )


# ── Preset factory functions ─────────────────────────────────────────────────

def temperature_pid(setpoint: float = 85.0) -> PIDController:
    """Pre-tuned PID for temperature control (°C)."""
    return PIDController(
        name="TEMP_PID",
        kp=2.0, ki=0.3, kd=0.5,
        setpoint=setpoint,
        output_min=0.0, output_max=100.0,
        deadband=0.5,
    )


def pressure_pid(setpoint: float = 4.0) -> PIDController:
    """Pre-tuned PID for pressure control (bar)."""
    return PIDController(
        name="PRES_PID",
        kp=3.0, ki=0.8, kd=0.2,
        setpoint=setpoint,
        output_min=0.0, output_max=100.0,
        deadband=0.05,
    )


def flow_pid(setpoint: float = 50.0) -> PIDController:
    """Pre-tuned PID for flow control (L/min)."""
    return PIDController(
        name="FLOW_PID",
        kp=1.5, ki=1.0, kd=0.05,
        setpoint=setpoint,
        output_min=0.0, output_max=100.0,
        deadband=0.2,
    )
