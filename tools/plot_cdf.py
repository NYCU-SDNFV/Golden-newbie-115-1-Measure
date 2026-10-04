#!/usr/bin/env python3
# pyright: reportMissingImports=false
"""Plot the RTT CDF. Given in full -- plotting is not what this lab grades.

Usage:
    python3 tools/plot_cdf.py data/e5_bloat.csv data/e5_aqm.csv -o figs/a4_cdf.png

Input:  one RTT sample (ms) per line, as written by harness/e5_aqm.sh.
Output: the CDF figure, plus p50/p90/p99 on stdout (the numbers for your B1 table).
"""
from __future__ import annotations

import argparse
import os
import sys
from collections.abc import Sequence

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt


def load(path: str) -> list[float]:
    vals: list[float] = []
    with open(path) as f:
        for line in f:
            line = line.strip().rstrip(",")
            if not line:
                continue
            for tok in line.split(","):
                try:
                    vals.append(float(tok))
                except ValueError:
                    pass
    if not vals:
        sys.exit("no samples in %s" % path)
    return sorted(vals)


def pct(sorted_vals: Sequence[float], q: float) -> float:
    if not sorted_vals:
        return float("nan")
    idx = min(len(sorted_vals) - 1, max(0, int(round(q / 100.0 * len(sorted_vals))) - 1))
    return sorted_vals[idx]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("csv", nargs="+")
    ap.add_argument("-o", "--out", default="figs/cdf.png")
    ap.add_argument("--logx", action="store_true", help="recommended when the tails differ by orders of magnitude")
    args = ap.parse_args()

    os.makedirs(os.path.dirname(args.out) or ".", exist_ok=True)
    fig, ax = plt.subplots(figsize=(6.5, 4.2))
    for path in args.csv:
        vals = load(path)
        label = os.path.splitext(os.path.basename(path))[0].replace("e5_", "")
        ys = [(i + 1) / len(vals) for i in range(len(vals))]
        ax.plot(vals, ys, marker=".", linestyle="-", linewidth=1.2, markersize=3, label=label)
        print("%-14s n=%-4d  p50=%8.2f ms  p90=%8.2f ms  p99=%8.2f ms  max=%8.2f ms"
              % (label, len(vals), pct(vals, 50), pct(vals, 90), pct(vals, 99), vals[-1]))

    if args.logx:
        ax.set_xscale("log")
    ax.set_xlabel("RTT (ms)")
    ax.set_ylabel("CDF")
    ax.set_ylim(0, 1.02)
    ax.grid(alpha=0.3)
    ax.legend()
    fig.tight_layout()
    fig.savefig(args.out, dpi=150)
    print("wrote", args.out)


if __name__ == "__main__":
    main()
