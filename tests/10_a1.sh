#!/bin/sh
# Check A1 - re-runs your e1 harness, then checks the relations. Do not modify.
. "$(dirname "$0")/lib.sh"
banner "check A1: baseline throughput / goodput / RTT"
require_container
mkdir -p data
run_harness data/a1.txt data/a1.json python3 /workspace/harness/e1_baseline.py
python3 "$(dirname "$0")/grade.py" a1
