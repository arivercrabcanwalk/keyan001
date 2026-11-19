"""Read saved AIR2 rows and independently re-score every complete witness."""
from copy import deepcopy
from pathlib import Path
import hashlib
import json
import socket
import sys

assert socket.gethostname() == '<COMPUTE_HOST>', '<REMOVED_ENDPOINT>_ONLY'
ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / 'frozen'))
from baselines import problem, wind_scorer
inp = json.loads((ROOT / 'INPUT.json').read_text())
fixtures = {f['id']: f for f in inp['cases']}
records = json.loads((ROOT / 'runs/MODIFIED_DETAILS.json').read_text())
checked = 0
for record in records:
    fixture = fixtures[record['fixture']]
    instance = problem.Instance(fixture['id'],
        tuple(problem.Node(j, *row) for j, row in enumerate(fixture['targets'], 1)),
        tuple(problem.Node(10001+j, *xy, 0, 0) for j, xy in enumerate(fixture['stations'])),
        hashlib.sha256(json.dumps(fixture, sort_keys=True).encode()).hexdigest(), problem.Parameters())
    anchor = problem.empty_solution(instance, fixture['types'])
    anchor['routes'] = fixture['routes']
    anchor['physics_sha256'] = wind_scorer.physics_identity(instance, tuple(inp['wind']))
    for st in record['stations']:
        si = st['station']
        for row in st['rows']:
            replacement = []
            for k, (done, prefix, suffix, future) in enumerate(row['station']):
                trips = done + ([prefix+suffix] if prefix or suffix else []) + future
                assert all(len(trip) <= (4, 3)[k] for trip in trips)
                assert [done, prefix] == st['input_station'][k][:2]
                replacement.append(trips)
            solution = deepcopy(anchor)
            solution['routes'][si] = replacement
            score = wind_scorer.score_solution(instance, solution, wind=tuple(inp['wind']))
            assert score['original_feasible']
            expected = row['score']
            assert score['cost'] == expected['full_single_replacement_cost']
            duties = [r['duty_min'] for r in score['slot_duty'] if r['station'] == si]
            assert duties == expected['duties'] and max(duties) == expected['local_M']
            checked += 1
result = {'status': 'ALL_SAVED_FULL_WITNESSES_RESCORING_PASS',
          'rows_rechecked_including_cross_prefix_repeats': checked,
          'configurations': len(records), 'scientific_qualification': False}
(ROOT / 'runs/AUDIT.json').write_text(json.dumps(result, indent=2) + '\n')
print(json.dumps(result, sort_keys=True))
