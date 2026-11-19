from pathlib import Path
import subprocess
import sys
import fullsolve_driver as d

ROOT = d.ROOT
CASES = ('equal', 'tiny', 'improve')


def probes(profile, out, classes=None):
    out.mkdir(parents=True, exist_ok=False)
    if classes is None:
        d.verify_build(profile)
        classes = ROOT / 'builds' / profile / 'classes'
    rows = {}
    for name in CASES:
        command = [str(d.JDK / 'bin/java'), *d.VM, '-Drepro.seed=2026111302',
                   '-Drepro.output=' + str(out / (name + '.raw.json')), '-cp', str(classes),
                   'test1.FinalRecorderProbe', name]
        process, stdout, stderr = d.execute(command, ROOT, 2, out / name)
        assert process['exit_status'] == 0 and not process['timed_out']
        rows[name] = dict(process=process, stdout=stdout, stderr=stderr)
    d.save(out / 'SUMMARY.json', rows)
    return rows


def baseline(out):
    rows = probes('wind_adapted_before', out)
    for name in CASES:
        expected = ('CASE=%s FINAL_METHOD=false FINAL_ROUTE_MATCH=%s\n' %
                    (name, 'true' if name == 'improve' else 'false'))
        assert rows[name]['stdout'] == expected
        print(rows[name]['stdout'], end='')


def modified(out):
    out.mkdir(parents=True, exist_ok=False)
    rows = probes('wind_adapted_fixed', out / 'direct')
    for name in CASES:
        assert rows[name]['stdout'] == 'CASE=%s FINAL_METHOD=true FINAL_ROUTE_MATCH=true\n' % name
        print(rows[name]['stdout'], end='')
    d.batch(out / 'full')
    regression = []
    for item in d.verify_inputs()['rows']:
        name = item['id']
        old = ROOT / 'previous_results' / name
        new = out / 'full' / name
        final_matches = (old / 'FINAL_MAIN.json').read_bytes() == (new / 'FINAL_MAIN.json').read_bytes()
        assert final_matches, ('FINAL_MAIN_ALGORITHM_OUTPUT_CHANGED', name)
        record = d.read(new / 'RUN.json')
        assert record['engineering_qualified'] and record['issued_cost_anchor'] is not None, record
        regression.append(dict(id=name, final_main_bytes_unchanged=True,
                               old_recorder_sha256=d.sha(old / 'reference.json'),
                               new_recorder_sha256=d.sha(new / 'reference.json'),
                               qualified=True))
    d.save(out / 'REGRESSION.json', regression)
    print('FINAL_MAIN_BEHAVIOR_UNCHANGED=2/2 RECORDER_FINAL_MATCH=2/2')


def rollback(out):
    out.mkdir(parents=True, exist_ok=False)
    target = out / 'tree'
    command = [str(ROOT / 'ROLLBACK.sh'), str(target)]
    proc = subprocess.run(command, text=True, capture_output=True, timeout=5)
    d.save(out / 'RESTORE.json', dict(argv=command, exit_status=proc.returncode,
                                    stdout=proc.stdout, stderr=proc.stderr))
    assert proc.returncode == 0
    patches = d.read(ROOT / 'PATCH_HASHES.json')
    assert all(d.sha(target / name) == h for name, h in patches['original'].items())
    classes = out / 'classes'
    classes.mkdir()
    sources = [f for f in sorted((ROOT / 'frozen/wind_adapted_before').glob('*.java'))
               if f.name not in patches['original']]
    sources += list(sorted(target.glob('*.java'))) + list(sorted((ROOT / 'validation/java').glob('*.java')))
    command = [str(d.JDK / 'bin/javac'), '-J-XX:ActiveProcessorCount=1', '-J-XX:+UseSerialGC',
               '-J-Xmx256m', '-J-XX:CompressedClassSpaceSize=64m',
               '-J-XX:ReservedCodeCacheSize=64m', '-encoding', 'UTF-8', '-d', str(classes),
               *map(str, sources)]
    process, _, _ = d.execute(command, ROOT, 8, out / 'compile')
    assert process['exit_status'] == 0
    rows = probes('wind_adapted_before', out / 'restored', classes)
    base = d.read(ROOT / 'runs/BASELINE/results/SUMMARY.json')
    assert all(rows[n]['stdout'] == base[n]['stdout'] for n in CASES)
    assert all(d.sha(ROOT / 'MODIFIED_FILE' / n) == h for n, h in patches['modified'].items())
    d.save(out / 'ROLLBACK.json', dict(original_hashes_match=2, literal_stdout_matches=3,
                                     stale_equal_and_tiny_restored=True, primary_modified_retained=True))
    print('ROLLBACK_ORIGINAL_HASHES=2/2 LITERAL_STDOUT_MATCH=3/3')
    print('RESTORED_STALE_EQUAL_AND_TINY=true PRIMARY_MODIFIED_RETAINED=true')


def audit(out):
    out.mkdir(parents=True, exist_ok=False)
    for profile in d.IDENTITIES:
        d.verify_build(profile)
    before = d.hashes(ROOT / 'frozen/wind_adapted_before', '.java')
    after = d.hashes(ROOT / 'frozen/wind_adapted_fixed', '.java')
    changed = [key for key in before if before[key] != after[key]]
    assert changed == ['Main.java', 'ReferenceRecorder.java']
    rows = [d.read(ROOT / 'runs/MODIFIED/results/full' / r['id'] / 'RUN.json')
            for r in d.verify_inputs()['rows']]
    assert all(r['engineering_qualified'] and r['main_returned'] and not r['final_output_issues'] for r in rows)
    d.save(out / 'SUMMARY.json', dict(full_main_invocations=2, engineering_qualified=2,
                                    changed_java_files=changed, rows=rows, training=0,
                                    scientific_maps=0, Formal=0, G0='UNPASSED', G3='UNPASSED'))
    print('FULL_MAIN_ENGINEERING_QUALIFIED=2/2 FINAL_OUTPUT_UNCHANGED=2/2')
    print('G0=UNPASSED G3=UNPASSED TRAINING=0 SCIENTIFIC_MAPS=0 FORMAL=0')


if __name__ == '__main__':
    d.require_host()
    globals()[sys.argv[1]](Path(sys.argv[2]).resolve())
