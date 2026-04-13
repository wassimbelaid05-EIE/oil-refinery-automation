"""
Unit Tests — Oil Refinery Automation
Author: Wassim BELAID
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
from plc.pid import PIDController, temperature_pid, pressure_pid
from plc.alarms import AlarmManager, AlarmPriority, AlarmState, refinery_alarms
from plc.sequencer import GrafcetSequencer


# ── PID Tests ────────────────────────────────────────────────────────────────

class TestPIDController:

    def test_proportional_only(self):
        pid = PIDController(kp=2.0, ki=0.0, kd=0.0, setpoint=100.0)
        out = pid.compute(measurement=80.0, dt=0.1)
        assert abs(out - 40.0) < 0.01   # kp * error = 2 * 20 = 40

    def test_output_clamped_to_max(self):
        pid = PIDController(kp=10.0, ki=0.0, kd=0.0, setpoint=100.0, output_max=100.0)
        out = pid.compute(measurement=0.0, dt=0.1)
        assert out == 100.0

    def test_output_clamped_to_min(self):
        pid = PIDController(kp=2.0, ki=0.0, kd=0.0, setpoint=0.0, output_min=0.0)
        out = pid.compute(measurement=100.0, dt=0.1)
        assert out == 0.0

    def test_integral_accumulates(self):
        pid = PIDController(kp=0.0, ki=1.0, kd=0.0, setpoint=100.0, anti_windup=False)
        pid.compute(measurement=90.0, dt=1.0)   # error=10, integral=10
        pid.compute(measurement=90.0, dt=1.0)   # error=10, integral=20
        out = pid.compute(measurement=90.0, dt=1.0)   # integral=30
        assert abs(out - 30.0) < 0.1

    def test_deadband(self):
        pid = PIDController(kp=5.0, ki=0.0, kd=0.0, setpoint=100.0, deadband=2.0)
        out = pid.compute(measurement=99.0, dt=0.1)   # error=1, within deadband
        assert out == 0.0

    def test_manual_mode(self):
        pid = PIDController(kp=5.0, setpoint=100.0)
        pid.set_manual(42.0)
        out = pid.compute(measurement=0.0, dt=0.1)
        assert out == 42.0

    def test_setpoint_change(self):
        pid = PIDController(kp=1.0, setpoint=50.0)
        pid.set_setpoint(100.0)
        assert pid.config.setpoint == 100.0

    def test_reset(self):
        pid = PIDController(kp=1.0, ki=1.0, setpoint=100.0, anti_windup=False)
        pid.compute(measurement=0.0, dt=1.0)
        pid.reset()
        assert pid.state.integral == 0.0
        assert pid.state.output == 0.0

    def test_history_logged(self):
        pid = PIDController(kp=1.0, setpoint=100.0)
        for _ in range(5):
            pid.compute(measurement=90.0, dt=0.1)
        assert len(pid.state.history) == 5

    def test_disabled_returns_zero(self):
        pid = PIDController(kp=5.0, setpoint=100.0)
        pid.disable()
        assert pid.compute(measurement=0.0, dt=0.1) == 0.0

    def test_temperature_preset(self):
        pid = temperature_pid(setpoint=85.0)
        assert pid.config.setpoint == 85.0
        assert pid.name == "TEMP_PID"

    def test_status_dict(self):
        pid = PIDController(kp=1.0, setpoint=100.0, name="TEST")
        pid.compute(measurement=80.0, dt=0.1)
        s = pid.status()
        assert s["name"] == "TEST"
        assert s["setpoint"] == 100.0
        assert s["mode"] == "AUTO"


# ── Alarm Tests ───────────────────────────────────────────────────────────────

class TestAlarmManager:

    def setup_method(self):
        self.mgr = AlarmManager()
        self.mgr.define(
            "TEMP_HIGH", "Temperature high",
            AlarmPriority.CRITICAL,
            high_limit=100.0,
            hysteresis=2.0,
        )
        self.mgr.define(
            "TEMP_LOW", "Temperature low",
            AlarmPriority.WARNING,
            low_limit=10.0,
            hysteresis=1.0,
        )

    def test_alarm_triggers_on_high_limit(self):
        ev = self.mgr.check("TEMP_HIGH", value=105.0)
        assert ev is not None
        assert ev.state == AlarmState.ACTIVE
        assert ev.priority == AlarmPriority.CRITICAL

    def test_no_alarm_below_limit(self):
        ev = self.mgr.check("TEMP_HIGH", value=95.0)
        assert ev is None

    def test_alarm_triggers_on_low_limit(self):
        ev = self.mgr.check("TEMP_LOW", value=5.0)
        assert ev is not None
        assert ev.state == AlarmState.ACTIVE

    def test_alarm_resolves_with_hysteresis(self):
        self.mgr.check("TEMP_HIGH", value=105.0)   # trigger
        ev = self.mgr.check("TEMP_HIGH", value=97.5)   # below 100-2=98 → resolve
        assert ev is not None
        assert ev.state == AlarmState.RESOLVED

    def test_alarm_does_not_resolve_within_hysteresis(self):
        self.mgr.check("TEMP_HIGH", value=105.0)
        ev = self.mgr.check("TEMP_HIGH", value=99.0)   # above 98, still active
        assert ev is None   # no state change
        assert len(self.mgr.active_alarms()) == 1

    def test_acknowledge(self):
        self.mgr.check("TEMP_HIGH", value=105.0)
        result = self.mgr.acknowledge("TEMP_HIGH", operator="OPERATOR1")
        assert result is True
        active = self.mgr.active_alarms()
        assert active[0].state == AlarmState.ACKNOWLEDGED

    def test_active_alarms_sorted_by_priority(self):
        mgr = refinery_alarms()
        mgr.check("TEMP_HIGH_WARN", 110.0)    # WARNING
        mgr.check("TEMP_HIGH_CRIT", 135.0)   # CRITICAL
        active = mgr.active_alarms()
        assert active[0].priority == AlarmPriority.CRITICAL

    def test_undefined_alarm_raises(self):
        with pytest.raises(KeyError):
            self.mgr.check("DOES_NOT_EXIST", value=50.0)

    def test_suppression(self):
        self.mgr.suppress("TEMP_HIGH")
        ev = self.mgr.check("TEMP_HIGH", value=150.0)
        assert ev is None

    def test_summary(self):
        self.mgr.check("TEMP_HIGH", value=105.0)
        s = self.mgr.summary()
        assert s["total_active"] == 1
        assert s["critical"] == 1

    def test_callback_on_trigger(self):
        triggered = []
        self.mgr.define("CB_TEST", "Callback test", AlarmPriority.INFO,
                         high_limit=50.0, on_trigger=lambda e: triggered.append(e.tag))
        self.mgr.check("CB_TEST", value=60.0)
        assert "CB_TEST" in triggered


# ── Sequencer Tests ───────────────────────────────────────────────────────────

class TestGrafcetSequencer:

    def build_simple_seq(self):
        seq = GrafcetSequencer(initial_step=0)
        seq.add_step(0, "IDLE")
        seq.add_step(1, "RUNNING")
        seq.add_step(2, "DONE")
        self._condition_1 = False
        self._condition_2 = False
        seq.add_transition(0, 1, condition=lambda: self._condition_1)
        seq.add_transition(1, 2, condition=lambda: self._condition_2)
        return seq

    def test_initial_step_active_after_start(self):
        seq = self.build_simple_seq()
        seq.start()
        assert seq.current_step_number() == 0
        assert seq.current_step_name() == "IDLE"

    def test_transition_fires_when_condition_true(self):
        seq = self.build_simple_seq()
        seq.start()
        self._condition_1 = True
        result = seq.scan()
        assert result == (0, 1)
        assert seq.current_step_number() == 1

    def test_transition_does_not_fire_when_false(self):
        seq = self.build_simple_seq()
        seq.start()
        self._condition_1 = False
        seq.scan()
        assert seq.current_step_number() == 0

    def test_sequential_transitions(self):
        seq = self.build_simple_seq()
        seq.start()
        self._condition_1 = True
        seq.scan()   # 0→1
        self._condition_1 = False
        self._condition_2 = True
        seq.scan()   # 1→2
        assert seq.current_step_number() == 2

    def test_pause_stops_transitions(self):
        seq = self.build_simple_seq()
        seq.start()
        seq.pause()
        self._condition_1 = True
        seq.scan()
        assert seq.current_step_number() == 0   # no transition while paused

    def test_resume_allows_transitions(self):
        seq = self.build_simple_seq()
        seq.start()
        seq.pause()
        self._condition_1 = True
        seq.scan()
        seq.resume()
        seq.scan()
        assert seq.current_step_number() == 1

    def test_reset_returns_to_initial(self):
        seq = self.build_simple_seq()
        seq.start()
        self._condition_1 = True
        seq.scan()
        seq.reset()
        assert not seq.is_running()

    def test_entry_callback_called(self):
        calls = []
        seq = GrafcetSequencer(initial_step=0)
        seq.add_step(0, "IDLE")
        seq.add_step(1, "RUNNING", on_entry=lambda: calls.append("entry_1"))
        seq.add_transition(0, 1, condition=lambda: True)
        seq.start()
        seq.scan()
        assert "entry_1" in calls

    def test_history_records_transitions(self):
        seq = self.build_simple_seq()
        seq.start()
        self._condition_1 = True
        seq.scan()
        h = seq.history()
        assert len(h) == 1
        assert h[0]["from"] == 0
        assert h[0]["to"] == 1

    def test_status(self):
        seq = self.build_simple_seq()
        seq.start()
        s = seq.status()
        assert s["running"] is True
        assert s["current_step"] == 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
