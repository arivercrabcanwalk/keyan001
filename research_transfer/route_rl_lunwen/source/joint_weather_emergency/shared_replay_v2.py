"""Minimal auditable, uniform exogenous-wind execution contract.
Units metres/minutes and original energy units; constant power in flight.
Terminal failures stop the entire drone, no recovery/relaunch is invented.
Duty limits retain original station-kind semantics and are report-only violations.
This independent replay is a candidate environment, not calibrated aircraft evidence.
"""
from dataclasses import dataclass
from collections import Counter
import math
from reference_environment import ground_speed


def _finite(value, name, minimum=0., positive=False):
    if type(value) not in (int, float) or not math.isfinite(value):
        raise ValueError(name + '_FINITE_NUMBER_REQUIRED')
    if (positive and value <= minimum) or (not positive and value < minimum):
        raise ValueError(name + '_DOMAIN')


def _node(node):
    for name in ('x', 'y'):
        value = getattr(node, name)
        if type(value) not in (int, float) or not math.isfinite(value):
            raise ValueError('NODE_COORDINATE')
    for name in ('energy', 'service'):
        _finite(getattr(node, name), 'NODE_' + name.upper())


@dataclass(frozen=True)
class Trace:
    # Each row gives exclusive end time, wind x and wind y in m/min.
    intervals: tuple
    scenario_id: str = 'fixture'

    def __post_init__(self):
        if not isinstance(self.intervals, (tuple, list)):
            raise ValueError('TRACE_SHAPE')
        rows = []
        for row in self.intervals:
            if not isinstance(row, (tuple, list)) or len(row) != 3:
                raise ValueError('TRACE_SHAPE')
            if any(type(value) not in (int, float) for value in row):
                raise ValueError('TRACE_VALUES')
            rows.append(tuple(float(value) for value in row))
        rows = tuple(rows)
        if not rows:
            raise ValueError('TRACE_SHAPE')
        prev = 0.
        for index, (end, wx, wy) in enumerate(rows):
            if math.isnan(end) or end <= prev or not math.isfinite(wx) or not math.isfinite(wy):
                raise ValueError('TRACE_VALUES')
            if math.isinf(end) and index != len(rows) - 1:
                raise ValueError('TRACE_VALUES')
            prev = end
        object.__setattr__(self, 'intervals', rows)

    def current(self, t):
        if t < 0 or not math.isfinite(t):
            raise ValueError('TIME_INVALID')
        for end, wx, wy in self.intervals:
            if t < end:
                return end, wx, wy
        raise ValueError('HORIZON_EXCEEDED')


def observation(t, position, served_ids, forecast=()):
    """Ordinary observations contain supplied causal values only, never Trace/future arrays."""
    _finite(t, 'TIME')
    if len(position) != 2 or not all(isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v) for v in position):
        raise ValueError('POSITION')
    if not all(isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v) for v in forecast):
        raise ValueError('FORECAST')
    return dict(time=float(t), position=tuple(position), served_ids=tuple(served_ids), forecast=tuple(forecast))


def flight(u, v, start, remaining_energy, power, speed, trace):
    # Validate before the zero-distance shortcut. Invalid physics is not a no-op.
    _node(u); _node(v)
    _finite(start, 'TIME'); _finite(remaining_energy, 'ENERGY')
    _finite(power, 'POWER'); _finite(speed, 'SPEED', positive=True)
    if not isinstance(trace, Trace):
        raise ValueError('TRACE_TYPE')
    dx, dy = v.x-u.x, v.y-u.y
    distance = math.hypot(dx,dy)
    if not math.isfinite(distance):
        raise ValueError('LEG_DISTANCE_OVERFLOW')
    if distance == 0:
        return dict(end=start, energy=0., failed=None, position=(v.x,v.y))
    progress, t, energy = 0., start, 0.
    while progress < distance:
        try:
            end, wx, wy = trace.current(t)
            vg = ground_speed(dx,dy,wx,wy,speed)
            _finite(vg, 'GROUND_SPEED', positive=True)
        except ValueError as exc:
            fraction = progress/distance
            return dict(end=t, energy=energy, failed=str(exc), position=(u.x+dx*fraction,u.y+dy*fraction))
        needed = (distance-progress)/vg
        duration = min(needed,end-t)
        available = max(0.,remaining_energy-energy)
        if power > 0 and duration*power > available + 1e-12:
            duration = available/power
            progress += duration*vg; t += duration; energy += available
            _finite(t, 'EXECUTION_TIME'); _finite(energy, 'EXECUTION_ENERGY')
            fraction = min(1.,progress/distance)
            return dict(end=t, energy=energy, failed='FLIGHT_ENERGY', position=(u.x+dx*fraction,u.y+dy*fraction))
        progress += duration*vg; t += duration; energy += duration*power
        _finite(t, 'EXECUTION_TIME'); _finite(energy, 'EXECUTION_ENERGY')
        # The exact arrival event is not a further wind query.
        if duration == needed:
            return dict(end=t, energy=energy, failed=None, position=(v.x,v.y))
    return dict(end=t, energy=energy, failed=None, position=(v.x,v.y))


def replay(ins, sol, trace):
    p = ins.params; served = []; drones = []; issues = []; fixed = 0.; counts = Counter()
    if not isinstance(trace, Trace):
        raise ValueError('TRACE_TYPE')
    _finite(p.speed, 'SPEED', positive=True)
    _finite(p.flight_energy, 'POWER'); _finite(p.time_cost, 'TIME_COST')
    for node in ins.nodes.values():
        _node(node)
    for station in ins.stations:
        _node(station)
    if len(set(ins.target_ids)) != len(ins.target_ids) or any(type(n) is not int or n not in ins.nodes for n in ins.target_ids):
        raise ValueError('TARGET_IDENTITIES')
    for di in (0,1):
        _finite(ins.capacity(di), 'CAPACITY', positive=True)
    for kind in (0,1,2):
        _finite(ins.fixed(kind), 'FIXED_COST')
        if kind:
            _finite(ins.radius(kind), 'RADIUS', positive=True)
            _finite(ins.duration(kind), 'DUTY_LIMIT', positive=True)
    if len(sol['station_types']) != len(ins.stations) or len(sol['routes']) != len(ins.stations):
        raise ValueError('STATION_DIMENSION')
    for si,(station,kind,routes) in enumerate(zip(ins.stations,sol['station_types'],sol['routes'])):
        if type(kind) is not int or kind not in (0,1,2) or len(routes)!=2:
            raise ValueError('STRUCTURE')
        fixed += ins.fixed(kind)
        for di,trips in enumerate(routes):
            t=0.; position=(station.x,station.y); failure=None; flown=0; completed=0
            for trip in trips:
                for nid in trip:
                    if type(nid) is not int or nid not in ins.target_ids:
                        raise ValueError('NON_TARGET')
                    counts[nid] += 1
                    node=ins.nodes[nid]
                    if math.hypot(node.x-station.x,node.y-station.y)>ins.radius(kind)+1e-7:
                        issues.append('coverage')
                if trip and (kind==0 or (kind==1 and di==0)):
                    issues.append('drone_qualification')
            if failure is None:
                for trip in trips:
                    if not trip: continue
                    if failure: break
                    flown += 1; energy=0.; prev=station
                    for node in [ins.nodes[n] for n in trip]+[station]:
                        result=flight(prev,node,t,ins.capacity(di)-energy,p.flight_energy,p.speed,trace)
                        t=result['end']; energy+=result['energy']; position=result['position']; failure=result['failed']
                        if failure: break
                        if node is not station:
                            remaining=max(0.,ins.capacity(di)-energy)
                            if node.energy > remaining + 1e-12:
                                fraction=remaining/node.energy
                                t += node.service*fraction; energy += remaining
                                _finite(t, 'EXECUTION_TIME'); _finite(energy, 'EXECUTION_ENERGY')
                                failure='SERVICE_ENERGY'; break
                            energy+=node.energy; t+=node.service; served.append(node.id)
                            _finite(t, 'EXECUTION_TIME'); _finite(energy, 'EXECUTION_ENERGY')
                        prev=node
                    if not failure: completed+=1
            limit=ins.duration(kind) if kind else 0.
            drones.append(dict(station=si,drone=di,end_time=t,position=position,terminal_failure=failure,
                               active=any(bool(tr) for tr in trips),never_launched=flown==0,
                               flown_trips=flown,completed_trips=completed,duty=t,duty_limit=limit,overtime=max(0.,t-limit),
                               returned=failure is None))
    if any(counts[n]!=1 for n in ins.target_ids): issues.append('planned_exactly_once')
    delivered_counts=Counter(served)
    if any(v>1 for v in delivered_counts.values()): issues.append('duplicate_service')
    missing=tuple(n for n in ins.target_ids if delivered_counts[n]==0)
    failure_count=sum(d['terminal_failure'] is not None for d in drones)
    complete=not missing and not failure_count and not issues
    duty_violation=any(d['overtime']>1e-7 for d in drones)
    return dict(scenario_id=trace.scenario_id,served_ids=tuple(served),undelivered_ids=missing,
                undelivered=len(missing),failed_drones=failure_count,drones=drones,issues=issues,
                all_work_returned=complete,feasible=complete and not duty_violation,
                complete_return_makespan=max((d['end_time'] for d in drones),default=0.) if complete else None,
                last_observed_time=max((d['end_time'] for d in drones),default=0.),
                incurred_cost=fixed+sum(d['duty'] for d in drones)*p.time_cost,
                duty_contract='original_station_kind_limit_report_only_no_reset',
                comparison_contract='incurred_cost_is_not_successful_completion_score')
