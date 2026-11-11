"""Frozen weather/NFZ scenario serialization tests."""
import json
from pathlib import Path
import tempfile
import unittest

from weather_scenario_io import SCHEMA, load_weather_scenario


class WeatherScenarioIoTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.path = Path(self.temporary.name) / "scenario.json"
        self.instance_hash = "a" * 64
        self.data = {"schema": SCHEMA, "name": "frozen", "instance_sha256": self.instance_hash,
                     "wind_knots": [{"time_s": 0.0, "east_mps": 1.0, "north_mps": 0.0},
                                    {"time_s": 60.0, "east_mps": -1.0, "north_mps": 2.0}],
                     "no_fly_zone": {"vertices_m": [[0.0, 0.0], [10.0, 0.0], [0.0, 10.0]],
                                     "on_s": 10.0, "off_s": 50.0},
                     "flight": {"speed_m_per_min": 900.0, "flight_energy_per_min": 0.018}}

    def tearDown(self):
        self.temporary.cleanup()

    def write(self):
        self.path.write_text(json.dumps(self.data), encoding="utf-8")

    def test_load_binds_instance_hash_and_full_forecast(self):
        self.write()
        scenario, receipt = load_weather_scenario(self.path, expected_instance_sha256=self.instance_hash)
        self.assertEqual(scenario.name, "frozen")
        self.assertEqual(len(scenario.wind.knots), 2)
        self.assertEqual(len(scenario.no_fly_zone.vertices), 3)
        self.assertEqual(receipt["instance_sha256"], self.instance_hash)
        self.assertEqual(len(receipt["scenario_sha256"]), 64)

    def test_rejects_map_hash_mismatch_and_unknown_fields(self):
        self.write()
        with self.assertRaisesRegex(ValueError, "does not match"):
            load_weather_scenario(self.path, expected_instance_sha256="b" * 64)
        self.data["unfrozen"] = True
        self.write()
        with self.assertRaisesRegex(ValueError, "exactly"):
            load_weather_scenario(self.path)

    def test_rejects_forecast_that_does_not_cover_zero(self):
        self.data["wind_knots"][0]["time_s"] = 1.0
        self.write()
        with self.assertRaisesRegex(ValueError, "cover time zero"):
            load_weather_scenario(self.path)


if __name__ == "__main__":
    unittest.main(verbosity=2)
