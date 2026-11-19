"""Synthetic adversarial tests for the time-dependent weather route oracle."""

import unittest

from weather_oracle import (
    FlightParams,
    NoFlyZone,
    Point,
    WindField,
    WindInfeasibleError,
    WindKnot,
    integrate_leg,
    plan_route,
)


def calm(start_s=0.0):
    return WindField((WindKnot(start_s, 0.0, 0.0),))


def square_zone(on_s, off_s, y0=-1.0, y1=1.0):
    return NoFlyZone((Point(4.0, y0), Point(6.0, y0),
                      Point(6.0, y1), Point(4.0, y1)), on_s, off_s)


class WindKinematicsTests(unittest.TestCase):
    def setUp(self):
        self.p = FlightParams(speed=60.0, flight_energy=0.018)
        self.a = Point(0.0, 0.0)
        self.b = Point(10.0, 0.0)

    def test_project_calm_defaults_keep_900_m_per_min_and_abstract_energy(self):
        p = FlightParams()
        self.assertEqual(p.speed, 900.0)
        self.assertEqual(p.airspeed_mps, 15.0)
        self.assertEqual(p.flight_energy, 0.018)
        segment = integrate_leg(Point(0.0, 0.0), Point(900.0, 0.0), 0.0, calm(), p)
        self.assertAlmostEqual(segment.arrival_time_s, 60.0)
        self.assertAlmostEqual(segment.energy, 0.018)

    def test_tailwind_headwind_and_crosswind_track_speed(self):
        tail = integrate_leg(self.a, self.b, 0.0,
                             WindField((WindKnot(0.0, 0.5, 0.0),)), self.p)
        head = integrate_leg(self.a, self.b, 0.0,
                             WindField((WindKnot(0.0, -0.25, 0.0),)), self.p)
        cross = integrate_leg(self.a, self.b, 0.0,
                              WindField((WindKnot(0.0, 0.0, 0.6),)), self.p)
        self.assertAlmostEqual(tail.arrival_time_s, 10.0 / 1.5)
        self.assertAlmostEqual(head.arrival_time_s, 10.0 / 0.75)
        self.assertAlmostEqual(cross.arrival_time_s, 10.0 / 0.8)

    def test_crosswind_infeasibility_and_nonpositive_progress_fail(self):
        with self.assertRaisesRegex(WindInfeasibleError, "crosswind_infeasible"):
            integrate_leg(self.a, self.b, 0.0,
                          WindField((WindKnot(0.0, 0.0, 1.01),)), self.p)
        with self.assertRaisesRegex(WindInfeasibleError, "nonpositive_progress"):
            integrate_leg(self.a, self.b, 0.0,
                          WindField((WindKnot(0.0, -1.0, 0.0),)), self.p)

    def test_exact_integration_across_time_bin(self):
        field = WindField((WindKnot(0.0, 0.0, 0.0),
                            WindKnot(4.0, 1.0, 0.0)))
        segment = integrate_leg(self.a, self.b, 0.0, field, self.p)
        self.assertAlmostEqual(segment.arrival_time_s, 7.0)
        self.assertAlmostEqual(segment.energy, 0.018 * 7.0 / 60.0)

    def test_crosswind_failure_after_a_knot_does_not_get_hidden(self):
        field = WindField((WindKnot(0.0, 0.0, 0.0),
                            WindKnot(4.0, 0.0, 1.01)))
        with self.assertRaisesRegex(WindInfeasibleError, "crosswind_infeasible"):
            integrate_leg(self.a, self.b, 0.0, field, self.p)


class NoFlyRoutingTests(unittest.TestCase):
    def setUp(self):
        self.params = FlightParams(speed=60.0, flight_energy=0.018)
        self.start = Point(0.0, 0.0)
        self.end = Point(10.0, 0.0)
        self.wind = calm()

    def test_direct_route_before_on_and_after_closure(self):
        zone = square_zone(10.0, 20.0)
        before = plan_route(self.start, self.end, 3.0, self.wind, self.params, zone)
        on = plan_route(self.start, self.end, 6.0, self.wind, self.params, zone)
        after = plan_route(self.start, self.end, 16.0, self.wind, self.params, zone)
        self.assertTrue(before.legal)
        self.assertEqual(before.polyline, (self.start, self.end))
        self.assertTrue(on.legal)
        self.assertNotEqual(on.polyline, (self.start, self.end))
        self.assertTrue(after.legal)
        self.assertEqual(after.polyline, (self.start, self.end))

    def test_active_inactive_and_half_open_closure_boundaries(self):
        entry_at_off = plan_route(self.start, self.end, 0.0, self.wind, self.params,
                                  square_zone(0.0, 4.0))
        exit_at_on = plan_route(self.start, self.end, 0.0, self.wind, self.params,
                                square_zone(6.0, 8.0))
        exact_crossing = plan_route(self.start, self.end, 0.0, self.wind, self.params,
                                    square_zone(4.0, 6.0))
        inactive = plan_route(self.start, self.end, 0.0, self.wind, self.params,
                              square_zone(0.0, 3.0))
        self.assertEqual(entry_at_off.polyline, (self.start, self.end))
        self.assertEqual(exit_at_on.polyline, (self.start, self.end))
        self.assertEqual(inactive.polyline, (self.start, self.end))
        self.assertNotEqual(exact_crossing.polyline, (self.start, self.end))

    def test_tangent_edge_is_legal_but_inside_edge_is_rejected_when_active(self):
        tangent_zone = square_zone(0.0, 30.0, y0=0.0, y1=2.0)
        tangent = plan_route(self.start, self.end, 0.0, self.wind, self.params,
                             tangent_zone)
        inside = plan_route(self.start, self.end, 0.0, self.wind, self.params,
                            square_zone(0.0, 30.0))
        self.assertEqual(tangent.polyline, (self.start, self.end))
        self.assertTrue(inside.legal)
        self.assertNotEqual(inside.polyline, (self.start, self.end))

    def test_active_zone_routes_around_polygon_vertices(self):
        result = plan_route(self.start, self.end, 0.0, self.wind, self.params,
                            square_zone(0.0, 100.0))
        self.assertTrue(result.legal)
        self.assertEqual(result.polyline[0], self.start)
        self.assertEqual(result.polyline[-1], self.end)
        self.assertEqual(len(result.polyline), 4)
        self.assertGreater(result.distance_m, 10.0)
        self.assertTrue(all(s.arrival_time_s > s.departure_time_s for s in result.segments))

    def test_equal_arrival_detours_use_stable_vertex_order_tie_break(self):
        result = plan_route(self.start, self.end, 0.0, self.wind, self.params,
                            square_zone(0.0, 100.0))
        self.assertEqual(result.polyline[1], Point(4.0, -1.0))
        self.assertEqual(result.polyline[2], Point(6.0, -1.0))

    def test_segment_times_are_contiguous_without_implicit_waiting(self):
        result = plan_route(self.start, self.end, 0.0, self.wind, self.params,
                            square_zone(0.0, 100.0))
        for previous, following in zip(result.segments, result.segments[1:]):
            self.assertEqual(following.departure_time_s, previous.arrival_time_s)
        self.assertEqual(result.arrival_time_s, result.segments[-1].arrival_time_s)
        self.assertAlmostEqual(result.energy,
                               sum(segment.energy for segment in result.segments))
        self.assertAlmostEqual(result.distance_m,
                               sum(segment.distance_m for segment in result.segments))

    def test_no_legal_path_reports_failure_for_wind_infeasibility(self):
        field = WindField((WindKnot(0.0, 0.0, 2.0),))
        result = plan_route(self.start, self.end, 0.0, field, self.params)
        self.assertFalse(result.legal)
        self.assertIsNone(result.arrival_time_s)
        self.assertIn("crosswind_infeasible", result.rejection_reasons)


if __name__ == "__main__":
    unittest.main()
