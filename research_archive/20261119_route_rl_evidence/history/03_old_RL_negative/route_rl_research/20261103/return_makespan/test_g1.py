"""Synthetic engineering tests only; no research maps or scientific solvers."""
import copy
from dataclasses import replace
import hashlib
import json
from pathlib import Path
import sys
import unittest

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(ROOT / 'route_rl_research/20261103/source_snapshot'))
sys.path.insert(0, str(HERE))
from lrphsd.problem import Instance, Node, Parameters, empty_solution
from lrphsd.evaluator import evaluate
from scorer import CostAnchor, cost_within_cap, score_solution, validate_candidate
from global_env import FullMapRouteEnv, IllegalAction, RouteAction, StationRouteEnv
from delivery import finalize_result


def small_instance(**changes):
    p = dict(speed=100., flight_energy=.1, small_battery=.8, large_battery=1.,
             small_radius=1000., large_radius=1000., small_duration=20., large_duration=20.)
    p.update(changes)
    return Instance('synthetic', (Node(1,100.,0.,.01,1.), Node(2,200.,0.,.01,1.)),
                    (Node(0,0.,0.,0.,0.),), hashlib.sha256(b'synthetic').hexdigest(), Parameters(**p))


def solution(ins, types, routes):
    sol = empty_solution(ins, types)
    sol['routes'] = copy.deepcopy(routes)
    return sol


def fixture(index=0):
    raw = json.loads((HERE / 'agents/audit/FIXTURES.json').read_text())['cases'][index]
    ins = Instance(raw['name'], tuple(Node(*n) for n in raw['targets']),
                   tuple(Node(*n) for n in raw['stations']),
                   hashlib.sha256(json.dumps(raw, sort_keys=True).encode()).hexdigest(),
                   Parameters(**raw['parameters']))
    return ins, solution(ins,raw['station_types'],raw['anchor_routes']), raw


def replay(env, full):
    for si in env.station_order:
        for d in env.station_envs[si].slots:
            for trip in full['routes'][si][d]:
                for nid in trip:
                    env.step(RouteAction(d,nid))
                if trip:
                    env.step(RouteAction(d))
    return env.result()


def fakeclock(*values):
    vals = iter(values)
    return lambda: next(vals)


class ScorerTests(unittest.TestCase):
    def test_parallel_clock_and_all_completion_metrics(self):
        ins,sol,raw = fixture()
        got = score_solution(ins,sol); want=raw['expected_anchor']
        self.assertTrue(got['original_feasible'],got['issues'])
        for a,b in [('operating_minutes','operating_minutes'),('fixed_cost','fixed_cost'),
                    ('cost','cost'),('M_return','M_return'),('M_service','M_service'),
                    ('mean_target_completion','mean_completion'),
                    ('p90_target_completion_nearest_rank','p90_completion_nearest_rank')]:
            self.assertAlmostEqual(got[a],want[b])
        self.assertEqual({str(k):v for k,v in got['target_completion'].items()},want['completion_by_target'])

    def test_original_evaluator_same_cost_and_feasibility(self):
        for i in (0,1):
            ins,sol,raw=fixture(i)
            for routes in (raw['anchor_routes'],raw['candidate_routes']):
                sol['routes']=routes
                old=evaluate(ins,sol); new=score_solution(ins,sol)
                self.assertEqual(old['feasible'],new['original_feasible'])
                self.assertAlmostEqual(old['cost'],new['cost'])
                self.assertAlmostEqual(old['operating_minutes'],new['operating_minutes'])

    def test_final_return_is_not_service_completion(self):
        ins=small_instance(); sol=solution(ins,[2],[[[[1]],[[2]]]])
        got=score_solution(ins,sol)
        self.assertEqual(got['M_return'],5.)
        self.assertEqual(got['M_service'],3.)

    def test_global_cap_allows_local_cost_increase(self):
        ins,sol,raw=fixture(1); anchor=CostAnchor.from_solution(ins,sol)
        sol['routes']=raw['candidate_routes']; got=validate_candidate(ins,sol,anchor)
        self.assertTrue(got['admissible'],got)
        self.assertAlmostEqual(got['cost'],anchor.cost)
        self.assertEqual(got['M_return'],4.)
        self.assertGreater(raw['expected_candidate']['station_operating_minutes'][0],
                           raw['expected_anchor']['station_operating_minutes'][0])

    def test_target_station_fixed_even_with_coverage(self):
        ins,sol,_=fixture(); anchor=CostAnchor.from_solution(ins,sol)
        sol['routes'][0][0][0]=[1,3]; sol['routes'][1][1]=[]
        got=validate_candidate(ins,sol,anchor)
        self.assertIn('fixed_target_station_changed',got['domain_issues'])
        self.assertFalse(got['admissible'])

    def test_slot_assignment_can_change(self):
        ins,sol,raw=fixture(); anchor=CostAnchor.from_solution(ins,sol)
        sol['routes']=raw['candidate_routes']
        self.assertTrue(validate_candidate(ins,sol,anchor)['admissible'])

    def test_station_type_cannot_change(self):
        ins,sol,_=fixture(); anchor=CostAnchor.from_solution(ins,sol)
        sol['station_types'][0]=1
        self.assertIn('fixed_station_types_changed',validate_candidate(ins,sol,anchor)['domain_issues'])

    def test_small_station_rejects_large_slot(self):
        ins=small_instance(); sol=solution(ins,[1],[[[[1,2]],[]]])
        self.assertIn('large_drone_at_small_station:0',score_solution(ins,sol)['issues'])

    def test_closed_station_rejected(self):
        ins=small_instance(); sol=solution(ins,[0],[[[],[[1,2]]]])
        self.assertIn('closed_station:0',score_solution(ins,sol)['issues'])

    def test_cumulative_duty_not_per_trip(self):
        ins=small_instance(small_duration=7.)
        sol=solution(ins,[1],[[[],[[1],[2]]]])
        self.assertIn('cumulative_duty:0:1',score_solution(ins,sol)['issues'])

    def test_sd_at_dabs_uses_dabs_duration(self):
        ins=small_instance(small_duration=7.,large_duration=20.)
        sol=solution(ins,[2],[[[],[[1],[2]]]])
        self.assertTrue(score_solution(ins,sol)['original_feasible'])

    def test_trip_energy_not_outbound_only(self):
        ins=small_instance(small_battery=.2)
        sol=solution(ins,[1],[[[],[[1,2]]]])
        self.assertIn('energy:0:1:0',score_solution(ins,sol)['issues'])

    def test_coverage_checked(self):
        ins=small_instance(small_radius=150.,large_radius=1000.)
        sol=solution(ins,[1],[[[],[[1,2]]]])
        self.assertIn('coverage:2',score_solution(ins,sol)['issues'])

    def test_duplicate_missing_bool_float_and_malformed_fail(self):
        ins=small_instance()
        for trips in ([[1,1]],[[1]],[[True,2]],[[1.,2]],['bad']):
            with self.subTest(trips=trips):
                sol=solution(ins,[1],[[[],trips]])
                self.assertFalse(score_solution(ins,sol)['original_feasible'])
        for value in (None,[],{}, {'station_types':[True],'routes':[[[],[]]]}):
            self.assertFalse(score_solution(ins,value)['original_feasible'])

    def test_empty_trips_ignored_but_counted(self):
        ins=small_instance(); sol=solution(ins,[1],[[[],[[],[1,2],[]]]])
        got=score_solution(ins,sol)
        self.assertTrue(got['original_feasible']); self.assertEqual(got['ignored_empty_trip_count'],2)

    def test_hash_missing_or_wrong_rejected(self):
        ins=small_instance(); sol=solution(ins,[1],[[[],[[1,2]]]])
        for value in (None,'0'*64):
            sol['instance_sha256']=value
            self.assertFalse(score_solution(ins,sol)['original_feasible'])

    def test_nan_inf_input_rejected(self):
        ins=small_instance(); sol=solution(ins,[1],[[[],[[1,2]]]])
        for value in (float('nan'),float('inf')):
            sol['extra']=value
            self.assertFalse(score_solution(ins,sol)['original_feasible'])

    def test_distance_cache_not_used(self):
        ins,sol,_=fixture(); before=score_solution(ins,sol)
        ins.dist={k:0. for k in ins.dist}
        after=score_solution(ins,sol)
        self.assertEqual(before['cost'],after['cost'])
        self.assertEqual(before['M_return'],after['M_return'])

    def test_anchor_immutable_and_fields_reverified(self):
        ins,sol,_=fixture(); anchor=CostAnchor.from_solution(ins,sol)
        sol['routes'][0][0].clear(); anchor.solution()['routes'].clear()
        anchor.verify(ins)
        with self.assertRaises(ValueError): replace(anchor,cost=0.).verify(ins)
        with self.assertRaises(ValueError): replace(anchor,parameter_sha256='bad').verify(ins)

    def test_absolute_tolerance_and_nonfinite_cap(self):
        self.assertTrue(cost_within_cap(1e6+5e-8,1e6))
        self.assertFalse(cost_within_cap(1e6+2e-7,1e6))
        for value in (float('nan'),float('inf'),-1.,True):
            self.assertFalse(cost_within_cap(value,10.))


class EnvironmentTests(unittest.TestCase):
    def test_complete_reward_is_negative_global_makespan(self):
        ins,sol,_=fixture(); env=FullMapRouteEnv(ins,sol)
        got=replay(env,sol)
        self.assertEqual(got['reward'],-8.)
        self.assertEqual(got['score']['M_return'],8.)
        self.assertNotEqual(got['reward'],-got['score']['operating_minutes'])

    def test_station_decode_order_does_not_create_waiting(self):
        ins,sol,_=fixture()
        a=replay(FullMapRouteEnv(ins,sol,station_order=(0,1)),sol)
        b=replay(FullMapRouteEnv(ins,sol,station_order=(1,0)),sol)
        self.assertEqual(a['score']['target_completion'],b['score']['target_completion'])
        self.assertEqual(a['score']['M_return'],b['score']['M_return'])
        self.assertEqual(a['reward'],b['reward'])

    def test_global_compensation_route_is_not_pruned_by_local_cap(self):
        ins,sol,raw=fixture(1); env=FullMapRouteEnv(ins,sol)
        sol['routes']=raw['candidate_routes']; got=replay(env,sol)
        self.assertEqual(got['score']['M_return'],4.)
        self.assertTrue(got['score']['admissible'])

    def test_illegal_and_untyped_action_is_nonmutating(self):
        ins,sol,_=fixture(); env=FullMapRouteEnv(ins,sol)
        before=copy.deepcopy(env.observation())
        for action in (RouteAction(0),RouteAction(True,1),RouteAction(0,True),RouteAction(0,999)):
            self.assertFalse(env.legal(action))
            with self.assertRaises(IllegalAction):env.step(action)
            self.assertEqual(env.observation(),before)

    def test_done_requires_return(self):
        ins=small_instance(); sol=solution(ins,[2],[[[[1,2]],[]]])
        env=FullMapRouteEnv(ins,sol)
        env.step(RouteAction(0,1));env.step(RouteAction(0,2))
        self.assertFalse(env.done)
        env.step(RouteAction(0));self.assertTrue(env.done)

    def test_explicit_dead_end_not_completion_certificate(self):
        ins=small_instance(small_duration=6.5)
        sol=solution(ins,[1],[[[],[[1,2]]]])
        env=FullMapRouteEnv(ins,sol)
        env.step(RouteAction(1,1)); obs,_,terminated,info=env.step(RouteAction(1))
        self.assertTrue(terminated);self.assertTrue(obs['dead_end']);self.assertFalse(env.done)
        self.assertFalse(obs['necessary_mask_is_completion_certificate'])
        self.assertEqual(info['failure'],'dead_end')
        with self.assertRaises(RuntimeError):env.result()
        with self.assertRaises(RuntimeError):env.candidate()

    def test_disabled_cost_mask_still_rejects_terminal_cap_violation(self):
        ins=small_instance();sol=solution(ins,[1],[[[],[[1,2]]]])
        env=FullMapRouteEnv(ins,sol,use_necessary_cost_mask=False)
        for act in (RouteAction(1,1),RouteAction(1),RouteAction(1,2),RouteAction(1)):
            obs,_,_,info=env.step(act)
        self.assertTrue(env.done);self.assertEqual(obs['status'],'COMPLETE_INVALID')
        self.assertFalse(info['terminal_score']['cost_cap_satisfied'])
        self.assertFalse(info['reward_is_complete_objective'])
        self.assertEqual(env.candidate()['routes'],[[[],[[1],[2]]]])
        with self.assertRaises(RuntimeError):env.result()

    def test_active_cost_mask_prunes_known_overcap_prefix(self):
        ins=small_instance();sol=solution(ins,[1],[[[],[[1,2]]]])
        env=FullMapRouteEnv(ins,sol)
        env.step(RouteAction(1,1));env.step(RouteAction(1))
        self.assertFalse(env.legal(RouteAction(1,2)))
        self.assertTrue(env.dead_end)

    def test_return_preserves_duty_and_resets_energy(self):
        ins,sol,_=fixture();env=FullMapRouteEnv(ins,sol)
        env.step(RouteAction(0,1));env.step(RouteAction(0))
        local=env.station_envs[0]
        self.assertEqual(local.cumulative_duty[0],3.)
        self.assertEqual(local.trip_energy[0],0.)
        self.assertEqual(local.trip_elapsed[0],0.)

    def test_old_station_api_remains_cost_based(self):
        ins=small_instance();env=StationRouteEnv(ins,0,2,(1,2))
        for action in (RouteAction(0,1),RouteAction(0),RouteAction(1,2),RouteAction(1)):
            env.step(action)
        self.assertEqual(env.result()['reward'],-4.)


class DeliveryTests(unittest.TestCase):
    def test_valid_ontime_delivery(self):
        ins,sol,_=fixture();anchor=CostAnchor.from_solution(ins,sol)
        got=finalize_result(ins,sol,anchor,started_at=100.,budget_s=1.,clock=fakeclock(100.,100.1,100.2))
        self.assertTrue(got['ontime_valid_output']);self.assertFalse(got['fallback_used'])
        self.assertFalse(got['anchor_generation_included'])

    def test_raw_failure_preserved_and_fallback_charged(self):
        ins,sol,_=fixture();anchor=CostAnchor.from_solution(ins,sol)
        bad=copy.deepcopy(sol);bad['routes'][0][0]=[]
        got=finalize_result(ins,bad,anchor,started_at=100.,budget_s=1.,clock=fakeclock(100.,100.1,100.4,100.5))
        self.assertTrue(got['fallback_used']);self.assertEqual(got['raw_solution'],bad)
        self.assertFalse(got['raw_score']['admissible'])
        self.assertAlmostEqual(got['fallback_validation_finished_elapsed_s'],.4)

    def test_late_raw_and_fallback_are_not_ontime(self):
        ins,sol,_=fixture();anchor=CostAnchor.from_solution(ins,sol)
        got=finalize_result(ins,sol,anchor,started_at=100.,budget_s=1.,clock=fakeclock(100.,101.1,101.2,101.3))
        self.assertFalse(got['ontime_valid_output']);self.assertIsNone(got['chosen_solution'])
        self.assertEqual(got['fallback_reason'],'raw_validation_late')

    def test_record_assembly_time_counts(self):
        ins,sol,_=fixture();anchor=CostAnchor.from_solution(ins,sol)
        got=finalize_result(ins,sol,anchor,started_at=100.,budget_s=1.,clock=fakeclock(100.,100.1,101.1))
        self.assertFalse(got['ontime_valid_output'])

    def test_fallback_validation_time_counts(self):
        ins,sol,_=fixture();anchor=CostAnchor.from_solution(ins,sol)
        got=finalize_result(ins,None,anchor,started_at=100.,budget_s=1.,clock=fakeclock(100.,100.1,101.1,101.2))
        self.assertTrue(got['fallback_attempted']);self.assertFalse(got['fallback_used'])
        self.assertFalse(got['ontime_valid_output'])

    def test_worse_admissible_candidate_falls_back(self):
        ins,sol,raw=fixture();worse=copy.deepcopy(sol)
        sol['routes']=raw['candidate_routes'];anchor=CostAnchor.from_solution(ins,sol)
        got=finalize_result(ins,worse,anchor,started_at=100.,budget_s=1.,clock=fakeclock(100.,100.1,100.2,100.3))
        self.assertTrue(got['raw_score']['admissible'])
        self.assertEqual(got['fallback_reason'],'raw_worse_than_anchor')
        self.assertTrue(got['fallback_used'])

    def test_nonmonotonic_clock_rejected(self):
        ins,sol,_=fixture();anchor=CostAnchor.from_solution(ins,sol)
        with self.assertRaises(ValueError):
            finalize_result(ins,sol,anchor,started_at=100.,budget_s=1.,clock=fakeclock(100.2,100.1))


if __name__=='__main__':
    unittest.main(verbosity=2)
