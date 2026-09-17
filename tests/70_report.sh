#!/bin/sh
# Check R - report and figures exist, are filled in, and are committed. Do not modify.
. "$(dirname "$0")/lib.sh"
banner "check R: report, figures, AI log"
for f in report/REPORT.md report/ai-usage.md figs/a4_cdf.png figs/b1_pareto.png data/a1.json data/a3.json data/pareto.csv; do
  git ls-files --error-unmatch "$f" >/dev/null 2>&1 || die "$f is not committed" "your measurements and figures are part of the submission: git add data figs report"
done
pass "report, figures and data are tracked by git"
python3 "$(dirname "$0")/grade.py" report
