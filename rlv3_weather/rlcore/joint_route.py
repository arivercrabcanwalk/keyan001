"""Joint physical route construction under one externally fixed wind.

An action is (original station index, author drone slot, target ID), or the
same pair followed by RETURN. Slots run in parallel; each slot's clock is its
cumulative operating duty, including every actual return. RETURN replaces the
battery, never the duty clock. There is no automatic return, repair or fallback.

FEATURE_NAMES is the versioned policy/heuristic observation contract. The mask
checks direct return reserves and necessary remaining-target opportunities; it
is not a complete feasibility oracle. Terminal solutions use fixed_anchor's
independent audit, including original map bytes. This module does not establish
author provenance or grant scientific eligibility.
"""
from copy import deepcopy
import math

from .common import load_ins, rel
from .fixed_anchor import audit_fixed_anchor, _wind, ENERGY_EPS

RETURN = -1
FEATURE_SCHEMA = "joint-route-physical-v1"
FEATURE_NAMES = (
    "is_return", "is_large_drone", "is_large_station", "at_station",
    "leg_dx_over_radius", "leg_dy_over_radius", "target_dx_over_radius",
    "target_dy_over_radius", "target_energy_over_battery", "service_over_duty_limit",
    "leg_minutes_over_duty_limit", "return_minutes_over_duty_limit",
    "used_energy_over_battery", "closed_energy_over_battery", "energy_slack_fraction",
    "duty_over_limit", "closed_duty_over_limit", "duty_slack_fraction",
    "current_closed_duty_over_600", "projected_team_makespan_over_600",
    "team_makespan_delta_over_600", "projected_closed_cost_over_cap",
    "remaining_service_cost_bound_over_cap", "station_remaining_fraction",
    "team_remaining_fraction", "other_slot_opportunity_fraction",
    "best_other_slot_finish_over_600", "target_has_no_other_slot",
    "slot_exclusive_remaining_fraction", "closed_duty_minus_sibling_over_600",
)
FEAT_DIM = len(FEATURE_NAMES)
EPS = 1e-7


class JointRoute:
    """Start from an audited same-wind deployment, then construct empty routes.

    The external anchor fixes only station type and target-to-station ownership.
    ``teacher_action`` can replay its trips; neither options nor feature vectors
    contain its target-to-slot labels, visit ranks, or objective values.
    ``source_slot_action`` is a separately named restricted reference.
    """

    def __init__(self, row, scenario, cap):
        if type(cap) not in (int, float) or not math.isfinite(cap) or cap <= 0:
            raise ValueError("positive finite original cost cap required")
        self.cap = float(cap)
        self.scenario, self.wind = _wind(scenario)
        self.path = rel(row["path"])
        self.instance = load_ins(self.path)
        self.anchor = deepcopy(row["solution"])
        self.anchor_audit = audit_fixed_anchor(self.instance, self.anchor,
                                               wind=self.scenario, map_path=self.path)
        if not self.anchor_audit["physical_feasible"]:
            raise ValueError("infeasible same-wind deployment: " + repr(self.anchor_audit["issues"]))
        if any(n.service <= 0 or n.id == RETURN for n in self.instance.targets):
            raise ValueError("positive service and target IDs different from RETURN required")
        self.params = self.instance.params
        self.targets = {n.id: n for n in self.instance.targets}
        self.types = tuple(self.anchor["station_types"])
        self.fixed = self.anchor_audit["metrics"]["fixed_cost"]
        self.assignment, self.source_slot, self.slots = {}, {}, {}
        self.routes = [[[], []] for _ in self.instance.stations]
        self._teacher = []
        for si, kind in enumerate(self.types):
            for di in ((0, 1) if kind == 2 else (1,) if kind == 1 else ()):
                s = self.instance.stations[si]
                key = (si, di)
                self.slots[key] = dict(si=si, di=di, node=s.id, energy=0.0,
                    duty=0.0, trip=[], capacity=self.instance.capacity(di),
                    limit=self.instance.duration(kind), returned=True)
                for trip in self.anchor["routes"][si][di]:
                    for tid in trip:
                        self.assignment[tid], self.source_slot[tid] = si, key
                        self._teacher.append((si, di, tid))
                    if trip:
                        self._teacher.append((si, di, RETURN))
        self.remaining = set(self.targets)
        self.trace = []
        self.done, self.fallback, self.termination_reason = False, False, None
        self.max_steps = 2 * len(self.targets)
        self._cache = None
        # Independent local implementation of the wind triangle. The auditor
        # computes original-coordinate legs separately and shares no route cache.
        self._travel = {}
        nodes = tuple(self.instance.targets) + tuple(self.instance.stations)
        for a in nodes:
            for b in nodes:
                dx, dy = b.x - a.x, b.y - a.y
                distance = math.hypot(dx, dy)
                if not distance:
                    duration = 0.0
                else:
                    ux, uy = dx / distance, dy / distance
                    along = self.wind[0] * ux + self.wind[1] * uy
                    cross = self.wind[0] * uy - self.wind[1] * ux
                    disc = (self.params.speed / 60.0) ** 2 - cross ** 2
                    ground = along + math.sqrt(disc) if disc >= 0 else 0.0
                    duration = distance / (60.0 * ground) if ground >= 4.0 else math.inf
                self._travel[a.id, b.id] = duration
        self._refresh()

    def _home(self, key):
        return self.instance.stations[key[0]].id

    def _closed_duty(self, key, state=None):
        d = self.slots[key] if state is None else state
        return d["duty"] + self._travel[d["node"], self._home(key)]

    def _target_state(self, key, tid, d=None):
        """Return the actual post-service state, reserving a real future return."""
        d = self.slots[key] if d is None else d
        if self.assignment[tid] != key[0]:
            return None
        node, station = self.targets[tid], self.instance.stations[key[0]]
        if math.hypot(node.x - station.x, node.y - station.y) > self.instance.radius(self.types[key[0]]) + EPS:
            return None
        fly = self._travel[d["node"], tid]
        back = self._travel[tid, station.id]
        energy = d["energy"] + self.params.flight_energy * fly + node.energy
        duty = d["duty"] + fly + node.service
        if (not math.isfinite(fly + back) or energy + self.params.flight_energy * back > d["capacity"] + ENERGY_EPS
                or duty + back > d["limit"] + EPS):
            return None
        return dict(d, node=tid, energy=energy, duty=duty, returned=False)

    def _return_state(self, key, d=None):
        d = self.slots[key] if d is None else d
        if d["returned"]:
            return None
        back = self._travel[d["node"], self._home(key)]
        if (not math.isfinite(back) or d["energy"] + self.params.flight_energy * back > d["capacity"] + ENERGY_EPS
                or d["duty"] + back > d["limit"] + EPS):
            return None
        return dict(d, node=self._home(key), energy=0.0, duty=d["duty"] + back, returned=True)

    def _opportunity(self, key, tid, state=None):
        """Best singleton finish now or after an explicit same-slot return.

        This necessary condition never executes a return or appends a target.
        It protects LD-only tasks and cumulative duty across future batteries.
        """
        d = self.slots[key] if state is None else state
        direct = self._target_state(key, tid, d)
        closed = self._return_state(key, d)
        fresh = self._target_state(key, tid, closed) if closed is not None else None
        vals = [self._closed_duty(key, q) for q in (direct, fresh) if q is not None]
        return min(vals) if vals else math.inf

    def _raw_options(self):
        remain = sorted(self.remaining)
        opportunities = {tid: {key: self._opportunity(key, tid)
                              for key in self.slots if key[0] == self.assignment[tid]}
                         for tid in remain}
        # A target with no singleton opportunity cannot be reached by a longer
        # path with extra positive service/energy under this directed metric.
        if any(not any(math.isfinite(v) for v in by_slot.values()) for by_slot in opportunities.values()):
            return []
        old_closed = {key: self._closed_duty(key) for key in self.slots}
        old_m = max(old_closed.values(), default=0.0)
        choices = []
        for key, d in self.slots.items():
            candidates = [(tid, self._target_state(key, tid)) for tid in remain
                          if self.assignment[tid] == key[0]]
            candidates.append((RETURN, self._return_state(key)))
            for tid, state in candidates:
                if state is None:
                    continue
                todo = [t for t in remain if t != tid]
                # Only this slot changes. Every other potential opportunity is
                # identical before/after this physical action.
                exclusive = [t for t in todo if not any(math.isfinite(v)
                             for k, v in opportunities[t].items() if k != key)]
                if any(not math.isfinite(self._opportunity(key, t, state)) for t in exclusive):
                    continue
                closed_duty = self._closed_duty(key, state)
                total_closed = sum(old_closed.values()) - old_closed[key] + closed_duty
                closed_cost = self.fixed + self.params.time_cost * total_closed
                cost_bound = closed_cost + self.params.time_cost * sum(self.targets[t].service for t in todo)
                if not math.isfinite(cost_bound) or cost_bound > self.cap + EPS:
                    continue
                after_m = max([closed_duty] + [v for k, v in old_closed.items() if k != key])
                others = [v for k, v in opportunities.get(tid, {}).items()
                          if k != key and math.isfinite(v)]
                node = self.instance.nodes[d["node"]]
                target = self.targets[tid] if tid != RETURN else self.instance.stations[key[0]]
                station = self.instance.stations[key[0]]
                radius = self.instance.radius(self.types[key[0]])
                fly = self._travel[d["node"], target.id]
                back = self._travel[target.id, station.id]
                e_closed = (d["energy"] + self.params.flight_energy * fly +
                            (target.energy if tid != RETURN else 0.0) + self.params.flight_energy * back)
                sibling = [v for k, v in old_closed.items() if k[0] == key[0] and k != key]
                n = max(1, len(self.targets))
                feat = [float(tid == RETURN), float(key[1] == 0), float(self.types[key[0]] == 2),
                    float(d["returned"]), (target.x-node.x)/radius, (target.y-node.y)/radius,
                    (target.x-station.x)/radius, (target.y-station.y)/radius,
                    (target.energy if tid != RETURN else 0.0)/d["capacity"],
                    (target.service if tid != RETURN else 0.0)/d["limit"],
                    fly/d["limit"], back/d["limit"], d["energy"]/d["capacity"],
                    e_closed/d["capacity"], (d["capacity"]-e_closed)/d["capacity"],
                    d["duty"]/d["limit"], closed_duty/d["limit"],
                    (d["limit"]-closed_duty)/d["limit"], old_closed[key]/600.0,
                    after_m/600.0, (after_m-old_m)/600.0, closed_cost/self.cap, cost_bound/self.cap,
                    sum(self.assignment[t] == key[0] for t in todo)/n, len(todo)/n,
                    len(others)/max(1, len(self.slots)-1), min(others, default=closed_duty)/600.0,
                    float(tid != RETURN and not others), len(exclusive)/n,
                    (closed_duty-max(sibling, default=old_closed[key]))/600.0]
                if len(feat) != FEAT_DIM or not all(math.isfinite(v) for v in feat):
                    raise RuntimeError("invalid joint feature contract")
                choices.append(((key[0], key[1], tid), feat))
        return choices

    def _refresh(self):
        if not self.remaining and all(d["returned"] for d in self.slots.values()):
            self.done, self.termination_reason, self._cache = True, "complete", []
        else:
            self._cache = self._raw_options()
            if not self._cache:
                self.done, self.termination_reason = True, "dead_end"

    def options(self):
        """All legal joint actions and fixed-length public feature vectors."""
        return [(action, list(feat)) for action, feat in self._cache]

    def step(self, action):
        if self.done:
            raise ValueError("joint episode has already ended")
        if (not isinstance(action, (tuple, list)) or len(action) != 3
                or any(type(x) is not int for x in action)):
            raise ValueError("action must contain three integer indices")
        action = tuple(action)
        if action not in {a for a, _ in self._cache}:
            raise ValueError("masked physical action")
        si, di, tid = action
        key, d = (si, di), self.slots[si, di]
        if tid == RETURN:
            state = self._return_state(key)
            self.routes[si][di].append(list(d["trip"]))
            state["trip"] = []
        else:
            state = self._target_state(key, tid)
            state["trip"] = list(d["trip"]) + [tid]
            self.remaining.remove(tid)
        self.slots[key] = state
        self.trace.append(action)
        if len(self.trace) > self.max_steps:
            raise RuntimeError("non-progressing joint route construction")
        self._refresh()
        return self.done

    def _subset_options(self, options):
        if options is None:
            return self.options()
        allowed = {a for a, _ in options}
        if not allowed <= {a for a, _ in self._cache}:
            raise ValueError("option subset contains masked actions")
        return [(a, list(f)) for a, f in self._cache if a in allowed]

    def teacher_action(self, options=None):
        """Strict same-wind author replay; deviation never triggers a repair."""
        if self.done:
            return None
        if options is not None:
            allowed = {a for a, _ in self._subset_options(options)}
            # A serial scheduler may interleave slots differently while each
            # slot still follows its exact original TARGET/RETURN sequence.
            for key in self.slots:
                local_trace = [a for a in self.trace if a[:2] == key]
                local_teacher = [a for a in self._teacher if a[:2] == key]
                if local_trace != local_teacher[:len(local_trace)]:
                    raise ValueError("teacher replay requested after a non-teacher action")
                if len(local_trace) < len(local_teacher) and local_teacher[len(local_trace)] in allowed:
                    return local_teacher[len(local_trace)]
            return None
        if self.trace != self._teacher[:len(self.trace)]:
            raise ValueError("teacher replay requested after a non-teacher action")
        action = self._teacher[len(self.trace)]
        if action not in {a for a, _ in self._cache}:
            raise ValueError("same-wind teacher violates current mask or original cap")
        return action

    @staticmethod
    def _greedy_key(option):
        """Joint load, alternate-slot finish and heterogeneous reserve comparison."""
        action, f = option
        if f[0]:
            # Real returns compete across slots but cost one explicit action.
            score = f[19] + .03 + .10*f[10]
        else:
            limit = 600.0 if f[2] else 480.0
            alternative_regret = max(0.0, f[16]*limit - f[26]*600.0) / 600.0
            score = (f[19] + .20*f[20] + .05*f[21] + .10*alternative_regret
                     + .03*f[28] - .02*f[27] + .05*max(0.0, f[29]))
        return score, action

    def greedy_action(self, options=None):
        """Deterministic non-learning policy, using exactly options' information."""
        choices = self._subset_options(options)
        return min(choices, key=self._greedy_key)[0] if choices else None

    def source_slot_action(self, options=None):
        """Legal heuristic constrained to the original author's target slots.

        This is a separately labelled reference, not the joint heuristic. It may
        dead-end under the added restriction; None never invokes a fallback.
        """
        choices = [(a, f) for a, f in self._subset_options(options)
                   if a[2] == RETURN or self.source_slot[a[2]] == a[:2]]
        return min(choices, key=self._greedy_key)[0] if choices else None

    def result(self):
        """Audit the complete typed plan; retain every unfinished/open prefix."""
        solution = dict(schema_version=1, instance=self.instance.name,
            instance_sha256=self.instance.sha256, station_types=list(self.types), routes=deepcopy(self.routes))
        open_trips = []
        for key, d in self.slots.items():
            if d["trip"]:
                solution["routes"][key[0]][key[1]].append(list(d["trip"]))
                open_trips.append(dict(station=key[0], slot=key[1], targets=list(d["trip"])))
        audit = audit_fixed_anchor(self.instance, solution, wind=self.scenario, map_path=self.path)
        all_returned = all(d["returned"] for d in self.slots.values())
        failed = sum(d["duty"] > d["limit"] + EPS or d["energy"] > d["capacity"] + ENERGY_EPS
                     for d in self.slots.values())
        cost = self.fixed + self.params.time_cost * sum(d["duty"] for d in self.slots.values())
        physical = bool(all_returned and not failed and audit["physical_feasible"])
        strict = bool(self.done and not self.remaining and physical)
        eligible = bool(strict and cost <= self.cap + EPS and not self.fallback)
        m_return = max((d["duty"] for d in self.slots.values()), default=0.0) if all_returned else None
        if strict and (abs(cost - audit["metrics"]["cost"]) > EPS
                       or abs(m_return - audit["metrics"]["M_return"]) > EPS):
            raise RuntimeError("joint simulator and independent audit disagree")
        return dict(cost=cost, J=cost+1000.0*len(self.remaining)+1000.0*failed,
            M_return=m_return, complete_strict=int(strict), all_returned=int(all_returned),
            physically_feasible=int(physical), eligible=eligible, fallback=False,
            solution=solution, audit=audit, open_trips=open_trips, unserved=len(self.remaining),
            failed=failed, routine_total=len(self.targets), routine_done=len(self.targets)-len(self.remaining),
            fixed=self.fixed, n_open=sum(k != 0 for k in self.types),
            n_dabs=sum(k == 2 for k in self.types), n_drones=len(self.slots),
            n_dec=len(self.trace), done=self.done, termination_reason=self.termination_reason,
            scientific_eligible=False, formal=False, feature_schema=FEATURE_SCHEMA)
