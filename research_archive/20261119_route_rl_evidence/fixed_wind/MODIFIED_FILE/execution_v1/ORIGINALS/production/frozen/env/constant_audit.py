"""Independent constant-wind route replay, using heading angles.

No engine, constant_wind helper, policy, matrix or cached time is imported.
Complete static TARGET/RETURN action logs only. Energy includes the return leg.
"""
from collections import Counter
import math


def heading_leg(origin, destination, wind, airspeed):
    dx, dy = destination[0] - origin[0], destination[1] - origin[1]
    length = math.hypot(dx, dy)
    if length == 0:
        return 0.0
    wind_speed = math.hypot(*wind)
    if wind_speed >= airspeed:
        raise ValueError("no nonzero closed tour")
    course, wind_angle = math.atan2(dy, dx), math.atan2(wind[1], wind[0])
    heading = course - math.asin(wind_speed / airspeed * math.sin(wind_angle - course))
    vx = airspeed * math.cos(heading) + wind[0]
    vy = airspeed * math.sin(heading) + wind[1]
    along = vx * math.cos(course) + vy * math.sin(course)
    if along <= 0:
        raise ValueError("no forward ground speed")
    return length / along


def audit_episode(static, wind, receipt, tolerance=1e-9):
    slots = {key: {"xy": (static.stations[key[0]].x, static.stations[key[0]].y),
                   "ready": 0.0, "duty": 0.0, "energy": 0.0,
                   "home": True} for key in static.slots()}
    seen, served, trips = Counter(), {}, []
    previous_t = -math.inf
    for row in receipt["actions"]:
        t, si, sj, kind, tid = row[:5]
        if t < previous_t - tolerance:
            raise ValueError("global dispatch time regression")
        previous_t = t
        key = si, sj
        if key not in slots:
            raise ValueError("unknown slot")
        state = slots[key]
        if t < state["ready"] - tolerance:
            raise ValueError("dispatch before previous completion")
        home = static.stations[si]
        if kind == "TARGET":
            if tid not in static.target_ids or static.station_of_target(tid) != si:
                raise ValueError("target ownership")
            node = static.nodes[tid]
            if math.hypot(node.x - home.x, node.y - home.y) > static.params.radius(
                    static.station_types[si]) + 1e-7:
                raise ValueError("original coordinate coverage")
            duration = heading_leg(state["xy"], (node.x, node.y), wind,
                                   static.params.speed)
            state["energy"] += duration * static.params.flight_energy + node.energy
            state["duty"] += duration + node.service
            state["ready"] = t + duration + node.service
            state["xy"], state["home"] = (node.x, node.y), False
            seen[tid] += 1
            served[tid] = state["ready"]
        elif kind == "RETURN":
            if state["home"]:
                raise ValueError("return from home")
            duration = heading_leg(state["xy"], (home.x, home.y), wind,
                                   static.params.speed)
            state["energy"] += duration * static.params.flight_energy
            state["duty"] += duration
            state["ready"] = t + duration
            trips.append({"slot": list(key), "energy": state["energy"],
                          "returned_at": state["ready"]})
            state["xy"], state["home"] = (home.x, home.y), True
        else:
            raise ValueError("nonphysical action")
        if state["energy"] > static.params.battery(sj) + 1e-12:
            raise ValueError("trip battery including return")
        if state["duty"] > static.params.duty_limit(static.station_types[si]) + 1e-7:
            raise ValueError("cumulative duty")
        if kind == "RETURN":
            state["energy"] = 0.0
    if any(seen[t] != 1 for t in static.target_ids) or any(
            not s["home"] for s in slots.values()):
        raise ValueError("incomplete service or return")
    fixed = sum(0.0 if k == 0 else 27.8 if k == 1 else 43.4
                for k in static.station_types)
    operating = sum(s["duty"] for s in slots.values())
    maximum = max(s["duty"] for s in slots.values())
    expected = {"M_return": maximum, "operating_minutes": operating,
                "cost": fixed + static.params.time_cost * operating}
    checks = {name: math.isclose(value, receipt["metrics"][name],
                                 rel_tol=tolerance, abs_tol=tolerance)
              for name, value in expected.items()}
    checks["served"] = (set(served) == {int(t) for t, _ in receipt["served"]}
                         and all(math.isclose(served[int(t)], at, rel_tol=tolerance,
                                               abs_tol=tolerance)
                                 for t, at in receipt["served"]))
    direct = sorted(trips, key=lambda r: (*r["slot"], r["returned_at"]))
    recorded = sorted(receipt["return_energy_ledger"],
                      key=lambda r: (r["station"], r["slot"], r["arrived_at"]))
    checks["return_energy"] = (len(direct) == len(recorded)
                               and all(a["slot"] == [b["station"], b["slot"]]
                                       and math.isclose(a["returned_at"], b["arrived_at"],
                                                        rel_tol=tolerance, abs_tol=tolerance)
                                       and math.isclose(a["energy"], b["total_trip_energy"],
                                                        rel_tol=tolerance, abs_tol=tolerance)
                                       for a, b in zip(direct, recorded)))
    return {"ok": all(checks.values()), "checks": checks,
            "recomputed": expected, "trips": trips}
