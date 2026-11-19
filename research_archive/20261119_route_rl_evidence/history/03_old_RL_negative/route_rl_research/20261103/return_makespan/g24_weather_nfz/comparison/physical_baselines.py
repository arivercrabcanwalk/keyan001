"""Bounded non-RL constructors for the fixed-outer weather route domain.

The routines here select only environment physical actions: a fixed-station
slot visits one of its fixed-owner targets, or that slot returns to its own
station.  They neither expose nor select search operators.  ``beam_construct``
is deliberately an anytime, width-limited control; its width is a resource
bound, not an optimality assertion.  ``enumerate_tiny_routes`` is a separate,
explicitly capped exhaustive reference for engineering fixtures only.
"""
from __future__ import annotations

from copy import deepcopy
from math import inf, isfinite
import time
from typing import Any, Optional

from weather_full_map import WeatherFullMapEnv, replay_weather_solution


DEFAULT_BEAM_WIDTH = 8
DEFAULT_TINY_TARGET_CAP = 7
DEFAULT_TINY_NODE_CAP = 100_000


def _new_env(case) -> WeatherFullMapEnv:
    """Build the common environment without changing the caller's case tuple."""
    if not isinstance(case, tuple) or len(case) < 4:
        raise TypeError("case must be (instance, anchor, scenario, weather_cost_cap)")
    return WeatherFullMapEnv(*case[:3], weather_cost_cap=case[3])


def _deadline_reached(started: float, deadline: Optional[float]) -> bool:
    return deadline is not None and time.perf_counter() - started >= deadline


def _action_receipt(action, reward, info, elapsed_s: float) -> dict[str, Any]:
    return {"station_idx": action.station_idx, "slot": action.slot,
            "target": "RETURN" if action.is_return else action.target_id,
            "reward": reward, "completion_min": info.get("completion_min"),
            "failure": info.get("failure"), "elapsed_s": elapsed_s}


def _action_signature(events: tuple[dict[str, Any], ...]) -> tuple:
    """Stable total-order tie breaker independent of object identity."""
    return tuple((event["station_idx"], event["slot"],
                  -1 if event["target"] == "RETURN" else event["target"])
                 for event in events)


def _result_from_done_env(env: WeatherFullMapEnv) -> Optional[dict[str, Any]]:
    """Materialize a terminal physical state through the independent replay."""
    if not env.done or env.failure is not None:
        return None
    if env._terminal_replay is not None:
        if not env._terminal_replay["admissible"]:
            return None
        return env.result()

    # A zero-target fixture is terminal before any ``step``.  It still needs
    # the same terminal authority as a nonempty route, not a synthetic pass.
    solution = env.candidate()
    replay = replay_weather_solution(env.instance, env.anchor, env.scenario, solution,
                                     weather_cost_cap=env.weather_cost_cap,
                                     tolerance=env.cost_tolerance)
    if not replay["admissible"]:
        return None
    return {"solution": solution, "replay": replay, "reward": env.total_reward,
            "action_count": env.action_count}


def _result_key(result: dict[str, Any], events: tuple[dict[str, Any], ...]) -> tuple:
    """Use final-return makespan first and MTC only as a deterministic tie break."""
    replay = result["replay"]
    mtc = replay["MTC"]
    return (float(replay["M_return"]), inf if mtc is None else float(mtc),
            float(replay["weather_cost"]), _action_signature(events))


def _frontier_key(env: WeatherFullMapEnv, events: tuple[dict[str, Any], ...]) -> tuple:
    """Deterministic optimistic ranking for a bounded beam, never a certificate."""
    remaining = sum(len(pool) for pool in env.remaining.values())
    return (float(env.potential), float(env.weather_cost), remaining, len(events),
            _action_signature(events))


def _base_response(*, started: float, events: tuple[dict[str, Any], ...] = (),
                   result: Optional[dict[str, Any]] = None, failure: Optional[str] = None,
                   **extra: Any) -> dict[str, Any]:
    elapsed = time.perf_counter() - started
    complete = result is not None
    response = {"complete": complete, "failure": None if complete else failure,
                "events": list(events), "transitions": [], "elapsed_s": elapsed,
                "result": result}
    response.update(extra)
    return response


def _finish_incumbent(*, started: float, incumbent, stop_reason: Optional[str], **extra: Any) -> dict[str, Any]:
    """Return a verified incumbent without presenting a truncated search as exact."""
    # Match ``run_episode``: an answer produced after its cooperative deadline
    # is not a delivered completion, even when a branch found a legal route.
    if stop_reason == "deadline":
        return _base_response(started=started, failure="deadline", search_status="deadline",
                              deadline_hit=True, **extra)
    if incumbent is None:
        return _base_response(started=started, failure=stop_reason or "no_complete_candidate",
                              search_status=stop_reason or "exhausted_without_complete", **extra)
    env, events, result, found_s = incumbent
    response = _base_response(started=started, events=events, result=result,
                              search_status=("beam_exhausted" if stop_reason is None else
                                             f"{stop_reason}_with_incumbent"),
                              incumbent_found_s=found_s, **extra)
    response["deadline_hit"] = stop_reason == "deadline"
    response["incumbent_on_time"] = (stop_reason != "deadline" or found_s <= extra.get("deadline_s", inf))
    # ``env`` is retained until this point so the winning physical state cannot
    # be confused with a replay of a different branch.
    response["physical_action_count"] = env.action_count
    return response


def _validate_deadline(deadline: Optional[float]) -> Optional[float]:
    if deadline is None:
        return None
    if not isinstance(deadline, (int, float)) or not isfinite(deadline) or deadline < 0:
        raise ValueError("deadline must be a finite number of seconds or None")
    return float(deadline)


def _consider(incumbent, env: WeatherFullMapEnv, events: tuple[dict[str, Any], ...],
              found_s: float):
    result = _result_from_done_env(env)
    if result is None:
        return incumbent
    candidate = (env, events, result, found_s)
    return candidate if incumbent is None or _result_key(result, events) < _result_key(incumbent[2], incumbent[1]) else incumbent


def beam_construct(case, deadline: Optional[float], width: int = DEFAULT_BEAM_WIDTH) -> dict[str, Any]:
    """Construct an anytime, replay-verified route using a modest bounded beam.

    ``deadline`` bounds search work cooperatively.  As in ``run_episode``, an
    invocation that reaches its deadline reports ``failure='deadline'`` and no
    result, even if it had already discovered a terminal branch.  A completed
    result is therefore both legal and delivered within this routine's budget.
    """
    deadline = _validate_deadline(deadline)
    if not isinstance(width, int) or isinstance(width, bool) or width < 1:
        raise ValueError("width must be a positive integer")
    started = time.perf_counter()
    if _deadline_reached(started, deadline):
        return _base_response(started=started, failure="deadline", search_status="deadline",
                              deadline_hit=True, width=width, deadline_s=deadline)
    env = _new_env(case)
    initial = _result_from_done_env(env)
    if initial is not None:
        return _base_response(started=started, result=initial, search_status="complete",
                              deadline_hit=False, incumbent_found_s=time.perf_counter() - started,
                              width=width, deadline_s=deadline, physical_action_count=0)
    if env.terminated:
        return _base_response(started=started, failure=env.failure or "initial_terminal_rejected",
                              search_status="initial_terminal", deadline_hit=False,
                              width=width, deadline_s=deadline)

    # The first component is a native-action priority.  With width one it
    # follows the common deterministic physical greedy rule: choose the legal
    # target with the least projected outbound time, and only return when no
    # target remains legal.  Potential/cost remain beam tie breakers below.
    frontier: list[tuple[WeatherFullMapEnv, tuple[dict[str, Any], ...], tuple]] = [(env, (), ())]
    incumbent = None
    expanded = generated = 0
    stop_reason = None
    while frontier:
        if _deadline_reached(started, deadline):
            stop_reason = "deadline"
            break
        next_frontier = []
        for parent, parent_events, _ in frontier:
            if _deadline_reached(started, deadline):
                stop_reason = "deadline"
                break
            observation = parent.observation()
            legal = [(index, action) for index, (action, allowed) in
                     enumerate(zip(observation["actions"], observation["mask"])) if allowed]
            if not legal:
                continue
            has_target = any(not action.is_return for _, action in legal)
            expanded += 1
            for index, action in legal:
                if _deadline_reached(started, deadline):
                    stop_reason = "deadline"
                    break
                child = deepcopy(parent)
                _, reward, _, info = child.step(action)
                events = parent_events + (_action_receipt(action, reward, info, time.perf_counter() - started),)
                generated += 1
                if child.done:
                    candidate = _consider(incumbent, child, events, time.perf_counter() - started)
                    if candidate is not incumbent:
                        incumbent = candidate
                elif not child.terminated:
                    if has_target:
                        action_priority = (int(action.is_return),
                                           float(observation["candidates"][index, 5]),
                                           action.station_idx, action.slot, action.target_id)
                    else:
                        # The reference greedy control preserves native action
                        # ordering for returns rather than treating it as a
                        # second optimization objective.
                        action_priority = (0, 0.0, index)
                    next_frontier.append((child, events, action_priority))
            if stop_reason is not None:
                break
        if stop_reason is not None:
            break
        next_frontier.sort(key=lambda node: (node[2], _frontier_key(node[0], node[1])))
        frontier = next_frontier[:width]
    return _finish_incumbent(started=started, incumbent=incumbent, stop_reason=stop_reason,
                             width=width, deadline_s=deadline, expanded_states=expanded,
                             generated_states=generated, frontier_remaining=len(frontier), exact=False)


def enumerate_tiny_routes(case, deadline: Optional[float], *,
                          target_cap: int = DEFAULT_TINY_TARGET_CAP,
                          depth_cap: Optional[int] = None,
                          node_cap: int = DEFAULT_TINY_NODE_CAP) -> dict[str, Any]:
    """Enumerate every legal physical action sequence only within explicit caps.

    This is an engineering reference for tiny fixtures, not a production
    baseline.  It can claim ``exact=True`` only after the finite action tree is
    exhausted before the deadline and node budget, with ``depth_cap >= 2*N``.
    """
    deadline = _validate_deadline(deadline)
    if (not isinstance(target_cap, int) or isinstance(target_cap, bool) or target_cap < 0 or
            not isinstance(node_cap, int) or isinstance(node_cap, bool) or node_cap < 1):
        raise ValueError("target_cap must be nonnegative and node_cap must be a positive integer")
    if depth_cap is None:
        depth_cap = 2 * target_cap
    if not isinstance(depth_cap, int) or isinstance(depth_cap, bool) or depth_cap < 0:
        raise ValueError("depth_cap must be a nonnegative integer")
    started = time.perf_counter()
    if _deadline_reached(started, deadline):
        return _base_response(started=started, failure="deadline", search_status="deadline",
                              deadline_hit=True, exact=False, target_cap=target_cap,
                              depth_cap=depth_cap, node_cap=node_cap, deadline_s=deadline)
    env = _new_env(case)
    target_count = len(env.instance.target_ids)
    if target_count > target_cap:
        return _base_response(started=started, failure="target_cap", search_status="target_cap",
                              deadline_hit=False, exact=False, target_cap=target_cap,
                              target_count=target_count, depth_cap=depth_cap,
                              node_cap=node_cap, deadline_s=deadline)
    initial = _result_from_done_env(env)
    if initial is not None:
        return _base_response(started=started, result=initial, search_status="complete",
                              deadline_hit=False, exact=depth_cap >= 2 * target_count,
                              target_cap=target_cap, target_count=target_count,
                              depth_cap=depth_cap, node_cap=node_cap, deadline_s=deadline,
                              physical_action_count=0)
    if env.terminated:
        return _base_response(started=started, failure=env.failure or "initial_terminal_rejected",
                              search_status="initial_terminal", deadline_hit=False, exact=False,
                              target_cap=target_cap, target_count=target_count,
                              depth_cap=depth_cap, node_cap=node_cap, deadline_s=deadline)

    stack: list[tuple[WeatherFullMapEnv, tuple[dict[str, Any], ...]]] = [(env, ())]
    incumbent = None
    expanded = generated = 0
    stop_reason = None
    truncated_by_depth = False
    while stack:
        if _deadline_reached(started, deadline):
            stop_reason = "deadline"
            break
        if expanded >= node_cap:
            stop_reason = "node_cap"
            break
        parent, parent_events = stack.pop()
        if len(parent_events) >= depth_cap:
            truncated_by_depth = True
            continue
        observation = parent.observation()
        legal = [action for action, allowed in zip(observation["actions"], observation["mask"]) if allowed]
        expanded += 1
        # Reverse push preserves the action's native deterministic order during DFS.
        for action in reversed(legal):
            if _deadline_reached(started, deadline):
                stop_reason = "deadline"
                break
            child = deepcopy(parent)
            _, reward, _, info = child.step(action)
            events = parent_events + (_action_receipt(action, reward, info, time.perf_counter() - started),)
            generated += 1
            if child.done:
                candidate = _consider(incumbent, child, events, time.perf_counter() - started)
                if candidate is not incumbent:
                    incumbent = candidate
            elif not child.terminated:
                stack.append((child, events))
        if stop_reason is not None:
            break
    if stop_reason is None and truncated_by_depth:
        stop_reason = "depth_cap"
    exact = stop_reason is None and depth_cap >= 2 * target_count
    response = _finish_incumbent(started=started, incumbent=incumbent, stop_reason=stop_reason,
                                 exact=exact, target_cap=target_cap, target_count=target_count,
                                 depth_cap=depth_cap, node_cap=node_cap, deadline_s=deadline,
                                 expanded_states=expanded, generated_states=generated,
                                 frontier_remaining=len(stack))
    # A complete route is a factual result; only ``exact`` certifies exhaustive
    # tiny-tree minimization under the declared M_return then MTC ordering.
    response["exact"] = exact
    return response


def exhaustive_construct(case, deadline: Optional[float], *,
                         target_cap: int = DEFAULT_TINY_TARGET_CAP,
                         depth_cap: Optional[int] = None,
                         node_cap: int = DEFAULT_TINY_NODE_CAP) -> dict[str, Any]:
    """Explicitly capped exhaustive reference for small test fixtures only."""
    return enumerate_tiny_routes(case, deadline, target_cap=target_cap,
                                 depth_cap=depth_cap, node_cap=node_cap)
