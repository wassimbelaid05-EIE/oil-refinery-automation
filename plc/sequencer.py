"""
GRAFCET / SFC Sequencer — Oil Refinery Automation
Implements IEC 61131-3 Sequential Function Chart logic.

Author: Wassim BELAID
"""

from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional, Tuple
import time


@dataclass
class Step:
    """A GRAFCET step."""
    number: int
    name: str
    action: Optional[Callable] = None       # Called every scan while active
    on_entry: Optional[Callable] = None     # Called once on step entry
    on_exit: Optional[Callable] = None      # Called once on step exit
    active: bool = False
    active_since: Optional[float] = None

    @property
    def elapsed(self) -> float:
        if self.active_since is None:
            return 0.0
        return time.time() - self.active_since


@dataclass
class Transition:
    """A GRAFCET transition."""
    from_step: int
    to_step: int
    condition: Callable[[], bool]
    label: str = ""


class GrafcetSequencer:
    """
    IEC 61131-3 Sequential Function Chart (SFC/GRAFCET) engine.

    Features:
    - Steps with entry/action/exit callbacks
    - Transitions with boolean conditions
    - Timer conditions (TON equivalent)
    - Pause / Resume / Reset
    - Sequence history

    Usage:
        seq = GrafcetSequencer()
        seq.add_step(0, "IDLE")
        seq.add_step(1, "HEATING", action=lambda: heater.set(80))
        seq.add_step(2, "DISTILL", action=distill.run)
        seq.add_transition(0, 1, condition=lambda: start_cmd and level > 20)
        seq.add_transition(1, 2, condition=lambda: temperature >= 85)
        seq.add_transition(2, 0, condition=lambda: batch_done)

        # In control loop:
        while running:
            seq.scan()
            time.sleep(0.1)
    """

    def __init__(self, initial_step: int = 0):
        self._steps: Dict[int, Step] = {}
        self._transitions: List[Transition] = []
        self._initial_step = initial_step
        self._running = False
        self._paused = False
        self._history: List[dict] = []
        self._scan_count = 0

    # ── Configuration ────────────────────────────────────────────────────────

    def add_step(
        self,
        number: int,
        name: str,
        action: Optional[Callable] = None,
        on_entry: Optional[Callable] = None,
        on_exit: Optional[Callable] = None,
    ) -> "GrafcetSequencer":
        self._steps[number] = Step(
            number=number,
            name=name,
            action=action,
            on_entry=on_entry,
            on_exit=on_exit,
        )
        return self

    def add_transition(
        self,
        from_step: int,
        to_step: int,
        condition: Callable[[], bool],
        label: str = "",
    ) -> "GrafcetSequencer":
        self._transitions.append(Transition(
            from_step=from_step,
            to_step=to_step,
            condition=condition,
            label=label,
        ))
        return self

    # ── Control ──────────────────────────────────────────────────────────────

    def start(self) -> None:
        """Activate initial step and start sequencer."""
        if self._initial_step not in self._steps:
            raise RuntimeError(f"Initial step {self._initial_step} not defined.")
        self._activate_step(self._initial_step)
        self._running = True
        self._paused = False

    def pause(self) -> None:
        self._paused = True

    def resume(self) -> None:
        self._paused = False

    def reset(self) -> None:
        """Deactivate all steps, return to initial."""
        for step in self._steps.values():
            if step.active and step.on_exit:
                step.on_exit()
            step.active = False
            step.active_since = None
        self._running = False
        self._paused = False

    def stop(self) -> None:
        self.reset()

    # ── Scan ─────────────────────────────────────────────────────────────────

    def scan(self) -> Optional[Tuple[int, int]]:
        """
        Execute one PLC scan cycle.
        Returns (from_step, to_step) if a transition fired, else None.
        """
        if not self._running or self._paused:
            return None

        self._scan_count += 1
        active_steps = [s for s in self._steps.values() if s.active]

        # Execute actions of active steps
        for step in active_steps:
            if step.action:
                try:
                    step.action()
                except Exception as e:
                    print(f"[GRAFCET] Step {step.number} action error: {e}")

        # Evaluate transitions
        for trans in self._transitions:
            src = self._steps.get(trans.from_step)
            dst = self._steps.get(trans.to_step)
            if src is None or dst is None:
                continue
            if src.active:
                try:
                    if trans.condition():
                        self._fire_transition(src, dst, trans)
                        return (trans.from_step, trans.to_step)
                except Exception as e:
                    print(f"[GRAFCET] Transition {trans.from_step}→{trans.to_step} error: {e}")

        return None

    # ── Queries ──────────────────────────────────────────────────────────────

    def current_step(self) -> Optional[Step]:
        for step in self._steps.values():
            if step.active:
                return step
        return None

    def current_step_name(self) -> str:
        s = self.current_step()
        return s.name if s else "NONE"

    def current_step_number(self) -> int:
        s = self.current_step()
        return s.number if s else -1

    def elapsed_in_step(self) -> float:
        s = self.current_step()
        return s.elapsed if s else 0.0

    def is_running(self) -> bool:
        return self._running and not self._paused

    def history(self, limit: int = 50) -> List[dict]:
        return self._history[-limit:]

    def status(self) -> dict:
        s = self.current_step()
        return {
            "running": self._running,
            "paused": self._paused,
            "current_step": s.number if s else None,
            "current_step_name": s.name if s else "NONE",
            "elapsed_s": round(s.elapsed if s else 0, 2),
            "scan_count": self._scan_count,
        }

    # ── Internal ─────────────────────────────────────────────────────────────

    def _activate_step(self, number: int) -> None:
        step = self._steps[number]
        step.active = True
        step.active_since = time.time()
        if step.on_entry:
            step.on_entry()

    def _deactivate_step(self, step: Step) -> None:
        if step.on_exit:
            step.on_exit()
        step.active = False
        step.active_since = None

    def _fire_transition(self, src: Step, dst: Step, trans: Transition) -> None:
        self._history.append({
            "t": time.time(),
            "from": src.number,
            "from_name": src.name,
            "to": dst.number,
            "to_name": dst.name,
            "label": trans.label,
            "elapsed_in_src": round(src.elapsed, 2),
        })
        self._deactivate_step(src)
        self._activate_step(dst.number)


# ── Refinery sequence factory ─────────────────────────────────────────────────

def build_refinery_sequence(process) -> GrafcetSequencer:
    """
    Build the main oil refinery GRAFCET sequence.

    Steps:
      S0 IDLE → S1 FILLING → S2 HEATING → S3 DISTILLATION → S4 DRAINING → S0
    """
    seq = GrafcetSequencer(initial_step=0)

    seq.add_step(0, "IDLE",
        on_entry=lambda: process.set_all_off(),
    )
    seq.add_step(1, "FILLING",
        on_entry=lambda: process.inlet_valve.open(),
        action=lambda: process.update_level(),
        on_exit=lambda: process.inlet_valve.close(),
    )
    seq.add_step(2, "HEATING",
        on_entry=lambda: process.heater.enable(),
        action=lambda: process.regulate_temperature(),
        on_exit=lambda: process.heater.disable(),
    )
    seq.add_step(3, "DISTILLATION",
        on_entry=lambda: process.distillation_column.start(),
        action=lambda: process.run_distillation(),
        on_exit=lambda: process.distillation_column.stop(),
    )
    seq.add_step(4, "DRAINING",
        on_entry=lambda: process.outlet_valve.open(),
        action=lambda: process.drain(),
        on_exit=lambda: process.outlet_valve.close(),
    )

    # Transitions
    seq.add_transition(0, 1,
        condition=lambda: process.start_command and process.tank_level < 80,
        label="START & tank not full",
    )
    seq.add_transition(1, 2,
        condition=lambda: process.tank_level >= 80,
        label="Tank full",
    )
    seq.add_transition(2, 3,
        condition=lambda: process.temperature >= 85.0,
        label="Temp ≥ 85°C",
    )
    seq.add_transition(3, 4,
        condition=lambda: process.output_flow < 0.5,
        label="Batch complete",
    )
    seq.add_transition(4, 0,
        condition=lambda: process.tank_level <= 5.0,
        label="Tank empty",
    )

    # Emergency stop: any step → S0
    for step_num in [1, 2, 3, 4]:
        seq.add_transition(step_num, 0,
            condition=lambda: process.emergency_stop,
            label="EMERGENCY STOP",
        )

    return seq
