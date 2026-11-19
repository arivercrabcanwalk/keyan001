"""Bounded read-only reuse of the completed A000 witness, EXECUTION_HOST only."""
from pathlib import Path
import argparse, json, os, socket, sys
assert socket.gethostname() == 'EXECUTION_HOST', 'HN01_ONLY'
BASE = Path(__file__).resolve().parent
PROBE_SOURCE = Path(os.environ.get('RECOVERY_IDENTITY_SOURCE', str(BASE)))
sys.path[:0] = [str(PROBE_SOURCE/'frozen'), str(PROBE_SOURCE)]
from baselines import problem, wind_scorer
from source_closure import sha

def check(mode):
    root = BASE.parent
    prior = root.parent/'execution_v1'
    a = json.loads((prior/'REGISTRATION.json').read_text())['authors'][0]
    out = prior/'authors'/a['short_id']/a['wind_id']
    ins = problem.read_instance(prior/'population'/a['short_id']/'instance.txt')
    solution = json.loads((out/'QUALIFIED_WIND_SOLUTION.json').read_text())
    intent = json.loads((out/'INTENT.json').read_text())
    q = json.loads((out/'QUALIFICATION.json').read_text())
    run = json.loads((out/'RUN.json').read_text())
    t = json.loads((prior/'guards/authors/A000/TERMINAL.json').read_text())
    registered = a['wind_m_per_min']
    wind = tuple(registered if mode == 'BASELINE' else map(float, registered))
    assert list(map(float, registered)) == intent['wind']
    assert run['main_returned'] and run['wind_witness_qualified']
    assert t['exit_status'] == 0 and t['budget_and_cleanup_pass']
    assert q['source_record_qualified'] and q['wind_witness_qualified']
    score = wind_scorer.score_solution(ins, solution, wind=wind)
    if mode == 'BASELINE':
        assert score['issues'] == ['physics_hash_missing_or_mismatch']
        try:
            wind_scorer.CostAnchor.from_solution(ins, solution, wind=wind)
        except ValueError as exc:
            assert str(exc) == "anchor is not a complete original-feasible witness: ['physics_hash_missing_or_mismatch']"
        else:
            raise AssertionError('ORIGINAL_ANCHOR_FAILURE_NOT_REPRODUCED')
        result = 'KNOWN_INT_FLOAT_PHYSICS_IDENTITY_FAILURE; COMPLETED_AUTHOR_NOT_RERUN'
    else:
        assert score['original_feasible'] and not score['issues']
        assert solution['physics_sha256'] == wind_scorer.physics_identity(ins, wind)
        assert wind_scorer.parameter_identity(ins) == q['wind_score']['parameter_sha256']
        assert json.loads(json.dumps(score)) == q['wind_score']
        anchor = wind_scorer.CostAnchor.from_solution(ins, solution, wind=wind)
        assert anchor.cost == q['issued_cost_anchor']['cost']
        assert anchor.makespan == q['issued_cost_anchor']['M_return']
        result = 'FLOAT_WIND_EXACT_SCORE_AND_ANCHOR_MATCH; SOLUTION_BYTES_UNCHANGED'
    record = {'mode': mode, 'probe_source': str(PROBE_SOURCE), 'input': str(out/'QUALIFIED_WIND_SOLUTION.json'),
              'input_sha256': sha(out/'QUALIFIED_WIND_SOLUTION.json'),
              'registered_wind': registered, 'evaluated_wind': list(wind),
              'saved_physics_sha256': solution['physics_sha256'],
              'evaluated_physics_sha256': score['physics_sha256'],
              'issues': score['issues'], 'result': result,
              'new_draws': 0, 'new_author_solves': 0, 'new_control_solves': 0}
    print(json.dumps(record, sort_keys=True), flush=True)
    return record

if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('--mode', choices=['BASELINE', 'MODIFIED'], required=True)
    check(p.parse_args().mode)
