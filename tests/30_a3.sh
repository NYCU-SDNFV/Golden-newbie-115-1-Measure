#!/bin/sh
# Check A3 - re-runs your e4 harness, then checks offload relations. Do not modify.
. "$(dirname "$0")/lib.sh"
banner "check A3: offload vs CPU"
require_container
mkdir -p data
run_harness data/a3.txt data/a3.json python3 /workspace/harness/e4_offload.py
python3 "$(dirname "$0")/grade.py" a3
