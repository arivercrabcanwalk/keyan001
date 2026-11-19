#!/usr/bin/env python3
"""EXECUTION_HOST-only full Main integration; data collection is not scientific G3."""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import re
import resource
import signal
import socket
import subprocess
import sys
import time

SOURCE_PROFILE = 'wind_adapted_fixed'

ROOT = next(p for p in Path(__file__).resolve().parents if (p / 'INPUTS.json').is_file())
sys.path.insert(0, str(ROOT / 'frozen'))
from baselines import problem, wind_scorer
from baselines.author_anchor import qualify_output

JDK = Path('/root/lunwen_engineering/20261112_takeover_completion/runtime/jdk17')
VM = ['-XX:ActiveProcessorCount=1', '-XX:+UseSerialGC', '-Xms16m', '-Xmx256m',
      '-XX:ReservedCodeCacheSize=64m', '-XX:CompressedClassSpaceSize=64m',
      '-XX:MaxMetaspaceSize=128m', '-Xss512k']
IDENTITIES = {'wind_adapted_before': ('J1b_constant_wind_single_station_guard_v1', 'AUTHOR_ALGORITHM_WIND_ADAPTED_TERMINATION_FIXED'),
              'wind_adapted_fixed': ('J1b_constant_wind_final_record_v1', 'AUTHOR_ALGORITHM_WIND_ADAPTED_FINAL_RECORD_FIXED')}


def require_host():
    assert socket.gethostname() == 'EXECUTION_HOST', 'HN01_ONLY'


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def hashes(root, suffix):
    return {str(p.relative_to(root)): sha(p) for p in sorted(root.rglob('*'))
            if p.is_file() and p.suffix == suffix}


def read(path):
    def reject(x):
        raise ValueError('nonfinite JSON: ' + x)
    return json.loads(Path(path).read_bytes(), parse_constant=reject)


def save(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, sort_keys=True, allow_nan=False) + '\n')


def execute(argv, cwd, timeout, log):
    require_host()
    before = resource.getrusage(resource.RUSAGE_CHILDREN)
    t0 = time.monotonic()
    child = subprocess.Popen(argv, cwd=cwd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    timed_out = False
    try:
        stdout, stderr = child.communicate(timeout=timeout)
    except subprocess.TimeoutExpired:
        timed_out = True
        child.kill()
        stdout, stderr = child.communicate()
    after = resource.getrusage(resource.RUSAGE_CHILDREN)
    record = dict(argv=argv, cwd=str(cwd), timeout_s=timeout, exit_status=child.returncode,
                  timed_out=timed_out, wall_s=time.monotonic() - t0,
                  child_cpu_s=after.ru_utime + after.ru_stime - before.ru_utime - before.ru_stime,
                  cumulative_child_maxrss_kib=after.ru_maxrss)
    Path(str(log) + '.stdout').write_bytes(stdout)
    Path(str(log) + '.stderr').write_bytes(stderr)
    record.update(stdout_sha256=hashlib.sha256(stdout).hexdigest(),
                  stderr_sha256=hashlib.sha256(stderr).hexdigest())
    save(Path(str(log) + '.json'), record)
    return record, stdout.decode('utf-8', errors='replace'), stderr.decode('utf-8', errors='replace')


def verify_inputs():
    conf = read(ROOT / 'INPUTS.json')
    for row in conf['rows']:
        assert sha(ROOT / row['input']) == row['input_sha256'], row['id']
    return conf


def verify_build(profile):
    lock = read(ROOT / 'SOURCE_LOCK.json')[profile]
    src = ROOT / 'frozen' / profile
    assert hashes(src, '.java') == lock['source_hashes'], 'SOURCE_HASH_MISMATCH'
    loc = ROOT / 'builds' / profile
    man = read(loc / 'BUILD_MANIFEST.json')
    assert man['identity'] == IDENTITIES[profile][0] and man['process']['exit_status'] == 0
    assert man['source_hashes'] == lock['source_hashes']
    assert hashes(loc / 'classes', '.class') == man['class_hashes'], 'CLASS_HASH_MISMATCH'
    assert man['instrumentation_hashes'] == hashes(ROOT / 'validation/java', '.java')
    assert man['java_sha256'] == sha(JDK / 'bin/java')
    assert man['javac_sha256'] == sha(JDK / 'bin/javac')
    return man


def build():
    require_host()
    verify_inputs()
    for profile in IDENTITIES:
        loc = ROOT / 'builds' / profile
        loc.mkdir(parents=True, exist_ok=False)
        classes = loc / 'classes'
        classes.mkdir()
        sources = sorted((ROOT / 'frozen' / profile).glob('*.java'))
        audit_sources = sorted((ROOT / 'validation/java').glob('*.java'))
        argv = [str(JDK / 'bin/javac'), '-J-XX:ActiveProcessorCount=1', '-J-XX:+UseSerialGC',
                '-J-Xmx256m', '-J-XX:CompressedClassSpaceSize=64m',
                '-J-XX:ReservedCodeCacheSize=64m', '-encoding', 'UTF-8', '-d', str(classes)]
        process, _, _ = execute(argv + list(map(str, sources + audit_sources)), ROOT, 8, loc / 'compile')
        man = dict(identity=IDENTITIES[profile][0], role='FULL_AUTHOR_MAIN_ENGINEERING',
                   source_hashes=hashes(ROOT / 'frozen' / profile, '.java'),
                   class_hashes=hashes(classes, '.class'),
                   instrumentation_hashes=hashes(ROOT / 'validation/java', '.java'),
                   java_sha256=sha(JDK / 'bin/java'), javac_sha256=sha(JDK / 'bin/javac'),
                   process=process)
        save(loc / 'BUILD_MANIFEST.json', man)
        verify_build(profile)
    print('BUILDS=2/2 FINAL_RECORD_INSTRUMENTATION_ONLY=true')


def final_main(stdout, instance):
    marker = '--------------------Final results-------------------'
    assert stdout.count(marker) == 1, 'FINAL_MAIN_SECTION_MISSING'
    text = stdout.split(marker, 1)[1]
    types = [None] * len(instance.stations)
    routes = [[[], []] for _ in instance.stations]
    for index, kind in re.findall(r'^Station (\d+): .* \(([012])\)$', text, re.M):
        index = int(index)
        assert 0 <= index < len(types) and types[index] is None
        types[index] = int(kind)
    assert None not in types, 'FINAL_STATION_TYPES_INCOMPLETE'
    si = di = None
    for line in text.splitlines():
        station = re.fullmatch(r'Station (\d+) Routes:', line)
        if station:
            si, di = int(station[1]) - 1, None
            assert 0 <= si < len(routes)
        elif line == '  Large Drone Routes:':
            di = 0
        elif line == '  Small Drone Routes:':
            di = 1
        elif re.match(r'    Route \d+: ', line):
            assert si is not None and di is not None, 'FINAL_ROUTE_HEADER'
            nodes = list(map(int, line.split(': ', 1)[1].split(' -> ')))
            assert len(nodes) > 2 and nodes[0] == nodes[-1] == instance.stations[si].id
            routes[si][di].append(nodes[1:-1])
    def scalar(pattern):
        values = re.findall(pattern, text, re.M)
        assert len(values) == 1, ('FINAL_METRIC_MISSING_OR_DUPLICATED', pattern)
        val = float(values[0])
        assert math.isfinite(val)
        return val
    return dict(station_types=types, routes=routes,
                objective=scalar(r'^Obj:([^\s]+)$'),
                cost=scalar(r'^Total cost: ([^\s]+)$'),
                M_return=scalar(r'^latest completion time:([^\s]+)$'))


def compare_final(raw, final, audit):
    issues = []
    if raw['station_types'] != final['station_types'] or raw['routes'] != final['routes']:
        issues.append('recorder_final_routes_mismatch')
    for a, b, label in [(raw['reference_reported_cost'], final['objective'], 'recorder_final_objective'),
                         (raw['reference_reported_cost'], final['cost'], 'recorder_final_cost'),
                         (audit['cost'], final['cost'], 'source_final_cost'),
                         (audit['M_return'], final['M_return'], 'source_final_latest_time')]:
        if not all(type(x) in (int, float) and math.isfinite(x) for x in (a, b)) or abs(a - b) > 1e-7:
            issues.append(label + '_mismatch')
    return issues


def run_row(row, out, *, seconds=0, delay_ms=0, timeout=None):
    require_host()
    begin = time.monotonic()
    out.mkdir(parents=True, exist_ok=False)
    conf = verify_inputs()
    man = verify_build(SOURCE_PROFILE)
    ins = problem.read_instance(ROOT / row['input'])
    wind = conf['wind']
    source_wind = [0, 0] if SOURCE_PROFILE == 'original_j1b' else wind
    raw_path = out / 'reference.json'
    command = [str(JDK / 'bin/java'), *VM, f'-Drepro.instance={ROOT / row["input"]}',
               f'-Drepro.seed={row["seed"]}', f'-Drepro.seconds={seconds}',
               f'-Drepro.wind.x={wind[0]}', f'-Drepro.wind.y={wind[1]}', '-Drepro.guard=true',
               f'-Drepro.output={raw_path}', f'-Dengineering.postMainDelayMillis={delay_ms}',
               '-cp', str(ROOT / 'builds' / SOURCE_PROFILE / 'classes'), 'test1.FullSolveEntry']
    save(out / 'INTENT.json', dict(input=row, profile=SOURCE_PROFILE, command=command,
                                 run_role='FULL_MAIN_ENGINEERING_NOT_SCIENTIFIC_POPULATION',
                                 seconds=seconds, post_main_delay_ms=delay_ms,
                                 timeout_s=timeout if timeout is not None else row['timeout_s']))
    proc, stdout, stderr = execute(command, out, timeout if timeout is not None else row['timeout_s'], out / 'main')
    rec = dict(id=row['id'], source_profile=SOURCE_PROFILE, input_sha256=ins.sha256,
               seed=row['seed'], process=proc, raw_exists=raw_path.exists(),
               source_manifest_sha256=wind_scorer.identity(man),
               main_returned='FULL_MAIN_RETURNED=true' in stdout,
               engineering_qualified=False, issued_cost_anchor=None, final_output_issues=[],
               scientific_G3_qualified=False, quality_ratio=None)
    if raw_path.exists():
        rec['raw_sha256'] = sha(raw_path)
        try:
            raw = read(raw_path)
            route_text = ' '.join(map(str, raw['station_types'])) + '\n'
            for si, station in enumerate(raw['routes']):
                for di, trips in enumerate(station):
                    for trip in trips:
                        route_text += ' '.join(map(str, [si, di, *trip])) + '\n'
            (out / 'witness.txt').write_text(route_text)
            audit_cmd = [str(JDK / 'bin/java'), *VM, f'-Drepro.wind.x={source_wind[0]}',
                         f'-Drepro.wind.y={source_wind[1]}', '-cp',
                         str(ROOT / 'builds' / SOURCE_PROFILE / 'classes'), 'test1.WitnessAuditMain',
                         str(ROOT / row['input']), str(out / 'witness.txt')]
            ap, ao, _ = execute(audit_cmd, out, 2, out / 'source_audit')
            assert ap['exit_status'] == 0 and not ap['timed_out'], 'SOURCE_AUDIT_FAILED'
            matches = re.findall(r'^FULL_WITNESS_AUDIT=(.+)$', ao, re.M)
            assert len(matches) == 1, 'SOURCE_AUDIT_MISSING'
            source = json.loads(matches[0])
            save(out / 'SOURCE_SCORE.json', source)
            try:
                final = final_main(stdout, ins)
                save(out / 'FINAL_MAIN.json', final)
                rec['final_output_issues'] = compare_final(raw, final, source)
            except (ValueError, AssertionError, KeyError) as e:
                rec['final_output_issues'].append(str(e))
            record = dict(anchor_identity=IDENTITIES[SOURCE_PROFILE][1],
                          run_role='FULL_MAIN_ENGINEERING_NOT_SCIENTIFIC_POPULATION',
                          source_manifest_sha256=wind_scorer.identity(man), source_hashes=man['source_hashes'],
                          raw_output_sha256=sha(raw_path), instance_sha256=ins.sha256,
                          parameter_sha256=wind_scorer.parameter_identity(ins), source_wind=source_wind,
                          source_M_return=source['M_return'], source_guard_passed=source['guard'],
                          process={'exit_status': proc['exit_status'], 'timed_out': proc['timed_out']})
            save(out / 'QUALIFICATION_RECORD.json', record)
            qualified = qualify_output(ins, raw_path.read_bytes(), record, wind=wind, verified_source_manifest=man)
            if rec['final_output_issues'] or not rec['main_returned']:
                qualified.update(source_record_qualified=False, wind_witness_qualified=False,
                                 issued_cost_anchor=None, status='FINAL_MAIN_OUTPUT_REJECTED')
                qualified['issues'] += rec['final_output_issues'] or ['full_main_not_returned']
            save(out / 'QUALIFICATION.json', qualified)
            rec['qualification_status'] = qualified['status']
            rec['engineering_qualified'] = qualified['wind_witness_qualified']
            rec['issued_cost_anchor'] = qualified['issued_cost_anchor']
            rec['source_score'] = qualified.get('source_score')
            rec['wind_score'] = qualified.get('wind_score')
        except Exception as e:
            rec['audit_exception'] = dict(type=type(e).__name__, message=str(e))
    if rec['engineering_qualified']:
        rec['status'] = 'QUALIFIED'
    elif proc['timed_out']:
        rec['status'] = 'TIMEOUT'
    elif 'WIND_INIT_NO_PROGRESS' in stderr:
        rec['status'] = 'INIT_NO_PROGRESS'
    else:
        rec['status'] = 'REJECTED'
    rec['output_ready_including_audit_serialize_s'] = time.monotonic() - begin
    save(out / 'RUN.json', rec)
    rec['total_until_saved_s'] = time.monotonic() - begin
    save(out / 'READY_RECEIPT.json', dict(total_until_saved_s=rec['total_until_saved_s'],
                                      note='Parent process exit remains included in phase TERMINAL; not 6s/12s certification'))
    return rec


def batch(out):
    require_host()
    out.mkdir(parents=True, exist_ok=False)
    conf = verify_inputs()
    rows = [run_row(row, out / row['id']) for row in conf['rows']]
    summary = dict(profile=SOURCE_PROFILE, registered=len(rows),
                   main_returned=sum(r['main_returned'] for r in rows),
                   engineering_qualified=sum(r['engineering_qualified'] for r in rows),
                   rows=[{key: r.get(key) for key in ('id', 'status', 'raw_sha256', 'engineering_qualified',
                                                     'final_output_issues', 'input_sha256', 'seed')} for r in rows])
    save(out / 'SUMMARY.json', summary)
    print('SOURCE_PROFILE=' + SOURCE_PROFILE)
    print('REGISTERED_ROWS=%d MAIN_RETURNED=%d ENGINEERING_QUALIFIED=%d' %
          (summary['registered'], summary['main_returned'], summary['engineering_qualified']))
    print('ROWS=' + ','.join(r['id'] + ':' + r['status'] for r in rows))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('action', choices=['build', 'batch'])
    parser.add_argument('--out', type=Path)
    args = parser.parse_args()
    if args.action == 'build':
        build()
    else:
        assert args.out is not None
        batch(args.out.resolve())


if __name__ == '__main__':
    main()
