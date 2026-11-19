"""Root-only serial CPU-ticket supervisor, including nested-session children.

Read-only container cgroup usage is a conservative process-tree upper bound:
it additionally charges unrelated container work. Children inherit one CPU.
The termination reserve is withheld from work, not silently spent on a solve.
"""
import argparse
import ctypes
import fcntl
import json
import os
from pathlib import Path
import resource
import signal
import socket
import subprocess
import sys
import time

def usage():
    return int(dict(line.split() for line in Path('/sys/fs/cgroup/cpu.stat').read_text().splitlines())['usage_usec'])/1e6

def append(path,row):
    with path.open('a') as f:
        f.write(json.dumps(row,sort_keys=True,allow_nan=False)+'\n');f.flush();os.fsync(f.fileno())

def debit(path):
    fixed=0.;latest={}
    if path.exists():
        for line in path.read_text().splitlines():
            r=json.loads(line)
            if r.get('schema')=='ticket_guard_v1':latest[r['row_id']]=r
            else:fixed+=r.get('total_debit_seconds',0.)
    return fixed+sum(r.get('total_debit_seconds',r['reserved_cpu_seconds']) for r in latest.values()),latest

def descendants():
    links={}
    for p in Path('/proc').iterdir():
        if not p.name.isdigit():continue
        try:
            # comm may contain spaces and parentheses; fields begin after final ).
            fields=(p/'stat').read_text().rsplit(')',1)[1].split()
            links[int(p.name)]=int(fields[1])
        except (FileNotFoundError,ProcessLookupError,PermissionError):continue
    found=set();parents={os.getpid()}
    while parents:
        children={pid for pid,ppid in links.items() if ppid in parents}-found
        found|=children;parents=children
    return found

def kill_owned():
    # Every subprocess here is owned by this one invocation. PR_SET_CHILD_SUBREAPER
    # keeps grandchildren whose launcher exited, including setsid workers.
    for pid in sorted(descendants(),reverse=True):
        try:os.kill(pid,signal.SIGKILL)
        except ProcessLookupError:pass

def main():
    assert socket.gethostname()=='EXECUTION_HOST','HN01_ONLY'
    p=argparse.ArgumentParser()
    p.add_argument('--ledger',type=Path,required=True)
    p.add_argument('--out',type=Path,required=True)
    p.add_argument('--row-id',required=True)
    p.add_argument('--reserved-cpu-seconds',type=float,required=True)
    p.add_argument('--wall-cap-seconds',type=float,required=True)
    p.add_argument('--ticket-cap-seconds',type=float,default=172800)
    p.add_argument('--termination-reserve-seconds',type=float,default=120)
    p.add_argument('--method-deadline-seconds',type=float)
    p.add_argument('command',nargs=argparse.REMAINDER)
    a=p.parse_args();command=a.command[1:] if a.command[:1]==['--'] else a.command
    assert command and 0<a.termination_reserve_seconds<a.reserved_cpu_seconds<a.ticket_cap_seconds<=172800
    assert 0<a.wall_cap_seconds<float('inf')
    a.out.mkdir(parents=True,exist_ok=False);a.ledger.parent.mkdir(parents=True,exist_ok=True)
    lock=a.ledger.with_suffix(a.ledger.suffix+'.lock').open('a');fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
    spent,latest=debit(a.ledger)
    if a.row_id in latest:raise RuntimeError('ROW_ALREADY_ATTEMPTED_NEVER_RELAUNCH')
    remaining=a.ticket_cap_seconds-spent
    if remaining<a.reserved_cpu_seconds+a.termination_reserve_seconds:
        (a.out/'NOT_STARTED.json').write_text(json.dumps({'status':'BUDGET_NOT_STARTED','remaining':remaining})+'\n');return 3
    assert ctypes.CDLL(None,use_errno=True).prctl(36,1,0,0,0)==0,'SUBREAPER_REQUIRED'
    cpu=min(os.sched_getaffinity(0));os.sched_setaffinity(0,{cpu})
    first=usage();start=time.monotonic()
    row={'schema':'ticket_guard_v1','row_id':a.row_id,'state':'RUNNING','reserved_cpu_seconds':a.reserved_cpu_seconds,
         'command':command,'cwd':os.getcwd(),'pinned_cpu':cpu,'container_cpu_start':first,
         'accounting':'container cgroup upper bound plus supervisor self CPU and 0.1s terminal allowance',
         'termination_reserve_seconds':a.termination_reserve_seconds,'prior_debit_seconds':spent}
    append(a.ledger,row);(a.out/'INTENT.json').write_text(json.dumps(row,indent=2)+'\n')
    stop=None
    with (a.out/'STDOUT.txt').open('wb') as stdout,(a.out/'STDERR.txt').open('wb') as stderr:
        method_started=time.perf_counter()
        child_env=dict(os.environ,PYTHONDONTWRITEBYTECODE='1',OMP_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1',MKL_NUM_THREADS='1')
        if a.method_deadline_seconds is not None:
            assert a.method_deadline_seconds in (6,12)
            child_env['CONTROL_PROCESS_STARTED']=repr(method_started)
        child=subprocess.Popen(command,stdout=stdout,stderr=stderr,start_new_session=True,env=child_env)
        try:
            while child.poll() is None:
                used=usage()-first
                if used<0:stop='CGROUP_COUNTER_RESET';break
                if used>=min(a.reserved_cpu_seconds,remaining)-a.termination_reserve_seconds:
                    stop='CPU_STOP_BEFORE_RESERVED_LIMIT';break
                if a.method_deadline_seconds is not None and time.perf_counter()-method_started>=a.method_deadline_seconds:
                    stop='CONTROL_PROCESS_DEADLINE';break
                if time.monotonic()-start>=a.wall_cap_seconds:
                    stop='WALL_STOP';break
                if os.sched_getaffinity(0)!={cpu}:stop='AFFINITY_CHANGED';break
                time.sleep(.02)
        finally:
            if stop or descendants()-{child.pid}:kill_owned()
            if child.poll() is None:child.kill()
            child.wait()
            observed_exit_elapsed=time.perf_counter()-method_started
            # Adopted descendants may briefly remain zombies; reap all.
            limit=time.monotonic()+2
            while descendants() and time.monotonic()<limit:
                kill_owned()
                try:
                    while os.waitpid(-1,os.WNOHANG)[0]:pass
                except ChildProcessError:pass
                time.sleep(.01)
    delta=usage()-first
    own=resource.getrusage(resource.RUSAGE_SELF)
    charged=delta+own.ru_utime+own.ru_stime+.1
    alive=sorted(descendants())
    ok=delta>=0 and not alive and charged<=a.reserved_cpu_seconds and spent+charged<=a.ticket_cap_seconds
    terminal=dict(row,state='TERMINAL',exit_status=child.returncode,stop_reason=stop,
                  container_cpu_delta_seconds=delta,total_debit_seconds=charged,
                  method_started=method_started,process_exit_observed_elapsed_s=observed_exit_elapsed,
                  method_deadline_seconds=a.method_deadline_seconds,
                  complete_process_ontime=(a.method_deadline_seconds is None or observed_exit_elapsed<=a.method_deadline_seconds),
                  wall_seconds=time.monotonic()-start,remaining_descendants=alive,
                  budget_and_cleanup_pass=ok)
    (a.out/'TERMINAL.json').write_text(json.dumps(terminal,indent=2)+'\n');append(a.ledger,terminal)
    print(json.dumps({k:terminal[k] for k in ('row_id','exit_status','stop_reason','total_debit_seconds','remaining_descendants','budget_and_cleanup_pass')},sort_keys=True))
    return 0 if ok and stop is None and child.returncode==0 else 4 if ok else 5

if __name__=='__main__':sys.exit(main())
