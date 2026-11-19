"""Finite prefix-preserving completion component. Numerical execution: <COMPUTE_HOST> only."""
import bisect
import hashlib
import json
import math
import socket


def host():
    assert socket.gethostname() == '<COMPUTE_HOST>', '<COMPUTE_HOST> only'


def canonical(x): return json.dumps(x, sort_keys=True, separators=(',', ':'))
def digest(x): return hashlib.sha256(canonical(x).encode()).hexdigest()
def freeze(x): return tuple(freeze(v) for v in x) if isinstance(x, list) else x


def norm(slot):
    done, prefix, suffix, future = slot
    future = tuple(t for t in future if t)
    if not prefix and not suffix and future:
        suffix, future = future[0], future[1:]
    return done, prefix, suffix, future


def routes(slot):
    d, p, t, f = slot
    return d + ((p+t,) if p or t else ()) + f


def pending(slot):
    return slot[2] + tuple(a for t in slot[3] for a in t)


def remove_target(station, a):
    out, found = [], 0
    for done, prefix, suffix, future in station:
        found += suffix.count(a) + sum(t.count(a) for t in future)
        suffix = tuple(v for v in suffix if v != a)
        future = tuple(tuple(v for v in t if v != a) for t in future)
        out.append(norm((done, prefix, suffix, future)))
    assert found == 1
    return tuple(out)


def force(station, k, a):
    out = list(remove_target(station, a) if a is not None else station)
    d, p, t, f = out[k]
    if a is not None:
        p = p+(a,)
    else:
        assert p
        d, p = d+(p,), ()
    out[k] = norm((d, p, t, f))
    return tuple(out)


def neighborhood(station, limit, check=lambda: None):
    """Identity or one relocation of an unexecuted target, with new trips allowed."""
    out = {station}
    for a in sorted(v for sl in station for v in pending(sl)):
        check()
        removed = remove_target(station, a)
        for k, (d, p, t, f) in enumerate(removed):
            for i in range(len(t)+1):
                check()
                ss = list(removed)
                ss[k] = norm((d, p, t[:i]+(a,)+t[i:], f))
                out.add(tuple(ss))
            for j, trip in enumerate(f):
                for i in range(len(trip)+1):
                    check()
                    ss, ff = list(removed), list(f)
                    ff[j] = trip[:i]+(a,)+trip[i:]
                    ss[k] = norm((d, p, t, tuple(ff)))
                    out.add(tuple(ss))
            for j in range(len(f)+1):
                check()
                ss = list(removed)
                ss[k] = norm((d, p, t, f[:j]+((a,),)+f[j:]))
                out.add(tuple(ss))
            if not p:
                ss = list(removed)
                ss[k] = norm((d, (), (a,), ((t,) if t else ())+f))
                out.add(tuple(ss))
    assert len(out) <= limit, 'frozen station candidate limit'
    return sorted(out)


class Compiler:
    def check(self):
        return None

    def __init__(self, fixture, mode, limit):
        host()
        assert mode in ('independent_compensation', 'shared_deferred_compensation')
        self.f, self.mode, self.limit = fixture, mode, limit
        self.targets = {row[0]: row[1:] for row in fixture['targets']}
        self.station_nodes = [row[1:3] for row in fixture['stations']]
        self.witness = tuple(tuple(norm(sl) for sl in station) for station in freeze(fixture['plans']))
        self.assigned = [set(a for sl in station for t in routes(sl) for a in t) for station in self.witness]
        assert set().union(*self.assigned) == set(self.targets)
        assert sum(map(len, self.assigned)) == len(self.targets)
        self.counters = {k: 0 for k in ('local_expansions', 'remote_expansions', 'candidate_strings',
                                       'station_scores', 'global_scores', 'envelope_builds', 'envelope_queries',
                                       'remote_cache_hits', 'deferred_queries')}
        self.cache = {}
        self.root = self.global_score(self.witness)
        assert self.root['valid'], self.root
        self.cap = self.root['cost']

    def leg(self, a, b):
        dx, dy = b[0]-a[0], b[1]-a[1]
        r2 = dx*dx+dy*dy
        if not r2: return 0.
        wx, wy = self.f['wind']
        dot = wx*dx+wy*dy
        return r2/(math.sqrt(dot*dot+(900.**2-wx*wx-wy*wy)*r2)+dot)

    def station_score(self, si, station):
        self.counters['station_scores'] += 1
        depot = self.station_nodes[si]
        duties, energies, ids = [], [], []
        valid = True
        for k, sl in enumerate(station):
            duty, ee = 0., []
            for trip in routes(sl):
                x, travel, service, use = depot, 0., 0., 0.
                for a in trip:
                    nx, ny, energy, duration = self.targets[a]
                    ids.append(a)
                    valid &= math.hypot(nx-depot[0], ny-depot[1]) <= 5000.+1e-7
                    travel += self.leg(x, (nx, ny))
                    service += duration
                    use += energy
                    x = (nx, ny)
                travel += self.leg(x, depot)
                duty += travel+service
                ee.append(.018*travel+use)
            valid &= duty <= 600.+1e-7 and all(e <= (1., .81)[k]+1e-12 for e in ee)
            duties.append(duty)
            energies.append(ee)
        valid &= sorted(ids) == sorted(self.assigned[si])
        return {'valid': bool(valid), 'duties': duties, 'energies': energies,
                'operating': duties[0]+duties[1], 'M': max(duties)}

    def global_score(self, plan):
        self.counters['global_scores'] += 1
        records = [self.station_score(si, station) for si, station in enumerate(plan)]
        operating = 0.
        for r in records:
            for d in r['duties']: operating += d
        return {'valid': all(r['valid'] for r in records), 'cost': len(plan)*43.4+.5*operating,
                'M': max(r['M'] for r in records), 'stations': records}

    def local(self, si, station, H):
        self.check()
        self.counters['local_expansions'] += 1
        candidates = neighborhood(station, self.limit, self.check)
        self.counters['candidate_strings'] += len(candidates)
        scored = [(self.station_score(si, st), st) for st in candidates]
        fit = [(sc['operating'], sc['M'], st) for sc, st in scored if sc['valid'] and sc['M'] <= H+1e-7]
        return min(fit)[2] if fit else None

    def donor(self, si, H):
        self.check()
        identity = (si, self.witness[si])
        shared = self.mode == 'shared_deferred_compensation'
        if shared and identity in self.cache:
            self.counters['remote_cache_hits'] += 1
            xs, prefix = self.cache[identity]
        else:
            self.counters['remote_expansions'] += 1
            candidates = neighborhood(self.witness[si], self.limit, self.check)
            self.counters['candidate_strings'] += len(candidates)
            scored = [(self.station_score(si, st), st) for st in candidates]
            valid = [(sc['M'], sc['operating'], st) for sc, st in scored if sc['valid']]
            if not shared:
                fit = [(c, m, st) for m, c, st in valid if m <= H+1e-7]
                return min(fit)[2] if fit else None
            self.counters['envelope_builds'] += 1
            xs, prefix, best = [], [], None
            for m, c, st in sorted(valid):
                current = (c, m, st)
                best = min(best, current) if best is not None else current
                xs.append(m)
                prefix.append(best[2])
            self.cache[identity] = xs, prefix
        self.counters['envelope_queries'] += 1
        i = bisect.bisect_right(xs, H+1e-7)-1
        return prefix[i] if i >= 0 else None

    def accepted(self, plan, H):
        sc = self.global_score(plan)
        return sc, bool(sc['valid'] and sc['M'] <= H+1e-7 and sc['cost'] <= self.cap+1e-7)

    def query(self, si, k, a, H):
        self.check()
        forced = force(self.witness[si], k, a)
        p0 = list(self.witness)
        p0[si] = forced
        single, single_ok = self.accepted(tuple(p0), H)
        local = self.local(si, forced, H)
        result = {'action': [si, k, a], 'H': H, 'single_support': single_ok,
                  'local_support': False, 'supported': False, 'compensated': False}
        if local is None:
            result['reason'] = 'no_local_physical_tail_within_H'
            return result
        combined = list(self.witness)
        combined[si] = local
        native, native_ok = self.accepted(tuple(combined), H)
        result['local_support'] = native_ok
        result['native_cost_debt'] = native['cost']-self.cap
        if not native_ok:
            self.counters['deferred_queries'] += 1
            for sj in range(len(combined)):
                if sj == si: continue
                choice = self.donor(sj, H)
                if choice is None:
                    result['reason'] = 'no_remote_tail_within_H'
                    return result
                combined[sj] = choice
        sc, ok = self.accepted(tuple(combined), H)
        result.update(supported=ok, compensated=ok and not native_ok)
        if ok:
            result.update(plan=combined, M=sc['M'], cost=sc['cost'], reason='complete_witness')
        else:
            result['reason'] = 'complete_cap_or_physics_failed'
        return result

    def run(self, factors, max_queries):
        out = []
        for factor in factors:
            H = self.root['M']*factor
            for si, station in enumerate(self.witness):
                remaining = sorted(a for sl in station for a in pending(sl))
                for k in range(2):
                    for a in remaining+([None] if station[k][1] else []):
                        out.append(self.query(si, k, a, H))
                        assert len(out) <= max_queries, 'frozen query limit'
        return {'name': self.f['name'], 'root': self.root, 'cap': self.cap, 'answers': out,
                'counters': dict(self.counters), 'remote_prefix_identities': [digest(k) for k in self.cache]}


def next_tokens(station, enabled_slots):
    """Physical actions compatible with one complete pre-action witness."""
    tokens = []
    for k in enabled_slots:
        done, prefix, suffix, future = station[k]
        if suffix:
            tokens.append((k, suffix[0]))
        elif prefix:
            tokens.append((k, None))
    return tuple(tokens)


def compile_pair_rows(station, enabled_slots, score_candidate, *,
                      rank_by_slot=(4, 3), row_limit=20000, check=lambda: None):
    """Enumerate registered <=2-source-trip / <=2-output-trip topology only.

    The caller binds the rank domain and supplies the original physical scorer.
    No local cost-cap filter is applied. Completed trips and open prefixes stay
    fixed; untouched pending trips retain their relative order. This is a fixed
    exact local-search component, not an RL policy or full-domain action oracle.
    """
    import itertools
    station = tuple(norm(sl) for sl in station)
    enabled_slots = tuple(enabled_slots)
    if len(station) != 2 or any(k not in (0, 1) for k in enabled_slots):
        raise ValueError('TWO_SLOTS_AND_VALID_ENABLED_SLOTS_REQUIRED')
    if any(station[k][1] or station[k][2] or station[k][3]
           for k in (0, 1) if k not in enabled_slots):
        raise ValueError('DISABLED_SLOT_HAS_PENDING_ROUTE')
    remaining = [((sl[1] + sl[2],) if sl[1] or sl[2] else ()) + sl[3]
                 for sl in station]
    source_trips = [(k, j, trip) for k in enabled_slots
                    for j, trip in enumerate(remaining[k])]
    seen, rows, buckets = set(), [], {}
    attempted = 0
    original_targets = sorted(a for sl in station for tr in routes(sl) for a in tr)

    def register(candidate, pair_ids):
        nonlocal attempted
        check()
        attempted += 1
        if candidate in seen:
            return
        seen.add(candidate)
        if any(candidate[k][:2] != station[k][:2] for k in (0, 1)):
            raise ValueError('EXECUTED_PREFIX_CHANGED')
        if sorted(a for sl in candidate for tr in routes(sl) for a in tr) != original_targets:
            raise ValueError('TARGET_COVERAGE_CHANGED')
        receipt = score_candidate(candidate)
        if receipt is None:
            return
        if len(rows) >= row_limit:
            raise RuntimeError('FROZEN_AIR2_ROW_LIMIT')
        tokens = next_tokens(candidate, enabled_slots)
        row = {'station': candidate, 'pair_source_ids': pair_ids,
               'route_hash': digest(candidate), 'actions': tokens, 'score': receipt}
        index = len(rows)
        rows.append(row)
        for action in tokens:
            buckets.setdefault(canonical(action), []).append(index)

    register(station, ())
    pairs = [(row,) for row in source_trips]
    pairs += list(itertools.combinations(source_trips, 2))
    for pair in pairs:
        check()
        if any(len(trip) > rank_by_slot[k] for k, j, trip in pair):
            raise ValueError('SOURCE_TRIP_OUTSIDE_BOUND_RANK_DOMAIN')
        selected = {(k, j) for k, j, trip in pair}
        targets = tuple(sorted(a for k, j, trip in pair for a in trip))
        if len(targets) != len(set(targets)) or len(targets) > 8:
            raise ValueError('PAIR_UNION_NOT_UNIQUE_OR_EXCEEDS_EIGHT')
        base = [tuple(trip for j, trip in enumerate(remaining[k]) if (k, j) not in selected)
                for k in (0, 1)]
        pinned_selected = {k for k in enabled_slots if station[k][1] and (k, 0) in selected}
        for ordering in itertools.permutations(targets):
            check()
            partitions = [(ordering,)]
            partitions.extend((ordering[:cut], ordering[cut:]) for cut in range(1, len(ordering)))
            for trips in partitions:
                for owners in itertools.product(enabled_slots, repeat=len(trips)):
                    check()
                    if any(len(trip) > rank_by_slot[k] for trip, k in zip(trips, owners)):
                        continue
                    new = [[trip for trip, owner in zip(trips, owners) if owner == k] for k in (0, 1)]
                    candidate = []
                    compatible = True
                    for k in (0, 1):
                        done, prefix, _, _ = station[k]
                        if k in pinned_selected:
                            anchored = [tr for tr in new[k] if tr[:len(prefix)] == prefix]
                            if len(anchored) != 1:
                                compatible = False
                                break
                            current = anchored[0]
                            rest = tuple(tr for tr in new[k] if tr != current) + base[k]
                            tail = current[len(prefix):]
                        elif prefix:
                            current = base[k][0]
                            tail = current[len(prefix):]
                            rest = tuple(new[k]) + base[k][1:]
                        else:
                            full = tuple(new[k]) + base[k]
                            tail, rest = (full[0], full[1:]) if full else ((), ())
                        candidate.append(norm((done, prefix, tail, rest)))
                    if compatible:
                        register(tuple(candidate), tuple((k, j) for k, j, tr in pair))
    return {'status': 'COMPLETE_REGISTERED_PAIR_DOMAIN_ONLY', 'rows': rows,
            'buckets': buckets, 'attempted_including_duplicates': attempted,
            'distinct_structural_candidates_scored': len(seen)}
