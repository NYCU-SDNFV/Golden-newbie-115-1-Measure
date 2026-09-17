#!/bin/sh
# Check B2 - re-runs your e3 harness, then checks both single-variable experiments. Do not modify.
. "$(dirname "$0")/lib.sh"
banner "check B2: two hypotheses, two experiments"
require_container
mkdir -p data
run_harness data/b2.txt data/b2.json python3 /workspace/harness/e3_cc_loss.py
python3 "$(dirname "$0")/grade.py" b2
