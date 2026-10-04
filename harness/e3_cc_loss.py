#!/usr/bin/env python3
"""B2 -- two competing hypotheses, two single-variable experiments

Run:     make b2
Writes:  data/b2.txt and data/b2.json

Scenario: a box on a high-RTT path gets "very low throughput". Two mechanisms could
explain it and you must find out which one does. Each experiment below changes
exactly ONE thing while everything else stays fixed. You design both; the
program only provides the loop.

  Experiment 1 -- vary the congestion-control algorithm, window untouched.
  Experiment 2 -- vary the socket window, congestion control fixed.

Write down in the report which hypothesis each experiment tests, what result
would falsify it, and what you actually saw.
"""
from __future__ import annotations

import labkit
from mininet.net import Mininet
from mininet.node import Host
from mininet.topo import Topo
from mininet.link import TCLink

CC_LIST: list[str]
WINDOWS: list[str]

# TODO(B2-1): design a path with high RTT AND random loss.
#   RTT has to be large for congestion control to matter; start with 1 % loss.
#   Mind where TCLink puts the loss (which link, one direction or both) -- it
#   changes how you interpret the result.
LINK_DELAY = "??ms"    # <-- fill in
LOSS_PCT = None        # <-- fill in (e.g. 1.0)

# TODO(B2-2): which congestion-control algorithms to compare? At least two, from
#   DIFFERENT families (hint: loss-based vs model/rate-based). Check first that the
#   kernel has them: sysctl net.ipv4.tcp_available_congestion_control
CC_LIST = []           # <-- fill in

# TODO(B2-3): the window experiment. Pick ONE congestion control (the loss-based
#   one) and two windows: the default ("") and one that is clearly larger than the
#   BDP of this path (you computed BDPs in A2). If enlarging the window does not
#   help while changing the algorithm does, what does that tell you?
WINDOW_CC = ""         # <-- e.g. "cubic"
WINDOWS = ["", ""]     # <-- e.g. ["", "4M"]

IPERF_SECS = 8


class T(Topo):
    def build(self) -> None:
        h1 = self.addHost("h1", ip="10.0.0.1/24")
        h2 = self.addHost("h2", ip="10.0.0.2/24")
        s1 = self.addSwitch("s1")
        self.addLink(h1, s1, bw=100, delay=LINK_DELAY)
        self.addLink(h2, s1, bw=100, delay=LINK_DELAY, loss=LOSS_PCT)


def set_cc(h: Host, cc: str) -> str:
    labkit.cmd(h, "sysctl -qw net.ipv4.tcp_congestion_control=%s" % cc)
    got = labkit.sysctl(h, "net.ipv4.tcp_congestion_control")
    if got != cc:
        raise SystemExit("could not set congestion control to %s (kernel says %s) -- "
                         "is the module available? see tcp_available_congestion_control" % (cc, got))
    return got


def run_once(h1: Host, h2: Host, opts: str) -> labkit.IperfResult:
    srv = labkit.start_iperf_server(h1)
    return labkit.iperf_client(h2, labkit.host_ip(h1), "-t %d -O 2 %s" % (IPERF_SECS, opts), server_proc=srv)


def main() -> None:
    if "?" in LINK_DELAY or LOSS_PCT is None:
        labkit.unimplemented("B2-1 LINK_DELAY / LOSS_PCT")
    if len(CC_LIST) < 2:
        labkit.unimplemented("B2-2 CC_LIST")
    if not WINDOW_CC or len([w for w in WINDOWS if w]) < 1 or len(WINDOWS) < 2:
        labkit.unimplemented("B2-3 WINDOW_CC / WINDOWS")

    labkit.setup()
    net = Mininet(topo=T(), link=TCLink, switch=labkit.kernel_switch(),
                  controller=None, waitConnected=False)
    labkit.start(net)
    try:
        h1 = labkit.get_node(net, "h1", Host)
        h2 = labkit.get_node(net, "h2", Host)
        avail = labkit.sysctl(h2, "net.ipv4.tcp_available_congestion_control").split()
        print("AVAILABLE_CC:", " ".join(avail))
        labkit.ping(h2, labkit.host_ip(h1), count=2)            # warm-up (ARP)
        p = labkit.ping(h2, labkit.host_ip(h1), count=5)
        print("RTT:", p["raw"].splitlines()[-1])
        tc = labkit.read_tc(h2, "h2-eth0")
        print("LINK h2-eth0: rate=%s Mbit delay=%s ms loss=%s %%" % (tc["rate_mbit"], tc["delay_ms"], tc["loss_pct"]))

        # Experiment 1: only the congestion control changes. Set it on BOTH hosts so the
        # sender is unambiguous.
        exp1 = []
        for cc in CC_LIST:
            for h in (h1, h2):
                set_cc(h, cc)
            r = run_once(h1, h2, "")
            print("EXP1 CC_%-6s: %.2f Mbps (receiver)   retransmits=%s" % (cc, r["receiver_mbps"], r["retransmits"]))
            exp1.append({"cc": cc, "receiver_mbps": r["receiver_mbps"], "sender_mbps": r["sender_mbps"],
                         "retransmits": r["retransmits"]})

        # Experiment 2: congestion control fixed, only the window changes.
        exp2 = []
        for h in (h1, h2):
            set_cc(h, WINDOW_CC)
        for win in WINDOWS:
            r = run_once(h1, h2, ("-w %s" % win) if win else "")
            print("EXP2 %s WIN_%-8s: %.2f Mbps (receiver)   retransmits=%s"
                  % (WINDOW_CC, win or "default", r["receiver_mbps"], r["retransmits"]))
            exp2.append({"cc": WINDOW_CC, "window": win, "receiver_mbps": r["receiver_mbps"],
                         "sender_mbps": r["sender_mbps"], "retransmits": r["retransmits"]})

        labkit.write_json("b2", {
            "exercise": "b2",
            "link": {"rate_mbit": 100, "one_way_delay": LINK_DELAY, "loss_pct": LOSS_PCT,
                     "measured": {"rtt_ms": p.get("min"), "tc_h2": tc}},
            "available_cc": avail,
            "exp1_vary_cc": exp1,
            "exp2_vary_window": exp2,
        })
    finally:
        net.stop()


if __name__ == "__main__":
    main()
