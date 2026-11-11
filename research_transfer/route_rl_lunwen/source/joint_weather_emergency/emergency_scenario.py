"""Causal, event-driven emergency-task wind environment.

This module is a development/reference environment, not a performance claim.  A
policy receives only the current observation and selects a physical route action
(TARGET, RETURN, or WAIT).  Future wind and unreleased emergency tasks never
enter the observation.  The simulator uses the versioned shared wind flight
integrator supplied beside this file.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import hashlib
import json
import math
import random
from typing import Any, Callable, Dict, Iterable, List, Optional, Sequence, Tuple

from shared_replay_v2 import Trace, flight

STRICT_VALIDATION = True


def _num(
    value: Any,
    name: str,
    *,
    positive: bool = False,
    allow_inf: bool = False,
    allow_negative: bool = False,
) -> float:
    if type(value) not in (int, float):
        raise ValueError(name + "_FINITE_NUMBER_REQUIRED")
    if math.isnan(float(value)) or (not allow_inf and not math.isfinite(float(value))):
        raise ValueError(name + "_FINITE_NUMBER_REQUIRED")
    if positive and float(value) <= 0:
        raise ValueError(name + "_POSITIVE_REQUIRED")
    if not positive and not allow_negative and float(value) < 0:
        raise ValueError(name + "_NONNEGATIVE_REQUIRED")
    return float(value)


def _fingerprint_value(value: Any) -> Any:
    """Map JSON-nonfinite floats to explicit tokens without losing identity."""
    if isinstance(value, float):
        if math.isnan(value):
            raise ValueError("FINGERPRINT_NAN")
        if math.isinf(value):
            return "INF" if value > 0 else "-INF"
        return value
    if isinstance(value, dict):
        return {str(k): _fingerprint_value(v) for k, v in value.items()}
    if isinstance(value, (tuple, list)):
        return [_fingerprint_value(v) for v in value]
    return value


@dataclass(frozen=True)
class Station:
    id: int
    x: float
    y: float


@dataclass(frozen=True)
class Task:
    id: int
    station_id: int
    x: float
    y: float
    energy: float
    service: float
    release: float = 0.0
    deadline: float = math.inf
    priority: int = 0
    emergency: bool = False


@dataclass(frozen=True)
class EmergencyConfig:
    horizon: float = 180.0
    speed: float = 900.0
    flight_power: float = 0.018
    time_cost: float = 0.5
    max_wait: float = 5.0
    service_power: float = 0.0
    duty_limit: float = 120.0
    fixed_cost: float = 0.0


@dataclass(frozen=True)
class Scenario:
    scenario_id: str
    stations: Tuple[Station, ...]
    tasks: Tuple[Task, ...]
    drone_stations: Tuple[int, ...]
    capacities: Tuple[float, ...]
    trace: Trace
    config: EmergencyConfig = field(default_factory=EmergencyConfig)
    forecast: Tuple[float, float] = (0.0, 0.0)

    def __post_init__(self) -> None:
        self.validate()

    def validate(self) -> None:
        if not self.scenario_id or not isinstance(self.scenario_id, str):
            raise ValueError("SCENARIO_ID")
        if not isinstance(self.config, EmergencyConfig):
            raise ValueError("CONFIG_TYPE")
        if not self.stations:
            raise ValueError("STATIONS_REQUIRED")
        if any(not isinstance(s, Station) for s in self.stations):
            raise ValueError("STATION_TYPE")
        if any(type(s.id) is not int for s in self.stations):
            raise ValueError("STATION_ID_TYPE")
        station_ids = [s.id for s in self.stations]
        if len(set(station_ids)) != len(station_ids):
            raise ValueError("DUPLICATE_STATION_ID")
        for s in self.stations:
            _num(s.x, "STATION_X", allow_negative=True)
            _num(s.y, "STATION_Y", allow_negative=True)
        if len(self.drone_stations) != len(self.capacities) or not self.capacities:
            raise ValueError("DRONE_DIMENSION")
        if any(type(sid) is not int for sid in self.drone_stations):
            raise ValueError("DRONE_STATION_ID_TYPE")
        for sid in self.drone_stations:
            if sid not in station_ids:
                raise ValueError("DRONE_STATION")
        for cap in self.capacities:
            _num(cap, "CAPACITY", positive=True)
        c = self.config
        _num(c.horizon, "HORIZON", positive=True)
        _num(c.speed, "SPEED", positive=True)
        _num(c.flight_power, "FLIGHT_POWER")
        _num(c.time_cost, "TIME_COST")
        _num(c.max_wait, "MAX_WAIT", positive=True)
        _num(c.service_power, "SERVICE_POWER")
        _num(c.duty_limit, "DUTY_LIMIT", positive=True)
        _num(c.fixed_cost, "FIXED_COST")
        if len(self.forecast) != 2:
            raise ValueError("FORECAST")
        for value in self.forecast:
            _num(value, "FORECAST", allow_negative=True)
        if any(not isinstance(t, Task) for t in self.tasks):
            raise ValueError("TASK_TYPE")
        if any(type(t.id) is not int for t in self.tasks):
            raise ValueError("TASK_ID_TYPE")
        ids = [t.id for t in self.tasks]
        if len(set(ids)) != len(ids):
            raise ValueError("DUPLICATE_TASK_ID")
        for t in self.tasks:
            if type(t.station_id) is not int:
                raise ValueError("TASK_STATION_ID_TYPE")
            if t.station_id not in station_ids:
                raise ValueError("TASK_STATION")
            _num(t.x, "TASK_X", allow_negative=True)
            _num(t.y, "TASK_Y", allow_negative=True)
            _num(t.energy, "TASK_ENERGY")
            _num(t.service, "TASK_SERVICE")
            _num(t.release, "TASK_RELEASE")
            _num(t.deadline, "TASK_DEADLINE", allow_inf=True)
            if STRICT_VALIDATION and t.deadline < t.release:
                raise ValueError("TASK_DEADLINE_BEFORE_RELEASE")
            if t.emergency and not math.isfinite(t.deadline):
                raise ValueError("EMERGENCY_DEADLINE_REQUIRED")
            if not isinstance(t.emergency, bool):
                raise ValueError("TASK_EMERGENCY_TYPE")
            if (
                type(t.priority) is not int
                or t.priority < 0
            ):
                raise ValueError("TASK_PRIORITY")
            if t.release > c.horizon:
                raise ValueError("TASK_RELEASE_AFTER_HORIZON")
        if not isinstance(self.trace, Trace) or not self.trace.intervals:
            raise ValueError("TRACE_REQUIRED")
        if self.trace.intervals[-1][0] < c.horizon:
            raise ValueError("TRACE_SHORTER_THAN_HORIZON")

    @property
    def station_map(self) -> Dict[int, Station]:
        return {s.id: s for s in self.stations}

    @property
    def task_map(self) -> Dict[int, Task]:
        return {t.id: t for t in self.tasks}

    def fingerprint(self) -> str:
        payload = {
            "scenario_id": self.scenario_id,
            "stations": [s.__dict__ for s in self.stations],
            "tasks": [t.__dict__ for t in self.tasks],
            "drone_stations": self.drone_stations,
            "capacities": self.capacities,
            "trace": self.trace.intervals,
            "config": self.config.__dict__,
            "forecast": self.forecast,
        }
        return hashlib.sha256(
            json.dumps(_fingerprint_value(payload), sort_keys=True, allow_nan=False).encode()
        ).hexdigest()


@dataclass(frozen=True)
class Action:
    kind: str
    target_id: Optional[int] = None
    wait_min: Optional[float] = None

    @staticmethod
    def target(target_id: int) -> "Action":
        if type(target_id) is not int:
            raise ValueError("TARGET_ID_TYPE")
        return Action("TARGET", target_id, None)

    @staticmethod
    def return_to_station() -> "Action":
        return Action("RETURN", None, None)

    @staticmethod
    def wait(minutes: float = 1.0) -> "Action":
        if (
            type(minutes) not in (int, float)
            or not math.isfinite(float(minutes))
        ):
            raise ValueError("WAIT_DURATION_TYPE")
        return Action("WAIT", None, float(minutes))


@dataclass(frozen=True)
class TaskView:
    id: int
    station_id: int
    x: float
    y: float
    energy: float
    service: float
    release: float
    deadline: float
    priority: int
    emergency: bool


@dataclass(frozen=True)
class DroneView:
    id: int
    station_id: int
    x: float
    y: float
    at_station: bool
    trip_energy: float
    duty: float
    terminal_failure: Optional[str]
    trip_task_ids: Tuple[int, ...]


@dataclass(frozen=True)
class Observation:
    now: float
    acting_drone: int
    wind_now: Tuple[float, float]
    forecast: Tuple[float, float]
    own: DroneView
    fleet: Tuple[DroneView, ...]
    visible_tasks: Tuple[TaskView, ...]
    served_ids: Tuple[int, ...]
    deadline_missed_ids: Tuple[int, ...]

    def to_dict(self) -> Dict[str, Any]:
        # Deliberately excludes Scenario.tasks after the release frontier and
        # excludes the Trace, so a policy cannot read future exogenous data.
        return {
            "now": self.now,
            "acting_drone": self.acting_drone,
            "wind_now": self.wind_now,
            "forecast": self.forecast,
            "own": self.own.__dict__,
            "fleet": [x.__dict__ for x in self.fleet],
            "visible_tasks": [x.__dict__ for x in self.visible_tasks],
            "served_ids": self.served_ids,
            "deadline_missed_ids": self.deadline_missed_ids,
        }


@dataclass
class _Drone:
    id: int
    station_id: int
    x: float
    y: float
    trip_energy: float = 0.0
    duty: float = 0.0
    at_station: bool = True
    trip_started: bool = False
    terminal_failure: Optional[str] = None
    trip_task_ids: List[int] = field(default_factory=list)
    served_trip_ids: List[int] = field(default_factory=list)
    last_return_time: Optional[float] = None
    last_time: float = 0.0


Policy = Callable[[Observation], Action]


class EmergencySimulator:
    """Exact event simulator with deterministic tie-breaking by drone id."""

    def __init__(self, scenario: Scenario):
        scenario.validate()
        self.scenario = scenario
        self._execution_trace = self._trace_until(scenario.config.horizon)
        station = scenario.station_map
        self.now = 0.0
        self.tasks = scenario.task_map
        self.status: Dict[int, str] = {t.id: "UNRELEASED" for t in scenario.tasks}
        self.reserved_by: Dict[int, int] = {}
        self.served_at: Dict[int, float] = {}
        self.returned_at: Dict[int, float] = {}
        self.deadline_missed: set[int] = set()
        self.action_log: List[Dict[str, Any]] = []
        self.events: List[Tuple[float, int, int, str, Dict[str, Any]]] = []
        self._seq = 0
        self.drones: List[_Drone] = []
        for i, (sid, _) in enumerate(zip(scenario.drone_stations, scenario.capacities)):
            s = station[sid]
            self.drones.append(_Drone(i, sid, s.x, s.y))
        self._release_until(0.0)

    def _push(
        self, when: float, drone_id: int, kind: str, payload: Dict[str, Any]
    ) -> None:
        if not math.isfinite(float(when)):
            raise ValueError("EVENT_TIME_NONFINITE")
        if float(when) < self.now:
            raise ValueError("EVENT_TIME_REVERSED")
        self._seq += 1
        self.events.append((float(when), self._seq, drone_id, kind, payload))
        self.events.sort(key=lambda x: (x[0], x[2], x[1]))

    def _release_until(self, t: float) -> None:
        t = float(t)
        if not math.isfinite(t) or t < self.now:
            raise RuntimeError("SIMULATION_TIME_REGRESSION")
        # All drones share the same physical frontier, including drones whose
        # next completion event is later than another drone's decision.
        for event in self.events:
            self._accrue_event(event, t)
        self.now = t
        for task in self.scenario.tasks:
            if self.status[task.id] == "UNRELEASED" and task.release <= self.now:
                self.status[task.id] = "AVAILABLE"
            if (
                task.id not in self.served_at
                and self.now > task.deadline
                and task.deadline < math.inf
            ):
                self.deadline_missed.add(task.id)

    def _trace_until(self, until: float) -> Trace:
        rows = []
        for end, wx, wy in self.scenario.trace.intervals:
            rows.append((min(end, until), wx, wy))
            if end >= until:
                break
        return Trace(tuple(rows), scenario_id=self.scenario.trace.scenario_id)

    def _phase_start(self, d: _Drone) -> Dict[str, Any]:
        return {"start": self.now, "base_energy": d.trip_energy,
                "base_duty": d.duty, "origin": (d.x, d.y)}

    def _accrue_event(
        self, event: Tuple[float, int, int, str, Dict[str, Any]], until: float
    ) -> None:
        when, _, did, kind, payload = event
        if kind == "WAIT_END":
            return
        start = payload["start"]
        end = min(when, until)
        d = self.drones[did]
        elapsed = max(0.0, end - start)
        if "result" in payload:
            if end == when:
                prefix = payload["result"]
            elif end == start:
                prefix = {"energy": 0.0, "position": payload["origin"]}
            else:
                ox, oy = payload["origin"]
                tx, ty = payload["destination"]
                prefix = flight(
                    type("Node", (), {"x": ox, "y": oy, "energy": 0.0,
                                      "service": 0.0})(),
                    type("Node", (), {"x": tx, "y": ty, "energy": 0.0,
                                      "service": 0.0})(),
                    start, payload["available"],
                    self.scenario.config.flight_power, self.scenario.config.speed,
                    self._trace_until(end),
                )
            consumed = float(prefix["energy"])
            d.x, d.y = prefix["position"]
        else:
            # Zero-duration service is an impulse at its event. For positive
            # durations use bounded ratios, avoiding energy / duration overflow.
            consumed = payload["service_energy"]
            if end < when:
                consumed *= min(1.0, elapsed / payload["duration"])
        # Recompute from the phase origin, so repeated frontier observations
        # and final event handling cannot count the same prefix twice.
        d.trip_energy = payload["base_energy"] + consumed
        d.duty = payload["base_duty"] + elapsed
        d.last_time = end

    def _wind_now(self) -> Tuple[float, float]:
        try:
            _, wx, wy = self.scenario.trace.current(self.now)
            return (float(wx), float(wy))
        except ValueError:
            return (float("nan"), float("nan"))

    def _view_drone(self, d: _Drone) -> DroneView:
        return DroneView(
            d.id,
            d.station_id,
            d.x,
            d.y,
            d.at_station,
            d.trip_energy,
            d.duty,
            d.terminal_failure,
            tuple(d.trip_task_ids),
        )

    def observation(self, drone_id: int) -> Observation:
        d = self.drones[drone_id]
        visible = []
        for task in self.scenario.tasks:
            if self.status[task.id] == "AVAILABLE":
                visible.append(
                    TaskView(
                        task.id,
                        task.station_id,
                        task.x,
                        task.y,
                        task.energy,
                        task.service,
                        task.release,
                        task.deadline,
                        task.priority,
                        task.emergency,
                    )
                )
        visible.sort(key=lambda x: x.id)
        return Observation(
            self.now,
            drone_id,
            self._wind_now(),
            self.scenario.forecast,
            self._view_drone(d),
            tuple(self._view_drone(x) for x in self.drones),
            tuple(visible),
            tuple(sorted(self.served_at)),
            tuple(sorted(self.deadline_missed)),
        )

    def action_mask(self, drone_id: int) -> Dict[str, Any]:
        if type(drone_id) is not int or not 0 <= drone_id < len(self.drones):
            raise ValueError("DRONE_ID")
        d = self.drones[drone_id]
        actionable = (
            self.now < self.scenario.config.horizon
            and d.terminal_failure is None
            and not any(event[2] == drone_id for event in self.events)
        )
        targets = [
            t.id
            for t in self.scenario.tasks
            if actionable
            and self.status[t.id] == "AVAILABLE"
            and t.station_id == d.station_id
        ]
        targets.sort()
        return {
            "TARGET": targets,
            "RETURN": bool(actionable and not d.at_station and d.trip_started),
            "WAIT": bool(actionable and d.at_station),
        }

    def _fail(self, d: _Drone, reason: str) -> None:
        d.terminal_failure = reason
        d.last_time = self.now
        self.action_log.append(
            {"time": self.now, "drone": d.id, "event": "FAILURE", "reason": reason}
        )

    def _validate_action(self, d: _Drone, action: Action) -> None:
        if not isinstance(action, Action):
            raise ValueError("ACTION_TYPE")
        if action.kind not in {"TARGET", "RETURN", "WAIT"}:
            raise ValueError("ACTION_KIND")
        if action.kind == "TARGET":
            if (
                type(action.target_id) is not int
                or action.target_id not in self.tasks
            ):
                raise ValueError("TARGET_ID")
            task = self.tasks[action.target_id]
            if self.status[task.id] != "AVAILABLE" or task.station_id != d.station_id:
                raise ValueError("TARGET_NOT_VISIBLE")
        elif action.kind == "RETURN":
            if d.at_station or not d.trip_started:
                raise ValueError("RETURN_AT_STATION")
        else:
            if not d.at_station:
                raise ValueError("WAIT_IN_FLIGHT")
            if (
                action.wait_min is None
                or type(action.wait_min) not in (int, float)
                or not math.isfinite(float(action.wait_min))
            ):
                raise ValueError("WAIT_DURATION")
            if float(action.wait_min) <= 0 or float(action.wait_min) > self.scenario.config.max_wait:
                raise ValueError("WAIT_DURATION")
            self._wait_end(float(action.wait_min))

    def _wait_end(self, duration: float) -> float:
        remaining = self.scenario.config.horizon - self.now
        end = self.scenario.config.horizon if duration >= remaining else self.now + duration
        if end <= self.now:
            raise ValueError("WAIT_CLOCK_NO_PROGRESS")
        return end

    def _start_target(self, d: _Drone, task: Task) -> None:
        if d.at_station:
            d.trip_started = True
            d.trip_energy = 0.0
            d.trip_task_ids.clear()
            d.served_trip_ids.clear()
        d.at_station = False
        self.status[task.id] = "IN_FLIGHT"
        self.reserved_by[task.id] = d.id
        d.trip_task_ids.append(task.id)
        # The remaining-energy argument is the exact trip battery budget.
        available = self.scenario.capacities[d.id] - d.trip_energy
        result = flight(
            type("Node", (), {"x": d.x, "y": d.y, "energy": 0.0, "service": 0.0})(),
            type(
                "Node", (), {"x": task.x, "y": task.y, "energy": 0.0, "service": 0.0}
            )(),
            self.now,
            available,
            self.scenario.config.flight_power,
            self.scenario.config.speed,
            self._execution_trace,
        )
        self._push(
            float(result["end"]),
            d.id,
            ("ARRIVE_TARGET" if result["failed"] is None
             else "FLIGHT_HORIZON" if result["failed"] == "HORIZON_EXCEEDED"
             else "FLIGHT_FAIL"),
            {**self._phase_start(d), "task_id": task.id, "result": result,
             "available": available, "destination": (task.x, task.y)},
        )

    def _start_return(self, d: _Drone) -> None:
        station = self.scenario.station_map[d.station_id]
        available = self.scenario.capacities[d.id] - d.trip_energy
        result = flight(
            type("Node", (), {"x": d.x, "y": d.y, "energy": 0.0, "service": 0.0})(),
            type(
                "Node",
                (),
                {"x": station.x, "y": station.y, "energy": 0.0, "service": 0.0},
            )(),
            self.now,
            available,
            self.scenario.config.flight_power,
            self.scenario.config.speed,
            self._execution_trace,
        )
        self._push(
            float(result["end"]),
            d.id,
            ("RETURN_END" if result["failed"] is None
             else "RETURN_HORIZON" if result["failed"] == "HORIZON_EXCEEDED"
             else "RETURN_FAIL"),
            {**self._phase_start(d), "result": result, "available": available,
             "destination": (station.x, station.y)},
        )

    def _start_service(self, d: _Drone, task: Task) -> None:
        available = max(0.0, self.scenario.capacities[d.id] - d.trip_energy)
        if task.service == 0:
            failed = task.energy > available
            duration = 0.0
            consumed = 0.0 if failed else task.energy
        else:
            failed = task.energy > available
            duration = task.service * (available / task.energy) if failed else task.service
            consumed = available if failed else task.energy
        kind = "SERVICE_FAIL" if failed else "SERVICE_END"
        remaining = self.scenario.config.horizon - self.now
        # Completion exactly at H is observable.  A future energy failure
        # landing exactly at H is a truncated phase, not a post-horizon
        # terminal failure.
        if duration > remaining or (failed and duration >= remaining):
            consumed = 0.0 if duration == 0.0 else consumed * remaining / duration
            duration = remaining
            kind = "SERVICE_HORIZON"
        self._push(
            self.now + duration,
            d.id,
            kind,
            {**self._phase_start(d), "task_id": task.id,
             "duration": duration, "service_energy": consumed},
        )

    def _handle_event(
        self, event: Tuple[float, int, int, str, Dict[str, Any]], decisions: set[int]
    ) -> None:
        when, _, did, kind, payload = event
        self._release_until(when)
        d = self.drones[did]
        d.last_time = self.now
        if kind == "WAIT_END":
            decisions.add(did)
            return
        self._accrue_event(event, when)
        result = payload.get("result", {})
        if kind == "FLIGHT_FAIL":
            self.status[payload["task_id"]] = "FAILED"
            self._fail(d, str(result.get("failed", "FLIGHT_FAILURE")))
            return
        if kind == "RETURN_FAIL":
            self._fail(d, str(result.get("failed", "RETURN_FAILURE")))
            return
        if kind in {"FLIGHT_HORIZON", "RETURN_HORIZON", "SERVICE_HORIZON"}:
            # The finite horizon truncates an in-flight leg. Preserve the
            # unfinished task/return state without fabricating a terminal
            # physics failure or a post-horizon success.
            return
        if kind == "SERVICE_FAIL":
            self.status[payload["task_id"]] = "FAILED"
            self._fail(d, "SERVICE_ENERGY")
            return
        if d.duty > self.scenario.config.duty_limit:
            self._fail(d, "DUTY_LIMIT")
            return
        if kind == "ARRIVE_TARGET":
            d.x, d.y = (
                self.tasks[payload["task_id"]].x,
                self.tasks[payload["task_id"]].y,
            )
            self._start_service(d, self.tasks[payload["task_id"]])
            return
        if kind == "SERVICE_END":
            tid = payload["task_id"]
            self.status[tid] = "SERVED"
            self.served_at[tid] = self.now
            d.served_trip_ids.append(tid)
            decisions.add(did)
            return
        if kind == "RETURN_END":
            station = self.scenario.station_map[d.station_id]
            d.x, d.y = station.x, station.y
            d.at_station = True
            d.trip_started = False
            d.trip_energy = 0.0
            d.last_return_time = self.now
            for tid in d.served_trip_ids:
                self.returned_at[tid] = self.now
            d.trip_task_ids.clear()
            d.served_trip_ids.clear()
            decisions.add(did)
            return
        raise RuntimeError("UNKNOWN_EVENT:" + kind)

    def _apply_action(self, d: _Drone, action: Action, decisions: set[int]) -> None:
        self._validate_action(d, action)
        self.action_log.append(
            {"time": self.now, "drone": d.id, "action": action.__dict__}
        )
        if action.kind == "TARGET":
            self._start_target(d, self.tasks[action.target_id])
            return
        if action.kind == "RETURN":
            self._start_return(d)
            return
        self._push(self._wait_end(float(action.wait_min)), d.id, "WAIT_END", {})

    def run(self, policy: Policy) -> Dict[str, Any]:
        decisions = set(range(len(self.drones)))
        horizon = self.scenario.config.horizon
        while True:
            self._release_until(self.now)
            # Drain the exact-time event closure before exposing a new decision
            # frontier. Positive waits must advance binary64 simulation time.
            while self.events and self.events[0][0] == self.now:
                self._handle_event(self.events.pop(0), decisions)
            # All decisions at a timestamp see the same causal frontier; drone
            # id is the only tie-break and reserved tasks disappear thereafter.
            if self.now < horizon:
                for did in sorted(tuple(decisions)):
                    decisions.discard(did)
                    d = self.drones[did]
                    if d.terminal_failure is not None:
                        continue
                    try:
                        obs = self.observation(did)
                        action = policy(obs)
                        self._apply_action(d, action, decisions)
                    except Exception as exc:
                        self._fail(
                            d,
                            "INVALID_ACTION:" + type(exc).__name__ + ":" + str(exc),
                        )
            else:
                decisions.clear()
            if not self.events:
                next_release = min(
                    (
                        t.release
                        for t in self.scenario.tasks
                        if self.status[t.id] == "UNRELEASED"
                    ),
                    default=math.inf,
                )
                if next_release <= horizon and next_release > self.now:
                    self._release_until(next_release)
                    decisions.update(
                        d.id
                        for d in self.drones
                        if d.at_station and d.terminal_failure is None
                    )
                    continue
                break
            next_time = self.events[0][0]
            if next_time > horizon:
                self.now = horizon
                self._release_until(horizon)
                break
            self.now = next_time
            # Exact ordering is essential: nearby timestamps are distinct
            # causal frontiers and must never be grouped by a tolerance.
        self._release_until(horizon)
        return self.result()

    def result(self) -> Dict[str, Any]:
        emergency = [t for t in self.scenario.tasks if t.emergency]

        def task_row(t: Task) -> Dict[str, Any]:
            delivered = t.id in self.served_at
            at = self.served_at.get(t.id)
            return {
                "id": t.id,
                "emergency": t.emergency,
                "release": t.release,
                "deadline": t.deadline,
                "served": delivered,
                "served_at": at,
                "returned_at": self.returned_at.get(t.id),
                "on_time": bool(delivered and at <= t.deadline),
                "late_by": (None if not delivered else max(0.0, at - t.deadline)),
                "status": self.status[t.id],
            }

        rows = [task_row(t) for t in self.scenario.tasks]
        ontime = sum(r["on_time"] for r in rows if r["emergency"])
        emergency_count = len(emergency)
        all_served = all(r["served"] for r in rows)
        all_returned = all(
            (not r["served"]) or r["returned_at"] is not None for r in rows
        )
        complete = (
            all_served
            and all_returned
            and not any(d.terminal_failure for d in self.drones)
        )
        makespan = max((d.last_return_time or 0.0 for d in self.drones), default=0.0)
        duty_violation = any(
            d.duty > self.scenario.config.duty_limit for d in self.drones
        )
        failures = [d.terminal_failure for d in self.drones if d.terminal_failure]
        incurred = (
            self.scenario.config.fixed_cost
            + self.scenario.config.time_cost * sum(d.duty for d in self.drones)
        )
        return {
            "scenario_id": self.scenario.scenario_id,
            "scenario_fingerprint": self.scenario.fingerprint(),
            "emergency_task_count": emergency_count,
            "emergency_on_time": ontime / emergency_count if emergency_count else None,
            "emergency_delivered": sum(r["served"] for r in rows if r["emergency"])
            / emergency_count
            if emergency_count
            else None,
            "emergency_returned": sum(
                r["returned_at"] is not None for r in rows if r["emergency"]
            )
            / emergency_count
            if emergency_count
            else None,
            "weighted_lateness": sum(
                (r["late_by"] or 0.0) * (10 if r["emergency"] else 1) for r in rows
            ),
            "undelivered": sum(not r["served"] for r in rows),
            "deadline_misses": len(self.deadline_missed),
            "terminal_failures": failures,
            "invalid_actions": sum("INVALID_ACTION" in str(x) for x in failures),
            "duty_violation": duty_violation,
            "complete_return": complete,
            "makespan": makespan if complete else None,
            "incurred_cost": incurred,
            "tasks": rows,
            "actions": list(self.action_log),
        }


def make_fixture(level: str = "moderate", seed: int = 0) -> Scenario:
    """Create a deterministic, pre-registered emergency fixture family.

    The generator does not inspect a policy or choose a favorable outcome.  The
    emergency release and wind trace are fixed by (level, seed) before a run.
    """
    if level not in {"easy", "moderate", "tight", "adverse"}:
        raise ValueError("UNKNOWN_LEVEL")
    if isinstance(seed, bool) or not isinstance(seed, int) or seed < 0:
        raise ValueError("SEED")
    rng = random.Random(1009 + seed)
    station = Station(0, 0.0, 0.0)
    routine_xy = (
        (3200.0, 900.0),
        (4100.0, -700.0),
        (5000.0, 500.0),
        (5900.0, -450.0),
        (3600.0, -1400.0),
        (4700.0, 1300.0),
        (6200.0, 850.0),
        (5400.0, -1250.0),
    )
    routine = tuple(
        Task(
            i + 1,
            0,
            x,
            y,
            0.020 * (1 + i % 2),
            5.0,
            release=0.0,
            deadline=120.0 + i * 8,
            priority=1,
        )
        for i, (x, y) in enumerate(routine_xy)
    )
    ex_xy = ((5600.0, 1800.0), (6500.0, 1500.0), (5200.0, -1900.0), (7100.0, -1300.0))
    ex_x, ex_y = ex_xy[rng.randrange(len(ex_xy))]
    arrival = {"easy": 18.0, "moderate": 8.0, "tight": 5.0, "adverse": 5.0}[level]
    slack = {"easy": 45.0, "moderate": 20.0, "tight": 11.0, "adverse": 13.0}[level]
    emergency = Task(
        1000 + seed,
        0,
        ex_x,
        ex_y,
        0.030,
        4.0,
        release=arrival,
        deadline=arrival + slack,
        priority=10,
        emergency=True,
    )
    if level in {"adverse", "tight"}:
        wind = ((35.0, 220.0), (120.0, 260.0))
    else:
        wind = ((0.0, 0.0), (80.0, 50.0))
    intervals = ((40.0, *wind[0]), (100.0, *wind[1]), (180.0, *wind[0]))
    trace = Trace(tuple(intervals), scenario_id="emergency-" + level)
    cfg = EmergencyConfig(
        horizon=180.0,
        speed=900.0,
        flight_power=0.018,
        time_cost=0.5,
        max_wait=5.0,
        duty_limit=120.0,
    )
    return Scenario(
        "emergency_" + level + "_" + str(seed),
        (station,),
        routine + (emergency,),
        (0, 0),
        (0.81, 0.81),
        trace,
        cfg,
        forecast=wind[0],
    )


def emergency_first_policy(obs: Observation) -> Action:
    candidates = [t for t in obs.visible_tasks if t.station_id == obs.own.station_id]
    if not candidates:
        return (
            Action.return_to_station() if not obs.own.at_station else Action.wait(1.0)
        )
    candidates.sort(key=lambda t: (not t.emergency, t.deadline, -t.priority, t.id))
    return Action.target(candidates[0].id)


def routine_first_policy(obs: Observation) -> Action:
    candidates = [t for t in obs.visible_tasks if t.station_id == obs.own.station_id]
    if not candidates:
        return (
            Action.return_to_station() if not obs.own.at_station else Action.wait(1.0)
        )
    candidates.sort(key=lambda t: (t.emergency, t.deadline, t.id))
    return Action.target(candidates[0].id)


def slack_policy(obs: Observation) -> Action:
    candidates = [t for t in obs.visible_tasks if t.station_id == obs.own.station_id]
    if not candidates:
        return (
            Action.return_to_station() if not obs.own.at_station else Action.wait(1.0)
        )

    def key(t: TaskView) -> Tuple[float, int, int]:
        eta = math.hypot(t.x - obs.own.x, t.y - obs.own.y) / 900.0 + t.service
        return (t.deadline - obs.now - eta, -t.priority, t.id)

    candidates.sort(key=key)
    return Action.target(candidates[0].id)


def run_fixture_family(
    levels: Sequence[str] = ("easy", "moderate", "tight", "adverse"),
    seeds: Iterable[int] = range(3),
) -> List[Dict[str, Any]]:
    rows = []
    for level in levels:
        for seed in seeds:
            scenario = make_fixture(level, seed)
            for name, policy in (
                ("emergency_first", emergency_first_policy),
                ("routine_first", routine_first_policy),
                ("slack", slack_policy),
            ):
                result = EmergencySimulator(scenario).run(policy)
                rows.append(
                    {
                        "level": level,
                        "seed": seed,
                        "method": name,
                        "scenario_fingerprint": scenario.fingerprint(),
                        "emergency_task_count": sum(
                            bool(task.emergency) for task in scenario.tasks
                        ),
                        "emergency_on_time": result["emergency_on_time"],
                        "emergency_delivered": result["emergency_delivered"],
                        "emergency_returned": result["emergency_returned"],
                        "undelivered": result["undelivered"],
                        "complete_return": result["complete_return"],
                        "terminal_failures": result["terminal_failures"],
                    }
                )
    return rows
