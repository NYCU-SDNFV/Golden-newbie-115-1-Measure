#!/usr/bin/env python3
"""A2 -- Bandwidth-Delay Product: a socket-window sweep

Run:     make a2
Writes:  data/a2.txt and data/a2.json

Target RTT = 200 ms, bw stays at 100 Mbit.
Predict the throughput ceiling of every window from the BDP *first*, then run,
then explain the gap.
"""
from __future__ import annotations

import labkit
from mininet.net import Mininet
from mininet.node import Host
from mininet.topo import Topo
from mininet.link import TCLink

WINDOWS: list[str]
AUTOTUNE_KEYS: list[str]

# TODO(A2-1): what one-way delay per link gives an RTT of about 200 ms?
#   (The topology is h1-s1-h2. How many delay stages does a round trip cross?
#   You already measured this once in A1.)
LINK_DELAY = "??ms"      # <-- fill in
LINK_BW = 100            # Mbit/s

# TODO(A2-2): at least three windows: one clearly below the BDP, one in between,
#   and the default (autotune). "" means "no -w", leave it to the kernel.
#   Use iperf3 notation: 64K / 512K / 2M.
WINDOWS = ["64K", "", ]  # <-- extend to three or more

IPERF_SECS = 6           # -t per window; -O 1 drops the first second


def bdp_bytes(bw_mbps: float, rtt_ms: float) -> float:
    """TODO(A2-3): return the BDP of this path in bytes.
    BDP = bandwidth x RTT. Mind the units: Mbit/s to bytes divides by what?"""
    labkit.unimplemented("A2-3 bdp_bytes")


def predict_mbps(win_bytes: int, rtt_ms: float) -> float:
    """TODO(A2-4): given an in-flight window ceiling (bytes) and the RTT, predict the
    throughput ceiling in Mbps. This is the 'theory' column of your report."""
    labkit.unimplemented("A2-4 predict_mbps")


# TODO(A2-5): for the default (autotune) run, how big may the kernel actually grow the
#   window? List the sysctl keys that bound it (hint: net.ipv4.tcp_wmem / tcp_rmem /
#   net.core.wmem_max) and the program reads them for you. Use them in the report to
#   explain how far autotune can open the window.
AUTOTUNE_KEYS = []       # <-- e.g. ["net.ipv4.tcp_wmem", ...]


def win_to_bytes(win: str) -> int | None:
    """'64K' -> 65536, '2M' -> 2097152. '' -> None (autotune has no fixed ceiling)."""
    if not win:
        return None
    mult = {"K": 1024, "M": 1024 ** 2, "G": 1024 ** 3}
    return int(float(win[:-1]) * mult[win[-1].upper()]) if win[-1].upper() in mult else int(win)


class T(Topo):
    def build(self) -> None:
        h1 = self.addHost("h1", ip="10.0.0.1/24")
        h2 = self.addHost("h2", ip="10.0.0.2/24")
        s1 = self.addSwitch("s1")
        self.addLink(h1, s1, bw=LINK_BW, delay=LINK_DELAY)
        self.addLink(h2, s1, bw=LINK_BW, delay=LINK_DELAY)


def main() -> None:
    if "?" in LINK_DELAY:
        labkit.unimplemented("A2-1 LINK_DELAY")
    labkit.setup()
    net = Mininet(topo=T(), link=TCLink, switch=labkit.kernel_switch(),
                  controller=None, waitConnected=False)
    labkit.start(net)
    try:
        h1 = labkit.get_node(net, "h1", Host)
        h2 = labkit.get_node(net, "h2", Host)
        labkit.ping(h2, labkit.host_ip(h1), count=2)            # warm-up: ARP on both sides costs one extra RTT
        p = labkit.ping(h2, labkit.host_ip(h1), count=5)
        rtt = p.get("min")                            # min = propagation only, no queueing noise
        if rtt is None:
            raise RuntimeError("ping did not report an RTT summary")
        print("RTT: %s" % p["raw"].splitlines()[-1])   # confirm it really is ~200 ms before going on

        bdp = bdp_bytes(LINK_BW, rtt)
        print("BDP @ %.0f Mbit x %.1f ms = %.0f bytes (%.2f MB)" % (LINK_BW, rtt, bdp, bdp / 1e6))

        runs = []
        for win in WINDOWS:
            wb = win_to_bytes(win)
            pred = predict_mbps(wb, rtt) if wb else None
            srv = labkit.start_iperf_server(h1)
            wopt = ("-w %s" % win) if win else ""
            r = labkit.iperf_client(h2, labkit.host_ip(h1), "-t %d -O 1 %s" % (IPERF_SECS, wopt), server_proc=srv)
            label = win or "DEFAULT_autotune"
            print("WIN_%-16s predicted=%s Mbps   measured(receiver)=%.2f Mbps" %
                  (label, ("%.2f" % pred) if pred else "  n/a ", r["receiver_mbps"]))
            runs.append({"window": win, "window_bytes": wb, "predicted_mbps": pred,
                         "receiver_mbps": r["receiver_mbps"], "sender_mbps": r["sender_mbps"],
                         "retransmits": r["retransmits"]})

        autotune = {k: labkit.sysctl(h2, k) for k in AUTOTUNE_KEYS}
        for k, v in autotune.items():
            print("SYSCTL %s = %s" % (k, v))

        labkit.write_json("a2", {
            "exercise": "a2",
            "link": {"rate_mbit": LINK_BW, "one_way_delay": LINK_DELAY},
            "rtt_ms": rtt,
            "bdp_bytes": bdp,
            "runs": runs,
            "autotune_sysctl": autotune,
        })
    finally:
        net.stop()


if __name__ == "__main__":
    main()
