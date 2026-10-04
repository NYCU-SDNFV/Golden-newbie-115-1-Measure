#!/usr/bin/env python3
# pyright: reportMissingImports=false
"""B1: scatter your settings as goodput vs P99 RTT and mark the dominated ones.

Usage:
    1) make b1            (runs every label in harness/qdiscs.conf, builds data/pareto.csv)
    2) python3 tools/plot_pareto.py data/pareto.csv -o figs/b1_pareto.png \
           --slo-goodput 9 --slo-p99 20

The program only draws and flags dominated points. Which points should exist, how to
read the SLO, and why you would pick one setting over another is what your report
has to defend.
"""
from __future__ import annotations

import argparse
import csv
import os
from collections.abc import Sequence
from typing import TypedDict

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt


class Point(TypedDict):
    label: str
    goodput: float
    p50: float
    p99: float


def dominated(pt: Point, others: Sequence[Point]) -> bool:
    """Higher goodput and lower p99 are better. If another point is at least as good in both
    dimensions and strictly better in one, this point is dominated."""
    g, p = pt["goodput"], pt["p99"]
    for o in others:
        if o is pt:
            continue
        if o["goodput"] >= g and o["p99"] <= p and (o["goodput"] > g or o["p99"] < p):
            return True
    return False


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("csv")
    ap.add_argument("-o", "--out", default="figs/b1_pareto.png")
    ap.add_argument("--slo-goodput", type=float, default=None, help="goodput floor (Mbps)")
    ap.add_argument("--slo-p99", type=float, default=None, help="P99 RTT ceiling (ms)")
    args = ap.parse_args()

    pts: list[Point] = []
    with open(args.csv) as f:
        for row in csv.DictReader(f):
            if not row.get("label") or row["label"].startswith("#"):
                continue
            pts.append({"label": row["label"].strip(),
                        "goodput": float(row["goodput_mbps"]),
                        "p50": float(row.get("p50_ms") or "nan"),
                        "p99": float(row["p99_ms"])})
    if len(pts) < 3:
        print("warning: only %d point(s); B1 asks for at least 3." % len(pts))

    os.makedirs(os.path.dirname(args.out) or ".", exist_ok=True)
    fig, ax = plt.subplots(figsize=(6.5, 4.6))
    rightmost = max((p["p99"] for p in pts), default=0)
    for index, p in enumerate(sorted(pts, key=lambda p: p["p99"])):
        dom = dominated(p, pts)
        ax.scatter(p["p99"], p["goodput"], s=70,
                   marker="x" if dom else "o",
                   color="#999999" if dom else "#1f77b4", zorder=3)
        ax.annotate("%s%s" % (p["label"], " (dominated)" if dom else ""),
                    (p["p99"], p["goodput"]), textcoords="offset points",
                    xytext=(-6 if p["p99"] == rightmost else 6,
                            9 if index % 2 == 0 else -14),
                    ha="right" if p["p99"] == rightmost else "left", fontsize=8)

    ax.margins(y=0.1)
    if args.slo_p99:
        ax.axvline(args.slo_p99, color="#d62728", linestyle="--", linewidth=1)
    if args.slo_goodput:
        ax.axhline(args.slo_goodput, color="#d62728", linestyle="--", linewidth=1)
    if args.slo_p99 and args.slo_goodput:
        low, high = ax.get_ylim()
        ax.axvspan(0, args.slo_p99,
                   ymin=(args.slo_goodput - low) / (high - low), ymax=1,
                   color="#d62728", alpha=0.05)
        ax.set_title("SLO: goodput >= %g Mbps and P99 <= %g ms" % (args.slo_goodput, args.slo_p99),
                     fontsize=9)

    ax.set_xlabel("P99 RTT under load (ms)")
    ax.set_ylabel("goodput (Mbps)")
    ax.grid(alpha=0.3)
    fig.tight_layout()
    fig.savefig(args.out, dpi=150)
    print("wrote", args.out)


if __name__ == "__main__":
    main()
