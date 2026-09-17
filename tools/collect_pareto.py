#!/usr/bin/env python3
"""Build data/pareto.csv from every data/e5_<label>.json written by harness/e5_aqm.sh.

Usage:  python3 tools/collect_pareto.py            (run automatically by `make b1`)

One row per label: label, leaf_qdisc, goodput_mbps, p50_ms, p90_ms, p99_ms, idle_rtt_ms.
The numbers are copied verbatim from your own runs -- nothing is computed here.
"""
import csv
import glob
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "..", "data")


def main():
    rows = []
    for path in sorted(glob.glob(os.path.join(DATA, "e5_*.json"))):
        with open(path) as f:
            j = json.load(f)
        rows.append({"label": j["label"], "leaf_qdisc": j["leaf_qdisc"],
                     "goodput_mbps": j.get("goodput_mbps"), "p50_ms": j.get("p50_ms"),
                     "p90_ms": j.get("p90_ms"), "p99_ms": j.get("p99_ms"),
                     "idle_rtt_ms": j.get("idle_rtt_avg_ms")})
    out = os.path.join(DATA, "pareto.csv")
    with open(out, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["label", "leaf_qdisc", "goodput_mbps", "p50_ms",
                                          "p90_ms", "p99_ms", "idle_rtt_ms"], lineterminator="\n")
        w.writeheader()
        w.writerows(rows)
    for r in rows:
        print("%-12s goodput=%-7s p50=%-8s p99=%-8s  %s" % (r["label"], r["goodput_mbps"],
                                                             r["p50_ms"], r["p99_ms"], r["leaf_qdisc"]))
    print("wrote data/pareto.csv (%d points)" % len(rows))


if __name__ == "__main__":
    main()
