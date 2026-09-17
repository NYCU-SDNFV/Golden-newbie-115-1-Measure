#!/bin/sh
# Check A2 - re-runs your e2 harness, then checks the BDP relations. Do not modify.
. "$(dirname "$0")/lib.sh"
banner "check A2: bandwidth-delay product"
require_container
mkdir -p data
run_harness data/a2.txt data/a2.json python3 /workspace/harness/e2_bdp.py
python3 "$(dirname "$0")/grade.py" a2
