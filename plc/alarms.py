"""
Alarm Management System — Oil Refinery Automation
Simulates TIA Portal alarm behaviour with priority levels.

Author: Wassim BELAID
"""

import time
from enum import Enum, auto
from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional


class AlarmPriority(Enum):
    INFO     = 1
    WARNING  = 2
    HIGH     = 3
    CRITICAL = 4


class AlarmState(Enum):
    INACTIVE    = auto()
    ACTIVE      = auto()
    ACKNOWLEDGED = auto()
    RESOLVED    = auto()


@dataclass
class AlarmDefinition:
    """Static alarm configuration."""
    tag: str
    description: str
    priority: AlarmPriority
    high_limit: Optional[float] = None
    low_limit: Optional[float] = None
    hysteresis: float = 0.0          # Prevents chattering
    on_trigger: Optional[Callable] = None  # Callback when alarm fires


@dataclass
class AlarmEvent:
    """One alarm occurrence."""
    tag: str
    description: str
    priority: AlarmPriority
    state: AlarmState
    value: float
    timestamp: float = field(default_factory=time.time)
    ack_timestamp: Optional[float] = None
    resolved_timestamp: Optional[float] = None
    operator: str = "SYSTEM"

    @property
    def age_seconds(self) -> float:
        return time.time() - self.timestamp

    def to_dict(self) -> dict:
        return {
            "tag": self.tag,
            "description": self.description,
            "priority": self.priority.name,
            "state": self.state.name,
            "value": round(self.value, 3),
            "timestamp": self.timestamp,
            "age_s": round(self.age_seconds, 1),
            "ack": self.ack_timestamp is not None,
        }


class AlarmManager:
    """
    Centralized alarm manager.

    Features:
    - High / Low limit alarms
    - Hysteresis (anti-chattering)
    - Alarm acknowledgement
    - Event history
    - Alarm suppression

    Usage:
        mgr = AlarmManager()
        mgr.define("HIGH_TEMP", "Temperature too high", AlarmPriority.CRITICAL,
                   high_limit=120.0, hysteresis=2.0)
        mgr.check("HIGH_TEMP", value=125.0)
        active = mgr.active_alarms()
    """

    def __init__(self):
        self._definitions: Dict[str, AlarmDefinition] = {}
        self._events: Dict[str, AlarmEvent] = {}
        self._history: List[AlarmEvent] = []
        self._suppressed: set = set()

    # ── Configuration ────────────────────────────────────────────────────────

    def define(
        self,
        tag: str,
        description: str,
        priority: AlarmPriority,
        high_limit: Optional[float] = None,
        low_limit: Optional[float] = None,
        hysteresis: float = 0.0,
        on_trigger: Optional[Callable] = None,
    ) -> None:
        """Register an alarm definition."""
        self._definitions[tag] = AlarmDefinition(
            tag=tag,
            description=description,
            priority=priority,
            high_limit=high_limit,
            low_limit=low_limit,
            hysteresis=hysteresis,
            on_trigger=on_trigger,
        )

    # ── Runtime ──────────────────────────────────────────────────────────────

    def check(self, tag: str, value: float) -> Optional[AlarmEvent]:
        """
        Evaluate alarm condition for a tag.
        Returns the AlarmEvent if state changed, else None.
        """
        if tag not in self._definitions:
            raise KeyError(f"Alarm '{tag}' not defined. Call define() first.")

        if tag in self._suppressed:
            return None

        defn = self._definitions[tag]
        triggered = False

        if defn.high_limit is not None and value > defn.high_limit:
            triggered = True
        if defn.low_limit is not None and value < defn.low_limit:
            triggered = True

        current = self._events.get(tag)

        if triggered:
            if current is None or current.state in (AlarmState.INACTIVE, AlarmState.RESOLVED):
                # New alarm
                event = AlarmEvent(
                    tag=tag,
                    description=defn.description,
                    priority=defn.priority,
                    state=AlarmState.ACTIVE,
                    value=value,
                )
                self._events[tag] = event
                self._history.append(event)
                if defn.on_trigger:
                    defn.on_trigger(event)
                return event
        else:
            # Check hysteresis for reset
            if current and current.state in (AlarmState.ACTIVE, AlarmState.ACKNOWLEDGED):
                reset = False
                if defn.high_limit is not None and value < defn.high_limit - defn.hysteresis:
                    reset = True
                if defn.low_limit is not None and value > defn.low_limit + defn.hysteresis:
                    reset = True
                if reset or (defn.high_limit is None and defn.low_limit is None):
                    current.state = AlarmState.RESOLVED
                    current.resolved_timestamp = time.time()
                    del self._events[tag]
                    return current

        return None

    def acknowledge(self, tag: str, operator: str = "OPERATOR") -> bool:
        """Acknowledge an active alarm."""
        if tag in self._events:
            ev = self._events[tag]
            if ev.state == AlarmState.ACTIVE:
                ev.state = AlarmState.ACKNOWLEDGED
                ev.ack_timestamp = time.time()
                ev.operator = operator
                return True
        return False

    def acknowledge_all(self, operator: str = "OPERATOR") -> int:
        count = 0
        for tag in list(self._events):
            if self.acknowledge(tag, operator):
                count += 1
        return count

    def suppress(self, tag: str) -> None:
        self._suppressed.add(tag)

    def unsuppress(self, tag: str) -> None:
        self._suppressed.discard(tag)

    # ── Queries ──────────────────────────────────────────────────────────────

    def active_alarms(self) -> List[AlarmEvent]:
        """Return all currently active (unresolved) alarms, sorted by priority."""
        return sorted(
            self._events.values(),
            key=lambda e: e.priority.value,
            reverse=True,
        )

    def unacknowledged(self) -> List[AlarmEvent]:
        return [e for e in self._events.values() if e.state == AlarmState.ACTIVE]

    def history(self, limit: int = 100) -> List[dict]:
        return [e.to_dict() for e in self._history[-limit:]]

    def summary(self) -> dict:
        active = self.active_alarms()
        return {
            "total_active": len(active),
            "critical": sum(1 for e in active if e.priority == AlarmPriority.CRITICAL),
            "high":     sum(1 for e in active if e.priority == AlarmPriority.HIGH),
            "warning":  sum(1 for e in active if e.priority == AlarmPriority.WARNING),
            "info":     sum(1 for e in active if e.priority == AlarmPriority.INFO),
            "unacknowledged": len(self.unacknowledged()),
        }

    def __repr__(self) -> str:
        s = self.summary()
        return f"AlarmManager(active={s['total_active']}, critical={s['critical']})"


# ── Pre-configured refinery alarm set ────────────────────────────────────────

def refinery_alarms() -> AlarmManager:
    """
    Returns an AlarmManager pre-loaded with standard refinery alarms.
    Based on real process limits from Cevital oil refinery.
    """
    mgr = AlarmManager()

    # Temperature alarms
    mgr.define("TEMP_HIGH_WARN",  "Heater temperature high",         AlarmPriority.WARNING,  high_limit=100.0, hysteresis=2.0)
    mgr.define("TEMP_HIGH_CRIT",  "Heater temperature CRITICAL",     AlarmPriority.CRITICAL, high_limit=130.0, hysteresis=3.0)
    mgr.define("TEMP_LOW",        "Heater temperature too low",       AlarmPriority.HIGH,     low_limit=40.0,  hysteresis=2.0)

    # Pressure alarms
    mgr.define("PRES_HIGH_WARN",  "Distillation pressure high",      AlarmPriority.WARNING,  high_limit=6.0,  hysteresis=0.2)
    mgr.define("PRES_HIGH_CRIT",  "Distillation pressure CRITICAL",  AlarmPriority.CRITICAL, high_limit=8.0,  hysteresis=0.3)

    # Tank level alarms
    mgr.define("LEVEL_HIGH",      "Raw oil tank level high",          AlarmPriority.HIGH,     high_limit=90.0, hysteresis=2.0)
    mgr.define("LEVEL_LOW_WARN",  "Raw oil tank level low",           AlarmPriority.WARNING,  low_limit=20.0,  hysteresis=2.0)
    mgr.define("LEVEL_LOW_CRIT",  "Raw oil tank EMPTY — pump stop",   AlarmPriority.CRITICAL, low_limit=5.0,   hysteresis=1.0)

    # Flow alarms
    mgr.define("FLOW_NO_FLOW",    "No flow detected — pump running",  AlarmPriority.HIGH,     low_limit=1.0,  hysteresis=0.5)
    mgr.define("FLOW_HIGH",       "Excessive flow rate",              AlarmPriority.WARNING,  high_limit=120.0, hysteresis=5.0)

    return mgr
