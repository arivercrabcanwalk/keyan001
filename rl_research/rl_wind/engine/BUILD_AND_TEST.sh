#!/bin/sh
set -eu
cd "$(dirname "$0")"
PYTHON=/opt/conda/bin/python
cc -O2 -ffp-contract=off -fno-fast-math -shared -fPIC -o native/libcakernel.so native/ca_kernel.c -lm
cc -O2 -ffp-contract=off -fno-fast-math -shared -fPIC -o native/libr6kernel.so native/r6_kernel.c -lm
$PYTHON -B tests/audit_regression.py .
$PYTHON -B tests/native_regression.py .
$PYTHON -B tests/test_carl.py
$PYTHON -B tests/test_v2_contract.py .
$PYTHON -B tests/test_v3_contract.py
$PYTHON -B tests/test_smdp_ppo.py
$PYTHON -B tests/test_cross_exchange_contract.py
$PYTHON -B tests/test_v2_contract.py .
$PYTHON -B tests/test_v3_contract.py
$PYTHON -B tests/test_smdp_ppo.py

$PYTHON -B tests/test_model_schema.py
$PYTHON -B tests/test_operator_level_contract.py
$PYTHON -B tests/test_locked_suite_selection.py
