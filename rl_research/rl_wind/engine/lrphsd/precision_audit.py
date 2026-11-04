"""Independent 50-digit witness audit of the official-data physical contract.

This is neither the authors' unavailable MILP nor an optimality certificate.
It does not import the solver, its parser, distance cache, or evaluator.
"""
from collections import Counter
from decimal import Decimal, localcontext
from pathlib import Path
import hashlib
import json

D = Decimal
CONTRACT = {
    'speed': '900', 'flight_energy': '0.018',
    'small_battery': '0.81', 'large_battery': '1',
    'small_radius': '4000', 'large_radius': '5000',
    'small_duration': '480', 'large_duration': '600',
    'small_station_cost': '22.8', 'large_station_cost': '30.4',
    'small_drone_cost': '5', 'large_drone_cost': '8', 'time_cost': '0.5',
}


def audit_witness(instance_path, solution, parameter_overrides=None):
    with localcontext() as context:
        context.prec = 50
        return _audit(instance_path, solution, parameter_overrides)


def _audit(instance_path, solution, parameter_overrides):
    parameters = dict(CONTRACT)
    if parameter_overrides:
        if set(parameter_overrides) - set(parameters):
            raise ValueError('unknown parameter')
        parameters.update(parameter_overrides)
    p = {key: D(str(value)) for key, value in parameters.items()}
    if not all(value.is_finite() and value > 0 for value in p.values()):
        raise ValueError('physical parameters must be finite and positive')
    raw = Path(instance_path).read_bytes()
    lines = raw.decode('utf-8-sig').splitlines()
    if not lines or 'CUST_NO' not in lines[0]:
        raise ValueError('official header required')
    nodes, targets, stations = {}, [], []
    for line in lines[1:]:
        if not line.strip():
            continue
        values = line.split()
        if len(values) != 5:
            raise ValueError('five input columns required')
        number = D(values[0])
        data = tuple(D(value) for value in values[1:])
        if not all(value.is_finite() for value in (number,) + data):
            raise ValueError('nonfinite input')
        if number != number.to_integral_value() or min(data[2:]) < 0:
            raise ValueError('invalid ID or service quantity')
        nid = int(number)
        if nid in nodes:
            raise ValueError('duplicate input ID')
        nodes[nid] = data
        (targets if data[2] > 0 else stations).append(nid)
        if data[2] == 0 and data[3] != 0:
            raise ValueError('station service is not zero')
    if not targets or not stations:
        raise ValueError('targets and stations required')

    def distance(a, b):
        ax, ay, *_ = nodes[a]
        bx, by, *_ = nodes[b]
        return ((ax-bx)**2 + (ay-by)**2).sqrt()

    digest = hashlib.sha256(raw).hexdigest()
    issues = []
    if solution.get('instance_sha256') != digest:
        issues.append('instance_hash')
    kinds, routes = solution.get('station_types'), solution.get('routes')
    if not isinstance(kinds, list) or not isinstance(routes, list) or len(kinds) != len(stations) or len(routes) != len(stations):
        raise ValueError('station dimensions')
    counts = Counter()
    fixed, total_time = D(0), D(0)
    trips_out, drones_out, unused = [], [], []
    for si, (station, kind, drones) in enumerate(zip(stations, kinds, routes)):
        if type(kind) is not int or kind not in (0, 1, 2):
            raise ValueError('station type')
        if not isinstance(drones, list) or len(drones) != 2:
            raise ValueError('drone dimensions')
        if kind == 1:
            fixed += p['small_station_cost'] + p['small_drone_cost']
        elif kind == 2:
            fixed += p['large_station_cost'] + p['small_drone_cost'] + p['large_drone_cost']
        radius = p['small_radius'] if kind == 1 else p['large_radius']
        limit = p['small_duration'] if kind == 1 else p['large_duration']
        for di, trips in enumerate(drones):
            if not isinstance(trips, list):
                raise ValueError('trip dimensions')
            capacity = p['large_battery'] if di == 0 else p['small_battery']
            drone_time, trip_count = D(0), 0
            for ti, trip in enumerate(trips):
                if not isinstance(trip, list):
                    raise ValueError('trip format')
                if not trip:
                    continue
                if any(type(nid) is not int or nid not in targets for nid in trip):
                    raise ValueError('non-target in trip')
                if kind == 0:
                    issues.append('closed_station')
                if kind == 1 and di == 0:
                    issues.append('large_drone_at_SABS')
                trip_count += 1
                counts.update(trip)
                seq = [station] + trip + [station]
                length = sum((distance(a, b) for a, b in zip(seq, seq[1:])), D(0))
                travel = length / p['speed']
                service_time = sum((nodes[nid][3] for nid in trip), D(0))
                service_energy = sum((nodes[nid][2] for nid in trip), D(0))
                energy = service_energy + travel * p['flight_energy']
                energy_slack = capacity - energy
                coverage_slack = min(radius-distance(station, nid) for nid in trip)
                if energy_slack < 0:
                    issues.append('energy')
                if coverage_slack < 0:
                    issues.append('coverage')
                time = travel + service_time
                drone_time += time
                trips_out.append({
                    'station_id': station, 'drone': 'LD' if di == 0 else 'SD',
                    'trip': ti, 'targets': list(trip), 'length_m': str(length),
                    'travel_minutes': str(travel), 'service_minutes': str(service_time),
                    'energy': str(energy), 'energy_slack': str(energy_slack),
                    'minimum_coverage_slack_m': str(coverage_slack),
                    'flight_rate_break_even': str((capacity-service_energy)/travel),
                })
            if drone_time > limit:
                issues.append('cumulative_time')
            if kind == 2 and trip_count == 0:
                unused.append({'station_id': station, 'drone': 'LD' if di == 0 else 'SD'})
            drones_out.append({'station_id': station, 'drone': 'LD' if di == 0 else 'SD',
                               'trips': trip_count, 'time_minutes': str(drone_time),
                               'time_slack': str(limit-drone_time)})
            total_time += drone_time
    if any(counts[nid] != 1 for nid in targets):
        issues.append('visit_exactly_once')
    objective = fixed + p['time_cost'] * total_time
    service_values = {nodes[nid][3] for nid in targets}
    literal_extra = (p['time_cost'] * next(iter(service_values)) * len(trips_out)) if len(service_values) == 1 else None
    return {
        'profile': 'official_data_zero_station_service_physical_contract',
        'arithmetic': 'Decimal precision=50, no feasibility epsilon',
        'instance_sha256': digest, 'feasible': not issues, 'issues': sorted(set(issues)),
        'parameters': {key: str(value) for key, value in p.items()},
        'objective': str(objective), 'fixed_cost': str(fixed),
        'operating_minutes': str(total_time), 'target_count': len(targets),
        'trip_count': len(trips_out), 'trips': trips_out, 'drones': drones_out,
        'unused_configured_DABS_drones': unused,
        'require_both_DABS_active': not unused,
        'literal_uniform_service_on_return_extra_cost': str(literal_extra) if literal_extra is not None else None,
        'literal_uniform_service_on_return_objective': str(objective+literal_extra) if literal_extra is not None else None,
        'original_author_MILP_verified': False,
    }
