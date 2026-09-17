#!/usr/bin/env python3
"""A1 -- baseline throughput / goodput / RTT   (h1 --- s1 --- h2)

Run:     make a1        (= docker exec lab2 python3 /workspace/harness/e1_baseline.py)
Writes:  data/a1.txt (what you see on screen) and data/a1.json (what the autograder reads)

Rules of the environment:
  * call net.start() only -- never net.build() yourself, or you get "veth File exists"
  * with controller=None the switch must be failMode="standalone", or it forwards nothing
  * if a previous run died half-way: `make clean` (runs `mn -c` inside the container)
"""
import labkit
from mininet.net import Mininet
from mininet.topo import Topo
from mininet.link import TCLink


class T(Topo):
    def build(self):
        h1 = self.addHost("h1", ip="10.0.0.1/24")
        h2 = self.addHost("h2", ip="10.0.0.2/24")
        s1 = self.addSwitch("s1")
        # TODO(A1-1): give BOTH links bw=100 Mbit and a one-way delay of 10 ms.
        #   Be sure what unit TCLink's `bw` uses and whether `delay` is one-way or
        #   round-trip, then check your answer against the RTT you measure (A1-4
        #   asks you for the formula).
        self.addLink(h1, s1)   # <-- add parameters
        self.addLink(h2, s1)   # <-- add parameters


# TODO(A1-2): iperf3 client options.
#   - run for at least 5 seconds
#   - keep TCP slow-start out of the statistics (hint: iperf3 has an "omit" option)
#   - explain in the report why slow-start has to be excluded
CLIENT_OPTS = ""          # <-- e.g. "-t ?? -O ??"

# TODO(A1-3): iperf3 reports a *sender* and a *receiver* number. Which one is goodput?
#   Write "sender" or "receiver", and explain how socket buffering, in-flight data
#   and the two measurement intervals can make the application-byte counters differ.
#   The sender rate is not a wire-byte counter; retransmissions are reported separately.
GOODPUT_IS = ""           # <-- "sender" or "receiver"


def main():
    if GOODPUT_IS not in ("sender", "receiver"):
        labkit.unimplemented("A1-3 GOODPUT_IS")
    if not CLIENT_OPTS.strip():
        labkit.unimplemented("A1-2 CLIENT_OPTS")
    labkit.setup()
    net = Mininet(topo=T(), link=TCLink, switch=labkit.kernel_switch(),
                  controller=None, waitConnected=False)
    labkit.start(net)
    try:
        h1, h2, s1 = net.get("h1", "h2", "s1")

        # For your report: what did TCLink actually hang on the interface?
        # (You need this to break down the gap between line rate and goodput.)
        tc = labkit.read_tc(h2, "h2-eth0")
        print("QDISC h2-eth0:", tc["qdisc"].replace("\n", " | "))
        print("CLASS h2-eth0:", tc["class"].replace("\n", " | "))
        print("parsed: rate=%s Mbit  one-way delay=%s ms" % (tc["rate_mbit"], tc["delay_ms"]))

        srv = labkit.start_iperf_server(h1)
        r = labkit.iperf_client(h2, h1.IP(), CLIENT_OPTS, server_proc=srv)
        print("IPERF3 sender   : %.2f Mbits/sec  (retransmits=%s)" % (r["sender_mbps"], r["retransmits"]))
        print("IPERF3 receiver : %.2f Mbits/sec" % r["receiver_mbps"])

        # TODO(A1-4): measure RTT with ping (at least 5 samples). The report must give the
        #   formula relating the RTT you measure to the delay you configured.
        PING_COUNT = 5
        p = labkit.ping(h2, h1.IP(), count=PING_COUNT)
        print(p["raw"])

        goodput = r[GOODPUT_IS + "_mbps"]
        print("GOODPUT (%s): %.2f Mbits/sec" % (GOODPUT_IS, goodput))

        labkit.write_json("a1", {
            "exercise": "a1",
            "datapath_type": labkit.datapath_type(s1),
            "link": {"rate_mbit": tc["rate_mbit"], "one_way_delay_ms": tc["delay_ms"]},
            "client_opts": CLIENT_OPTS,
            "iperf": r,
            "goodput_is": GOODPUT_IS,
            "goodput_mbps": goodput,
            "rtt_ms": {k: p.get(k) for k in ("min", "avg", "max", "mdev", "samples")},
            "link_stats_h2": h2.cmd("ip -s link show h2-eth0").replace("\r", "").strip(),
        })
    finally:
        net.stop()


if __name__ == "__main__":
    main()
