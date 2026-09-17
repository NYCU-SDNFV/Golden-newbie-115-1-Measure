#!/bin/sh
# Check A4 - re-runs e5 with label bloat, then checks the bufferbloat relations. Do not modify.
. "$(dirname "$0")/lib.sh"
banner "check A4: latency under load (bloat)"
require_container
mkdir -p data
run_harness data/a4.txt data/e5_bloat.json bash /workspace/harness/e5_aqm.sh bloat
python3 "$(dirname "$0")/grade.py" a4
