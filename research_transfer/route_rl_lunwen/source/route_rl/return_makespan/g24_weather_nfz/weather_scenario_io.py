"""Strict, hashable serialization for frozen weather/NFZ scenarios."""
from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path

from weather_full_map import MAX_NFZ_VERTICES, MAX_WIND_KNOTS, WeatherMapScenario
from weather_oracle import FlightParams, NoFlyZone, Point, WindField, WindKnot


SCHEMA = "weather_map_scenario_v1"


def _canonical_json(value) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")


def _read_json(path: Path):
    def reject_constant(token):
        raise ValueError(f"non-finite JSON value: {token}")
    return json.loads(path.read_text(encoding="utf-8"), parse_constant=reject_constant)


def _finite_number(value, field: str) -> float:
    if type(value) not in (int, float) or not math.isfinite(value):
        raise ValueError(f"{field} must be a finite number")
    return float(value)


def _exact_keys(value: dict, expected: set[str], context: str) -> None:
    if not isinstance(value, dict) or set(value) != expected:
        raise ValueError(f"{context} must have exactly {sorted(expected)}")


def load_weather_scenario(path: Path, *, expected_instance_sha256: str | None = None):
    """Load a full-forecast scenario and return `(scenario, immutable_receipt)`.

    The serial form intentionally carries an instance hash. It avoids silently
    applying a frozen forecast/NFZ polygon to another map.
    """
    path = Path(path).resolve()
    raw = _read_json(path)
    _exact_keys(raw, {"schema", "name", "instance_sha256", "wind_knots", "no_fly_zone", "flight"},
                "scenario")
    if raw["schema"] != SCHEMA:
        raise ValueError(f"unsupported scenario schema: {raw['schema']!r}")
    if not isinstance(raw["name"], str) or not raw["name"]:
        raise ValueError("scenario name must be nonempty")
    instance_hash = raw["instance_sha256"]
    if not isinstance(instance_hash, str) or len(instance_hash) != 64 or any(ch not in "0123456789abcdef" for ch in instance_hash):
        raise ValueError("instance_sha256 must be a lowercase SHA-256")
    if expected_instance_sha256 is not None and instance_hash != expected_instance_sha256:
        raise ValueError("scenario instance_sha256 does not match the supplied map")
    if not isinstance(raw["wind_knots"], list) or not raw["wind_knots"]:
        raise ValueError("wind_knots must be a nonempty list")
    if len(raw["wind_knots"]) > MAX_WIND_KNOTS:
        raise ValueError(f"scenario exceeds {MAX_WIND_KNOTS} wind-knot policy limit")
    knots = []
    for index, knot in enumerate(raw["wind_knots"]):
        _exact_keys(knot, {"time_s", "east_mps", "north_mps"}, f"wind_knots[{index}]")
        knots.append(WindKnot(_finite_number(knot["time_s"], f"wind_knots[{index}].time_s"),
                              _finite_number(knot["east_mps"], f"wind_knots[{index}].east_mps"),
                              _finite_number(knot["north_mps"], f"wind_knots[{index}].north_mps")))
    _exact_keys(raw["flight"], {"speed_m_per_min", "flight_energy_per_min"}, "flight")
    flight = FlightParams(_finite_number(raw["flight"]["speed_m_per_min"], "flight.speed_m_per_min"),
                          _finite_number(raw["flight"]["flight_energy_per_min"], "flight.flight_energy_per_min"))
    zone_raw = raw["no_fly_zone"]
    zone = None
    if zone_raw is not None:
        _exact_keys(zone_raw, {"vertices_m", "on_s", "off_s"}, "no_fly_zone")
        vertices = zone_raw["vertices_m"]
        if not isinstance(vertices, list) or len(vertices) > MAX_NFZ_VERTICES:
            raise ValueError(f"no_fly_zone supports 3..{MAX_NFZ_VERTICES} vertices")
        points = []
        for index, vertex in enumerate(vertices):
            if not isinstance(vertex, list) or len(vertex) != 2:
                raise ValueError(f"no_fly_zone.vertices_m[{index}] must be [x_m, y_m]")
            points.append(Point(_finite_number(vertex[0], f"no_fly_zone.vertices_m[{index}][0]"),
                                _finite_number(vertex[1], f"no_fly_zone.vertices_m[{index}][1]")))
        zone = NoFlyZone(tuple(points), _finite_number(zone_raw["on_s"], "no_fly_zone.on_s"),
                         _finite_number(zone_raw["off_s"], "no_fly_zone.off_s"))
    scenario = WeatherMapScenario(WindField(tuple(knots)), zone, flight, raw["name"])
    receipt = {"schema": SCHEMA, "path": str(path), "scenario_sha256": hashlib.sha256(_canonical_json(raw)).hexdigest(),
               "instance_sha256": instance_hash, "name": raw["name"], "wind_knot_count": len(knots),
               "nfz_vertex_count": 0 if zone is None else len(zone.vertices), "canonical": raw}
    return scenario, receipt
