"""Deadline-aware conditional-route delivery with explicit raw and fallback logs.

The caller starts the clock BEFORE loading/encoding/constructing its method.
This helper does not manufacture an on-time incumbent from a late validation.
The shared anchor's prior generation is an input cost reported separately in D.
"""
from __future__ import annotations

from copy import deepcopy
import math
from time import perf_counter

from scorer import COST_TOLERANCE, validate_candidate


def finalize_result(instance, raw_solution, anchor, *, started_at, budget_s,
                    clock=perf_counter, epsilon=0.0,
                    cost_tolerance=COST_TOLERANCE):
    if (type(started_at) not in (int, float) or not math.isfinite(started_at)
            or type(budget_s) not in (int, float) or not math.isfinite(budget_s)
            or budget_s <= 0):
        raise ValueError("finite caller start and positive improvement budget required")
    previous = started_at

    def elapsed():
        nonlocal previous
        now = clock()
        if (type(now) not in (int, float) or not math.isfinite(now)
                or now < previous):
            raise ValueError("a monotonic clock in the caller's clock domain is required")
        previous = now
        return now - started_at

    validation_started = elapsed()
    raw_copy = deepcopy(raw_solution)
    raw_score = validate_candidate(instance, raw_copy, anchor,
                                   epsilon=epsilon, cost_tolerance=cost_tolerance)
    raw_finished = elapsed()
    reason = None
    if not raw_score["admissible"]:
        reason = "raw_inadmissible"
    elif raw_finished > budget_s:
        reason = "raw_validation_late"
    elif raw_score["M_return"] > anchor.makespan:
        reason = "raw_worse_than_anchor"

    chosen_solution = chosen_score = None
    fallback_copy = fallback_score = None
    fallback_finished = None
    if reason is None:
        chosen_solution, chosen_score = raw_copy, raw_score
    else:
        fallback_copy = anchor.solution()
        fallback_score = validate_candidate(instance, fallback_copy, anchor,
                                            epsilon=epsilon, cost_tolerance=cost_tolerance)
        fallback_finished = elapsed()
        if fallback_score["admissible"] and fallback_finished <= budget_s:
            chosen_solution, chosen_score = fallback_copy, fallback_score

    record = {
        "schema": "return_makespan_delivery_v1",
        "budget_scope": "D_improvement_from_common_ready_input",
        "anchor_generation_included": False,
        "caller_start_must_precede_model_load_and_construction": True,
        "budget_s": budget_s,
        "validation_started_elapsed_s": validation_started,
        "raw_validation_finished_elapsed_s": raw_finished,
        "raw_solution": raw_copy,
        "raw_score": raw_score,
        "fallback_attempted": reason is not None,
        "fallback_reason": reason,
        "fallback_solution": fallback_copy,
        "fallback_score": fallback_score,
        "fallback_validation_finished_elapsed_s": fallback_finished,
        "chosen_solution": deepcopy(chosen_solution),
        "chosen_score": deepcopy(chosen_score),
        "anchor_solution_sha256": anchor.solution_sha256,
    }
    ready = elapsed()  # Copies, identities, validation and record assembly count.
    record["output_ready_elapsed_s"] = ready
    if ready > budget_s:
        record["chosen_solution"] = record["chosen_score"] = None
    record["ontime_valid_output"] = record["chosen_solution"] is not None
    record["fallback_used"] = bool(record["ontime_valid_output"] and reason is not None)
    record["status"] = "ONTIME_VALID" if record["ontime_valid_output"] else "NO_ONTIME_VALID_OUTPUT"
    return record
