"""New common-H worker connected to the existing whole-process controller."""
from pathlib import Path
import argparse
import importlib.util
import json
import os
import socket
import sys
import time

assert socket.gethostname() == 'EXECUTION_HOST', 'HN01_ONLY'
BASE = Path(__file__).resolve().parent
sys.path[:0] = [str(BASE / 'frozen')]
from route_method import load_input, payload_for, write_json


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--bundle', type=Path, required=True)
    parser.add_argument('--result', type=Path, required=True)
    parser.add_argument('--budget', type=float, required=True)
    parser.add_argument('--reserve-s', type=float, default=0.25)
    parser.add_argument('--delay-after-save', type=float, default=0.0)
    args = parser.parse_args()
    spec = importlib.util.spec_from_file_location('independent_control', BASE / 'MODIFIED_FILE.py')
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    bundle, instance, anchor, input_hash = load_input(args.bundle)
    started = float(os.environ['ROUTE_DELIVERY_STARTED'])
    if not (0 < args.budget < float('inf')) or not (0 <= args.reserve_s < args.budget):
        raise ValueError('FINITE_POSITIVE_BUDGET_AND_SMALLER_NONNEGATIVE_RESERVE_REQUIRED')
    result = mod.generate(instance, anchor, bundle['common_H'], bundle['search'],
                          deadline=started + args.budget, delivery_reserve_s=args.reserve_s)
    payload = payload_for(instance, anchor, result['delivery']['solution'], input_hash, 'common_h')
    payload['details'] = result
    payload['method_output_ready_elapsed_s'] = time.perf_counter() - float(os.environ['ROUTE_DELIVERY_STARTED'])
    write_json(args.result, payload)
    print('METHOD=common_h COMPLETE_OUTPUT_DURABLE=true', flush=True)
    if args.delay_after_save:
        time.sleep(args.delay_after_save)


if __name__ == '__main__':
    main()
