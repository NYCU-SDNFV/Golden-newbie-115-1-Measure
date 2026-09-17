#!/bin/sh
# Check B1 - re-runs every label in harness/qdiscs.conf, rebuilds pareto.csv, checks the frontier. Do not modify.
. "$(dirname "$0")/lib.sh"
banner "check B1: Pareto frontier"
require_container
mkdir -p data
LABELS=$(awk '$0 !~ /^[[:space:]]*#/ && NF >= 2 { print $1 }' harness/qdiscs.conf)
[ -n "$LABELS" ] || die "no settings in harness/qdiscs.conf" "TODO(A4-1)/(B1-1)"
rm -f data/pareto.csv || die "cannot remove the previous data/pareto.csv" "check the data/ permissions"
for l in $LABELS; do
  case "$l" in
    *[!a-zA-Z0-9_-]*) die "invalid qdisc label: $l" "use only letters, digits, hyphens and underscores" ;;
  esac
  printf '\n--- label %s ---\n' "$l"
  run_harness "data/b1_$l.txt" "data/e5_$l.json" bash /workspace/harness/e5_aqm.sh "$l"
done
dexec python3 /workspace/tools/collect_pareto.py \
  || die "could not collect data/pareto.csv" "read the collector error above"
python3 "$(dirname "$0")/grade.py" b1
