# GRAFCET — Main Refinery Sequence

```
[S0] IDLE
 ↓  T0: start_command AND tank_level < 80%
[S1] FILLING
 ↓  T1: tank_level >= 80%
[S2] HEATING
 ↓  T2: temperature >= 85°C
[S3] DISTILLATION
 ↓  T3: output_flow < 0.5 L/min
[S4] DRAINING
 ↓  T4: tank_level <= 5%
[S0] IDLE
```

Emergency stop: any step → S0 immediately.
