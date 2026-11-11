"""Round-5 exact-semantics fast candidate engine.

Every retained expression keeps the operand order and association of
``fidelity_ops_v4``.  Precomputed tables store exactly the doubles the
reference recomputes (``dist/speed`` and ``(dist/speed)*flight_energy``), so
results are bit-identical.  What changes is only *how often* the interpreter
walks the same arithmetic: redundant recomputation, per-call cache-key
construction and temporary list allocation are removed.

The route cache of round 4 is not used here: insertion candidates are unique
routes, so a memo keyed by route content was pure overhead on the hot path.
Cached values are still exact because the underlying functions are pure.
"""
import math

DIST = DT = DE = SVC = ENGE = STID = CAP = LIM = RAD = None
SPEED = 0.0
FE = 0.0
RUNTIME = None
NTIME = 0
NENERGY = 0


def prepare(ins):
    """Build immutable per-instance tables once per solve."""
    global DIST, DT, DE, SVC, ENGE, STID, CAP, LIM, RAD, SPEED, FE, NTIME, NENERGY
    p = ins.params
    SPEED = p.speed
    FE = p.flight_energy
    NTIME = 0
    NENERGY = 0
    nodes = ins.nodes
    DIST = {(a.id, b.id): math.sqrt((a.x - b.x) ** 2 + (a.y - b.y) ** 2)
            for a in nodes.values() for b in nodes.values()}
    DT = {k: v / SPEED for k, v in DIST.items()}
    DE = {k: (v / SPEED) * FE for k, v in DIST.items()}
    SVC = {k: v.service for k, v in nodes.items()}
    ENGE = {k: v.energy for k, v in nodes.items()}
    STID = [s.id for s in ins.stations]
    small = p.small_battery
    CAP = {0: (small, small), 1: (small, small), 2: (p.large_battery, small)}
    LIM = {0: p.large_duration, 1: p.small_duration, 2: p.large_duration}
    RAD = {0: p.large_radius, 1: p.small_radius, 2: p.large_radius}
    ins.dist = DIST
    return DIST


def clone(sol):
    return {**sol, 'station_types': sol['station_types'].copy(),
            'routes': [[[trip.copy() for trip in drone] for drone in station]
                       for station in sol['routes']]}


def source_distances(ins):
    return {(a.id, b.id): math.sqrt((a.x - b.x) ** 2 + (a.y - b.y) ** 2)
            for a in ins.nodes.values() for b in ins.nodes.values()}


def physical(sol):
    out = {**sol, 'routes': [[[list(t) for t in drone] for drone in station]
                             for station in sol['routes']]}
    for si, kind in enumerate(out['station_types']):
        if kind == 1:
            out['routes'][si][1] = out['routes'][si][0] + out['routes'][si][1]
            out['routes'][si][0] = []
    out.pop('_storage_profile', None)
    return out


def _path_time(ins, si, trip):
    global NTIME
    NTIME += 1
    n = len(trip)
    if not n:
        return 0.0
    dt = DT
    svc = SVC
    depot = STID[si]
    prev = trip[0]
    value = dt[depot, prev]
    for i in range(1, n):
        cur = trip[i]
        value += dt[prev, cur]
        value += svc[prev]
        prev = cur
    value += dt[prev, depot]
    value += svc[prev]
    return value


def _path_energy(ins, si, trip, segment=False):
    global NENERGY
    NENERGY += 1
    n = len(trip)
    depot = STID[si]
    if not segment:
        dist = DIST
        total = 0.0
        prev = depot
        for x in trip:
            total += dist[prev, x]
            prev = x
        total += dist[prev, depot]
        extra = 0.0
        enge = ENGE
        for x in trip:
            extra += enge[x]
        return total / SPEED * FE + extra
    if not n:
        return 0.0
    de = DE
    enge = ENGE
    prev = trip[0]
    value = de[depot, prev]
    for i in range(1, n):
        cur = trip[i]
        value += de[prev, cur]
        value += enge[prev]
        prev = cur
    value += de[prev, depot]
    value += enge[prev]
    return value


def path_time(ins, si, trip):
    return _path_time(ins, si, trip)


def path_energy(ins, si, trip, segment=False):
    return _path_energy(ins, si, trip, segment)


def capacity(ins, kind, di):
    return CAP[kind][di]


def raw_valid(ins, sol, time_check=True):
    runtime = RUNTIME
    if runtime is not None:
        counts = runtime.counts
        counts["source_energy_query_api_requests"] += 1
        counts["source_time_query_api_requests"] += bool(time_check)
    cap = CAP
    lim = LIM
    routes = sol['routes']
    for si, kind in enumerate(sol['station_types']):
        station = routes[si]
        if kind:
            c = cap[kind]
            for di, trips in enumerate(station):
                cc = c[di]
                for t in trips:
                    if _path_energy(ins, si, t) > cc:
                        return False
        if time_check:
            limit = lim[kind]
            for di, trips in enumerate(station):
                total = 0.0
                for t in trips:
                    total += _path_time(ins, si, t)
                if total > limit:
                    return False
    return True


def different_indices(rng, length):
    a = rng.randrange(length)
    b = rng.randrange(length)
    while b == a:
        b = rng.randrange(length)
    return a, b


def location(types, rng, which=None):
    result = types.copy()
    which = rng.randrange(4) if which is None else which
    if which == 0:
        if len(types) < 2:
            return result
        a, b = different_indices(rng, len(types))
        result[a], result[b] = result[b], result[a]
    else:
        choices = [i for i, k in enumerate(types) if (k < 2 if which == 1 else k > 0)]
        if choices:
            i = rng.choice(choices)
            result[i] = result[i] + 1 if which == 1 else result[i] - 1 if which == 2 else 0
    return result


def local_candidate(ins, sol, which, rng):
    candidate = clone(sol)
    routes = candidate['routes']
    types = sol['station_types']
    if which == 4:
        dist = DIST
        for si, station in enumerate(routes):
            depot = STID[si]
            for drone in station:
                for trip in drone:
                    improved = True
                    while improved:
                        improved = False
                        for a in range(len(trip) - 1):
                            for b in range(a + 1, len(trip)):
                                before = depot if a == 0 else trip[a - 1]
                                after = depot if b + 1 == len(trip) else trip[b + 1]
                                current = dist[before, trip[a]] + dist[trip[b], after]
                                proposed = dist[before, trip[b]] + dist[trip[a], after]
                                if proposed < current:
                                    trip[a:b + 1] = reversed(trip[a:b + 1])
                                    improved = True
        return candidate
    if which == 0:
        stations = [i for i, k in enumerate(types) if k]
        if not stations:
            return sol
        si = rng.choice(stations)
        drones = [i for i, trips in enumerate(routes[si]) if trips]
        if not drones:
            return sol
        di = rng.choice(drones)
        trips = [i for i, t in enumerate(routes[si][di]) if len(t) > 1]
        if not trips:
            return sol
        ti = rng.choice(trips)
        trip = routes[si][di][ti]
        a, b = different_indices(rng, len(trip))
        trip[a], trip[b] = trip[b], trip[a]
    elif which == 1:
        si = rng.randrange(len(routes))
        if not any(routes[si]):
            return candidate
        di = rng.randrange(len(routes[si]))
        trips = routes[si][di]
        if len(trips) < 2:
            return candidate
        a, b = different_indices(rng, len(trips))
        if not trips[a] or not trips[b]:
            return candidate
        pa = rng.randrange(len(trips[a]))
        pb = rng.randrange(len(trips[b]))
        trips[a][pa], trips[b][pb] = trips[b][pb], trips[a][pa]
    elif which == 2:
        stations = [i for i, k in enumerate(types) if k == 2]
        if not stations:
            return sol
        si = rng.choice(stations)
        large, small = routes[si]
        if not large or not small:
            return sol
        a = rng.randrange(len(large))
        b = rng.randrange(len(small))
        if not large[a] or not small[b]:
            return sol
        pa = rng.randrange(len(large[a]))
        pb = rng.randrange(len(small[b]))
        large[a][pa], small[b][pb] = small[b][pb], large[a][pa]
    else:
        stations = [i for i, k in enumerate(types) if k]
        if len(stations) < 2:
            return sol
        a, b = different_indices(rng, len(stations))
        sa, sb = stations[a], stations[b]
        if not any(routes[sa]) or not any(routes[sb]):
            return sol
        da = rng.randrange(len(routes[sa]))
        db = rng.randrange(len(routes[sb]))
        ta, tb = routes[sa][da], routes[sb][db]
        if not ta or not tb:
            return sol
        a = rng.randrange(len(ta))
        b = rng.randrange(len(tb))
        if not ta[a] or not tb[b]:
            return sol
        pa = rng.randrange(len(ta[a]))
        pb = rng.randrange(len(tb[b]))
        ta[a][pa], tb[b][pb] = tb[b][pb], ta[a][pa]
    return candidate if raw_valid(ins, candidate, time_check=which >= 2) else sol


def positions(sol):
    return [(si, di, ti, pi, n)
            for si, station in enumerate(sol['routes'])
            for di, trips in enumerate(station)
            for ti, trip in enumerate(trips)
            for pi, n in enumerate(trip)]


def target_set(sol):
    return {n for station in sol['routes'] for drone in station for trip in drone for n in trip}


def destroy_candidate(ins, sol, which, rng):
    candidate = clone(sol)
    routes = candidate['routes']
    types = sol['station_types']
    counts = {(si, di): sum(map(len, trips)) for si, s in enumerate(routes) for di, trips in enumerate(s)}
    entries = [e for e in positions(candidate) if types[e[0]] and counts[e[0], e[1]] > 1]
    if which == 2:
        if not entries:
            return sol
        si, di, ti, pi, _ = rng.choice(entries)
        routes[si][di][ti].pop(pi)
        return candidate if raw_valid(ins, candidate) else sol
    time_cost = ins.params.time_cost
    if which == 0:
        best = None
        gain = -math.inf
        for si, di, ti, pi, nid in entries:
            trip = routes[si][di][ti]
            old = _path_time(ins, si, trip)
            trip.pop(pi)
            new = _path_time(ins, si, trip)
            saving = (old - new) * time_cost
            ok = False
            if saving > gain:
                ok = _path_energy(ins, si, trip, True) < CAP[types[si]][di]
            trip.insert(pi, nid)
            if saving > gain and ok:
                gain = saving
                best = (si, di, ti, pi)
        if best:
            si, di, ti, pi = best
            if len(routes[si][di][ti]) > 1:
                routes[si][di][ti].pop(pi)
        return candidate if raw_valid(ins, candidate) else sol
    if which == 1:
        for si, s in enumerate(routes):
            depot = STID[si]
            for di, trips in enumerate(s):
                remaining = counts[si, di]
                for trip in trips:
                    options = []
                    for pi, nid in enumerate(trip):
                        if remaining == 1:
                            continue
                        a = depot if pi == 0 else trip[pi - 1]
                        b = depot if pi + 1 == len(trip) else trip[pi + 1]
                        saving = DIST[a, nid] + DIST[nid, b] - DIST[a, b]
                        if saving > 0:
                            options.append((saving, pi))
                    options.sort(key=lambda x: -x[0])
                    for _, pi in options:
                        if rng.random() <= 0.7 and remaining > 1:
                            trip.pop(pi)
                            remaining -= 1
                            break
        return candidate
    candidates = []
    scores = []
    cover = {}
    for si, di, ti, pi, nid in entries:
        trip = routes[si][di][ti]
        if len(trip) < 2:
            continue
        score = 0.0
        cover_a = cover.get(nid)
        if cover_a is None:
            cover_a = any(k and DIST[STID[j], nid] <= RAD[k] for j, k in enumerate(types))
            cover[nid] = cover_a
        for other in trip:
            if other == nid:
                continue
            cover_b = cover.get(other)
            if cover_b is None:
                cover_b = any(k and DIST[STID[j], other] <= RAD[k] for j, k in enumerate(types))
                cover[other] = cover_b
            weight = .8 if cover_a and cover_b else .5 if cover_a or cover_b else .2
            score += weight / max(DIST[nid, other], 1e-6)
        if score > 0:
            candidates.append((si, di, ti, pi))
            scores.append(score)
    if not candidates:
        return sol
    low, high = min(scores), max(scores)
    weights = [(1.0 if abs(high - low) < 1e-9 else (x - low) / (high - low)) + 1e-6 for x in scores]
    si, di, ti, pi = rng.choices(candidates, weights=weights, k=1)[0]
    routes[si][di][ti].pop(pi)
    return candidate


def covered_drones(ins, sol, nid, require_routes=False, allow_empty_station=False):
    dist = DIST
    rad = RAD
    stid = STID
    cap = CAP
    lim = LIM
    routes = sol['routes']
    for si, kind in enumerate(sol['station_types']):
        if not kind or dist[stid[si], nid] > rad[kind]:
            continue
        # Init represents an open station with no assigned targets by zero
        # drone entries. Only source operators 2/3 enumerate empty receivers.
        station = routes[si]
        if not any(station) and not allow_empty_station:
            continue
        c = cap[kind]
        limit = lim[kind]
        for di, trips in enumerate(station):
            if require_routes and not trips:
                continue
            yield si, di, trips, c[di], limit


def options_in_drone(ins, si, di, trips, cap, limit, nid, total=None):
    depot = STID[si]
    if total is None:
        total = 0.0
        for t in trips:
            total += _path_time(ins, si, t)
    for ti, trip in enumerate(trips):
        old_time = _path_time(ins, si, trip)
        n = len(trip)
        for pos in range(n + 1):
            trip.insert(pos, nid)
            if _path_energy(ins, si, trip, True) > cap:
                trip.pop(pos)
                continue
            newtime = _path_time(ins, si, trip)
            trip.pop(pos)
            after = total - old_time + newtime
            if after > limit:
                continue
            a = depot if pos == 0 else trip[pos - 1]
            b = depot if pos == n else trip[pos]
            delta = DIST[a, nid] + DIST[nid, b] - DIST[a, b]
            yield (si, di, ti, pos, delta, after, newtime - old_time)


def apply_option(sol, nid, option):
    si, di, ti, pos, *_ = option
    trips = sol['routes'][si][di]
    if ti == len(trips):
        trips.append([nid])
    else:
        trips[ti].insert(pos, nid)


FAST_MIN_REPAIR = True


def repair_candidate(ins, sol, pending, which):
    candidate = clone(sol)
    time_cost = ins.params.time_cost
    for nid in pending:
        if which == 3:
            # Actual code prioritizes first empty storage drone, NOT emptiest
            # station and NOT load-balance score on existing insertion.
            newpath = None
            for si, di, trips, cap, limit in covered_drones(
                    ins, candidate, nid, allow_empty_station=True):
                if not trips and _path_energy(ins, si, [nid], True) <= cap and _path_time(ins, si, [nid]) <= limit:
                    newpath = (si, di, 0, 0)
                    break
            if newpath:
                apply_option(candidate, nid, newpath)
                continue
        if FAST_MIN_REPAIR and which != 2:
            # Round-4 scans every insertion position and keeps the feasible
            # option with the smallest delta; for which==0 a station fallback
            # also lowers the running min_delta.  Scanning positions in
            # ascending delta order therefore reproduces the same decision
            # while evaluating route statistics only for candidates that can
            # still improve the running minimum.
            pairs = list(covered_drones(
                ins, candidate, nid, require_routes=which in (0, 1),
                allow_empty_station=which == 3))
            best = None
            newpath = None
            min_delta = math.inf
            for si, di, trips, cap, limit in pairs:
                depot = STID[si]
                ranked = []
                for ti, trip in enumerate(trips):
                    n = len(trip)
                    for pos in range(n + 1):
                        a = depot if pos == 0 else trip[pos - 1]
                        b = depot if pos == n else trip[pos]
                        ranked.append((DIST[a, nid] + DIST[nid, b] - DIST[a, b], ti, pos))
                ranked.sort(key=lambda x: x[0])
                chosen = False
                total = None
                for delta, ti, pos in ranked:
                    if delta >= min_delta:
                        break
                    trip = trips[ti]
                    trip.insert(pos, nid)
                    ok = _path_energy(ins, si, trip, True) <= cap
                    newtime = _path_time(ins, si, trip) if ok else 0.0
                    trip.pop(pos)
                    if not ok:
                        continue
                    if total is None:
                        total = 0.0
                        for t in trips:
                            total += _path_time(ins, si, t)
                    old_time = _path_time(ins, si, trip)
                    after = total - old_time + newtime
                    if after > limit:
                        continue
                    min_delta = delta
                    best = (si, di, ti, pos, delta, after, newtime - old_time)
                    chosen = True
                    break
                if not chosen and which == 0:
                    base = DIST[depot, nid]
                    if base < min_delta:
                        min_delta = base
                        newpath = (si, di, len(trips), 0)
            if best is not None:
                apply_option(candidate, nid, best)
                continue
            if newpath is not None:
                apply_option(candidate, nid, newpath)
                continue
            if which == 1:
                mincost = math.inf
                newpath = None
                for si, di, trips, cap, limit in covered_drones(ins, candidate, nid, require_routes=True):
                    single = _path_time(ins, si, [nid])
                    cost = single * time_cost
                    if _path_energy(ins, si, [nid], True) > cap:
                        continue
                    if cost <= limit and cost < mincost:
                        mincost = cost
                        newpath = (si, di, len(trips), 0)
                if newpath is not None:
                    apply_option(candidate, nid, newpath)
                    continue
            else:
                mincost = math.inf
                newpath = None
                for si, di, trips, cap, limit in covered_drones(
                        ins, candidate, nid, require_routes=False,
                        allow_empty_station=which in (2, 3)):
                    single = _path_time(ins, si, [nid])
                    cost = single * time_cost
                    if _path_energy(ins, si, [nid], True) > cap:
                        continue
                    total = 0.0
                    for t in trips:
                        total += _path_time(ins, si, t)
                    if total + single <= limit and cost < mincost:
                        mincost = cost
                        newpath = (si, di, len(trips), 0)
                if newpath is not None:
                    apply_option(candidate, nid, newpath)
                    continue
                return sol
            continue

        best = None
        newpath = None
        bestscore = -math.inf
        min_delta = math.inf
        for si, di, trips, cap, limit in covered_drones(
                ins, candidate, nid, require_routes=which in (0, 1),
                allow_empty_station=which in (2, 3)):
            found = False
            total = 0.0
            for t in trips:
                total += _path_time(ins, si, t)
            for option in options_in_drone(ins, si, di, trips, cap, limit, nid, total):
                delta = option[4]
                if which in (0, 1):
                    if delta < min_delta:
                        min_delta = delta
                        best = option
                        found = True
                else:
                    score = .6 * (limit - option[5]) / limit + .4 / (1 + abs(option[6] * time_cost))
                    if score > bestscore:
                        bestscore = score
                        best = option
                        newpath = None
            if which == 0 and not found:
                base = DIST[STID[si], nid]
                if base < min_delta:
                    min_delta = base
                    newpath = (si, di, len(trips), 0)
            if which == 2:
                single_time = _path_time(ins, si, [nid])
                after = total + single_time
                if _path_energy(ins, si, [nid], True) <= cap and after <= limit:
                    score = (limit - after) / limit
                    if score > bestscore:
                        bestscore = score
                        best = None
                        newpath = (si, di, len(trips), 0)
        if best is not None:
            apply_option(candidate, nid, best)
            continue
        if newpath is not None:
            apply_option(candidate, nid, newpath)
            continue
        if which in (1, 3):
            mincost = math.inf
            for si, di, trips, cap, limit in covered_drones(
                    ins, candidate, nid, require_routes=which == 1,
                    allow_empty_station=which == 3):
                single = _path_time(ins, si, [nid])
                cost = single * time_cost
                if _path_energy(ins, si, [nid], True) > cap:
                    continue
                if which == 1:
                    feasible = cost <= limit
                else:
                    total = 0.0
                    for t in trips:
                        total += _path_time(ins, si, t)
                    feasible = total + single <= limit
                if feasible and cost < mincost:
                    mincost = cost
                    newpath = (si, di, len(trips), 0)
            if newpath:
                apply_option(candidate, nid, newpath)
                continue
        if which in (2, 3):
            return sol
        # nearest/min-regret silently leave this target missing in public code.
    return candidate if raw_valid(ins, candidate) else sol
