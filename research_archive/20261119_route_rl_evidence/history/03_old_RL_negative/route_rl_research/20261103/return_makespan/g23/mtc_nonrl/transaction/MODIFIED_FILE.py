"""Standard sequence-aware MTC controls under the shared full-map cost cap.

No new operator/metric is claimed. All proposals use the independent scorer.
M_return and p90 are reported, not additional acceptance constraints.
"""
from __future__ import annotations

from copy import deepcopy
from functools import cmp_to_key
from itertools import combinations
import json
import math
import random
from time import perf_counter

from scorer import COST_TOLERANCE, CostAnchor, validate_candidate


METHODS = ("smith_trip_order", "joint_mtc_vnd", "joint_mtc_ils")
FAMILIES = ("reverse", "relocate", "swap", "split", "merge", "slot_reassign")
SEARCH_BUDGET_FRACTION = .9


def _mtc(score):
    value = score.get("mean_target_completion")
    if type(value) not in (int, float) or not math.isfinite(value):
        raise ValueError("finite complete-map mean_target_completion required")
    return value


def _rank(score):
    return _mtc(score)


def _eligible(kind):
    return (1,) if kind == 1 else ((0, 1) if kind == 2 else ())


def _clean(routes):
    return [[[list(trip) for trip in slot if trip] for slot in station]
            for station in routes]


def _duration(instance, si, trip):
    station = instance.stations[si]
    nodes = [instance.nodes[nid] for nid in trip]
    sequence = [station] + nodes + [station]
    distance = sum(math.hypot(a.x - b.x, a.y - b.y)
                   for a, b in zip(sequence, sequence[1:]))
    return distance / instance.params.speed + sum(n.service for n in nodes)


def smith_trip_order(instance, routes):
    """Exact MTC order for fixed intact trips on each physical slot.

    Trip q contributes its internal completion offsets plus n_q*start_q.
    Adjacent a,b favor a,b iff p_a*n_b<=p_b*n_a, hence ascending p/n.
    This solves fixed-trip ordering only, not the joint routing problem.
    """
    result = _clean(routes)
    for si, station in enumerate(result):
        for slot, trips in enumerate(station):
            durations = {tuple(t): _duration(instance, si, t) for t in trips}

            def compare(a, b):
                left, right = durations[tuple(a)] * len(b), durations[tuple(b)] * len(a)
                if left != right:
                    return -1 if left < right else 1
                return (tuple(a) > tuple(b)) - (tuple(a) < tuple(b))

            result[si][slot] = sorted(trips, key=cmp_to_key(compare))
    return result


def _locations(routes):
    return [(si, d, ti, pi, nid) for si, station in enumerate(routes)
            for d, trips in enumerate(station) for ti, trip in enumerate(trips)
            for pi, nid in enumerate(trip)]


def _neighbors(solution, family):
    """Complete within-station route proposals; Smith handles trip permutation."""
    base, kinds = solution["routes"], solution["station_types"]
    if family == "reverse":
        for si, station in enumerate(base):
            for d, trips in enumerate(station):
                for ti, trip in enumerate(trips):
                    for left in range(len(trip)):
                        for right in range(left + 1, len(trip)):
                            out = deepcopy(base)
                            out[si][d][ti][left:right + 1] = reversed(out[si][d][ti][left:right + 1])
                            yield "reverse", out, si
    elif family == "relocate":
        for si, sd, st, sp, nid in _locations(base):
            for dd in _eligible(kinds[si]):
                for dt, trip in enumerate(base[si][dd]):
                    remaining = len(trip) - int((sd, st) == (dd, dt))
                    for dp in range(remaining + 1):
                        if (sd, st) == (dd, dt) and dp == sp:
                            continue
                        out = deepcopy(base)
                        # Keep empty placeholders until insertion; indices stay stable.
                        out[si][sd][st].pop(sp)
                        out[si][dd][dt].insert(dp, nid)
                        yield "relocate_insert", out, si
                for dt in range(len(base[si][dd]) + 1):
                    if sd == dd and len(base[si][sd][st]) == 1:
                        continue  # Intact-trip ordering already optimized by Smith.
                    out = deepcopy(base)
                    out[si][sd][st].pop(sp)
                    out[si][dd].insert(dt, [nid])
                    yield "relocate_new_trip", out, si
    elif family == "swap":
        for a, b in combinations(_locations(base), 2):
            si, ad, at, ap, an = a
            sj, bd, bt, bp, bn = b
            if si != sj:
                continue
            out = deepcopy(base)
            out[si][ad][at][ap], out[si][bd][bt][bp] = bn, an
            yield "target_swap", out, si
    elif family == "split":
        for si, station in enumerate(base):
            for sd, trips in enumerate(station):
                for st, trip in enumerate(trips):
                    for cut in range(1, len(trip)):
                        for ad in _eligible(kinds[si]):
                            for bd in _eligible(kinds[si]):
                                out = deepcopy(base)
                                out[si][sd].pop(st)
                                out[si][ad].append(list(trip[:cut]))
                                out[si][bd].append(list(trip[cut:]))
                                yield "trip_split", out, si
    elif family == "merge":
        for si, station in enumerate(base):
            refs = [(d, ti) for d, trips in enumerate(station) for ti in range(len(trips))]
            for a, b in combinations(refs, 2):
                for order in (False, True):
                    left, right = (b, a) if order else (a, b)
                    merged = base[si][left[0]][left[1]] + base[si][right[0]][right[1]]
                    for dd in _eligible(kinds[si]):
                        out = deepcopy(base)
                        for d, ti in sorted((a, b), reverse=True):
                            out[si][d].pop(ti)
                        out[si][dd].append(list(merged))
                        yield "trip_merge", out, si
    elif family == "slot_reassign":
        for si, station in enumerate(base):
            for sd, trips in enumerate(station):
                for st, trip in enumerate(trips):
                    for dd in _eligible(kinds[si]):
                        if sd == dd:
                            continue
                        out = deepcopy(base)
                        out[si][sd].pop(st)
                        out[si][dd].append(list(trip))
                        yield "intact_trip_slot_reassign", out, si
    else:
        raise ValueError("unknown neighborhood family")


def _perturb(solution, rng):
    """One fixed-seed physical-route kick; full validator decides admissibility."""
    base = solution["routes"]
    locations = _locations(base)
    if not locations:
        return None
    si, sd, st, sp, nid = rng.choice(locations)
    out = deepcopy(base)
    kind = rng.choice(("swap", "reverse", "relocate", "slot", "split"))
    others = [loc for loc in locations if loc[0] == si and loc != (si, sd, st, sp, nid)]
    if kind == "swap" and others:
        _, dd, dt, dp, other = rng.choice(others)
        out[si][sd][st][sp], out[si][dd][dt][dp] = other, nid
    elif kind == "reverse" and len(base[si][sd][st]) > 1:
        left, right = sorted(rng.sample(range(len(base[si][sd][st])), 2))
        out[si][sd][st][left:right + 1] = reversed(out[si][sd][st][left:right + 1])
    elif kind == "slot":
        dd = rng.choice(_eligible(solution["station_types"][si]))
        trip = out[si][sd].pop(st)
        out[si][dd].append(trip)
    elif kind == "split" and len(base[si][sd][st]) > 1:
        cut = rng.randrange(1, len(base[si][sd][st]))
        dd = rng.choice(_eligible(solution["station_types"][si]))
        trip = out[si][sd].pop(st)
        out[si][sd].append(trip[:cut])
        out[si][dd].append(trip[cut:])
    else:
        kind = "relocate"
        out[si][sd][st].pop(sp)
        dd = rng.choice(_eligible(solution["station_types"][si]))
        if out[si][dd] and rng.random() < .8:
            dt = rng.randrange(len(out[si][dd]))
            out[si][dd][dt].insert(rng.randrange(len(out[si][dd][dt]) + 1), nid)
        else:
            out[si][dd].append([nid])
    return "perturb_" + kind, out, si


class _Timer:
    def __init__(self, started_at, budget_s, clock):
        self.started_at, self.budget_s, self.clock = started_at, budget_s, clock
        self.previous = started_at

    def elapsed(self):
        now = self.clock()
        if type(now) not in (int, float) or not math.isfinite(now) or now < self.previous:
            raise ValueError("finite monotonic clock in caller start domain required")
        self.previous = now
        return now - self.started_at

    def search_expired(self):
        return self.elapsed() >= self.budget_s * SEARCH_BUDGET_FRACTION


def _certificate(score, move, station, phase, elapsed):
    reasons = list(score.get("issues", [])) + list(score.get("domain_issues", []))
    if not score["cost_cap_satisfied"]:
        reasons.append("full_map_cost_cap_exceeded")
    return {"move": move, "station": station, "phase": phase,
            "solution_sha256": score.get("solution_sha256"),
            "admissible": score["admissible"], "original_feasible": score["original_feasible"],
            "domain_valid": score["domain_valid"], "cost_cap_satisfied": score["cost_cap_satisfied"],
            "cost": score["cost"], "raw_cost_minus_cap": score["raw_cost_minus_cap"],
            "mean_target_completion": score["mean_target_completion"],
            "M_return": score["M_return"],
            "p90_target_completion_nearest_rank": score["p90_target_completion_nearest_rank"],
            "validation_finished_elapsed_s": elapsed, "issues": reasons}


def solve(instance, anchor_or_solution, *, method="joint_mtc_ils", budget_s=6.0,
          started_at=None, clock=perf_counter, max_evaluations=12000,
          seed=20261103, max_perturbations=8):
    """Return complete raw/chosen solutions with candidate/deadline accounting.

    The caller start must precede loading. Anchor generation is a shared input
    cost in D; all checks, generation, validation, copying and delivery here count.
    max_evaluations limits search proposals, not final delivery checks. Counters
    count direct validator calls; each internally rechecks the anchor as well.
    """
    if method not in METHODS:
        raise ValueError("method must be one of " + repr(METHODS))
    if type(budget_s) not in (int, float) or not math.isfinite(budget_s) or budget_s <= 0:
        raise ValueError("budget_s must be finite and positive")
    if type(max_evaluations) is not int or max_evaluations < 1:
        raise ValueError("max_evaluations must be a positive integer")
    if type(max_perturbations) is not int or max_perturbations < 0 or type(seed) is not int:
        raise ValueError("integer seed and nonnegative integer max_perturbations required")
    started_at = clock() if started_at is None else started_at
    if type(started_at) not in (int, float) or not math.isfinite(started_at):
        raise ValueError("started_at must be finite")
    timer = _Timer(started_at, budget_s, clock)
    timer.elapsed()
    anchor = (anchor_or_solution if isinstance(anchor_or_solution, CostAnchor)
              else CostAnchor.from_solution(instance, anchor_or_solution))
    anchor.verify(instance)
    ledger, accepted = [], []
    counts = {"anchor_validation_calls": 0, "candidate_validation_calls": 0,
              "delivery_validation_calls": 0, "rejected_inadmissible_candidates": 0,
              "late_search_candidates": 0, "perturbation_attempts": 0,
              "accepted_perturbations": 0, "vnd_accepted_moves": 0}

    def evaluate(solution, move, station, phase):
        score = validate_candidate(instance, solution, anchor, epsilon=0.0,
                                   cost_tolerance=COST_TOLERANCE)
        elapsed = timer.elapsed()
        counts[phase + "_validation_calls"] += 1
        ledger.append(_certificate(score, move, station, phase, elapsed))
        if phase == "candidate":
            counts["rejected_inadmissible_candidates"] += int(not score["admissible"])
            counts["late_search_candidates"] += int(elapsed > budget_s)
        return score, elapsed

    best = anchor.solution()
    best_score, _ = evaluate(best, "shared_anchor", None, "anchor")
    anchor_mtc = _mtc(best_score)
    current, current_score = deepcopy(best), best_score
    stop_reason = "cheap_control_complete"
    if not timer.search_expired():
        proposal = anchor.solution()
        proposal["routes"] = smith_trip_order(instance, proposal["routes"])
        score, elapsed = evaluate(proposal, "smith_trip_order", None, "candidate")
        if score["admissible"] and elapsed <= budget_s and _rank(score) < _rank(best_score):
            best, best_score = proposal, score
        if score["admissible"] and elapsed <= budget_s:
            current, current_score = proposal, score

    rng = random.Random(seed)
    if method != "smith_trip_order":
        family_index, stop_reason = 0, "local_minimum"
        while True:
            if counts["candidate_validation_calls"] >= max_evaluations:
                stop_reason = "evaluation_cap"
                break
            if timer.search_expired():
                stop_reason = "search_deadline_reserve"
                break
            if family_index == len(FAMILIES):
                if method != "joint_mtc_ils" or counts["perturbation_attempts"] >= max_perturbations:
                    stop_reason = "local_minimum_or_perturbation_cap"
                    break
                kick = _perturb(current, rng)
                if kick is None:
                    stop_reason = "no_targets_to_perturb"
                    break
                move, routes, si = kick
                counts["perturbation_attempts"] += 1
                proposal = anchor.solution()
                proposal["routes"] = smith_trip_order(instance, routes)
                score, elapsed = evaluate(proposal, move, si, "candidate")
                if score["admissible"] and elapsed <= budget_s:
                    current, current_score = proposal, score
                    counts["accepted_perturbations"] += 1
                    accepted.append({"move": move, "station": si, "solution": deepcopy(proposal),
                                     "mean_target_completion": _mtc(score),
                                     "cost": score["cost"], "M_return": score["M_return"]})
                    if _rank(score) < _rank(best_score):
                        best, best_score = proposal, score
                    family_index = 0
                continue
            local_best = None
            iterator = iter(_neighbors(current, FAMILIES[family_index]))
            while counts["candidate_validation_calls"] < max_evaluations and not timer.search_expired():
                try:
                    move, routes, si = next(iterator)
                except StopIteration:
                    break
                proposal = anchor.solution()
                proposal["routes"] = smith_trip_order(instance, routes)
                score, elapsed = evaluate(proposal, move + "+smith", si, "candidate")
                if not score["admissible"] or elapsed > budget_s:
                    continue
                if _rank(score) < _rank(best_score):
                    best, best_score = proposal, score
                if _rank(score) < _rank(current_score) and (
                        local_best is None or _rank(score) < _rank(local_best[1])):
                    local_best = proposal, score, move, si
            if local_best is None:
                family_index += 1
            else:
                current, current_score, move, si = local_best
                counts["vnd_accepted_moves"] += 1
                accepted.append({"move": move, "station": si, "solution": deepcopy(current),
                                 "mean_target_completion": _mtc(current_score),
                                 "cost": current_score["cost"], "M_return": current_score["M_return"]})
                family_index = 0

    # Local MTC delivery deliberately does not call the minmax-only finalizer.
    validation_started = timer.elapsed()
    raw_solution = deepcopy(best)
    raw_score, raw_finished = evaluate(raw_solution, "delivery_raw", None, "delivery")
    reason = None
    if not raw_score["admissible"]:
        reason = "raw_inadmissible"
    elif raw_finished > budget_s:
        reason = "raw_validation_late"
    elif _mtc(raw_score) > anchor_mtc:
        reason = "raw_worse_than_anchor_MTC"
    chosen_solution = chosen_score = fallback_solution = fallback_score = None
    fallback_finished = None
    if reason is None:
        chosen_solution, chosen_score = deepcopy(raw_solution), deepcopy(raw_score)
    else:
        fallback_solution = anchor.solution()
        fallback_score, fallback_finished = evaluate(
            fallback_solution, "delivery_anchor_fallback", None, "delivery")
        if fallback_score["admissible"] and fallback_finished <= budget_s:
            chosen_solution, chosen_score = deepcopy(fallback_solution), deepcopy(fallback_score)

    result = {"schema": "cost_capped_mean_target_completion_delivery_v1",
        "method": method, "implementation": "standard_smith_station_joint_mtc_vnd_ils_v1",
        "primary_objective": "mean_target_completion", "seed": seed,
        "selection_order": ["mean_target_completion"],
        "M_return_is_extra_constraint": False,
        "budget_scope": "D_improvement_from_common_ready_input", "anchor_generation_included": False,
        "caller_start_must_precede_model_load_and_construction": True,
        "budget_s": budget_s, "search_budget_fraction": SEARCH_BUDGET_FRACTION,
        "validation_started_elapsed_s": validation_started,
        "raw_validation_finished_elapsed_s": raw_finished,
        "raw_solution": raw_solution, "raw_score": raw_score,
        "fallback_attempted": reason is not None, "fallback_reason": reason,
        "fallback_solution": fallback_solution, "fallback_score": fallback_score,
        "fallback_validation_finished_elapsed_s": fallback_finished,
        "chosen_solution": chosen_solution, "chosen_score": chosen_score,
        "anchor_solution_sha256": anchor.solution_sha256,
        "anchor_mean_target_completion": anchor_mtc, "anchor_M_return": anchor.makespan,
        "candidate_certificates": ledger, "accepted_moves": accepted,
        "search_stop_reason": stop_reason,
        "search_timed_out": stop_reason == "search_deadline_reserve",
        "max_evaluations": max_evaluations, "max_perturbations": max_perturbations, **counts}
    result["total_validation_calls"] = sum(counts[k] for k in (
        "anchor_validation_calls", "candidate_validation_calls", "delivery_validation_calls"))
    result["validation_counter_semantics"] = (
        "direct validate_candidate calls; each internally rescans anchor and candidate; "
        "anchor construction/verify also rescans anchor; all time included")
    json.dumps(result, allow_nan=False, separators=(",", ":"))
    ready = timer.elapsed()
    result["output_ready_elapsed_s"] = ready
    if ready > budget_s:
        result["chosen_solution"] = result["chosen_score"] = None
    result["ontime_valid_output"] = result["chosen_solution"] is not None
    result["fallback_used"] = bool(result["ontime_valid_output"] and reason is not None)
    result["failure_count"] = int(not result["ontime_valid_output"])
    result["status"] = "ONTIME_VALID" if result["ontime_valid_output"] else "NO_ONTIME_VALID_OUTPUT"
    return result
