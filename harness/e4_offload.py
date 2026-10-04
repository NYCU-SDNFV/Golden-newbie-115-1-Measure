#!/usr/bin/env python3
"""A3 -- what TSO/GSO/GRO offload does to throughput *and* CPU

Run:     make a3
Writes:  data/a3.txt and data/a3.json

This exercise is deliberately NOT rate-limited (plain veth, no bw/delay): the point
is to make the CPU the bottleneck. You are graded on Gbps-per-CPU, not raw Gbps.

Why the kernel datapath is mandatory here: the userspace (netdev) datapath does not
fix up the partial checksums TX offload leaves behind, so with offload=on the TCP
handshake never completes and there is nothing to compare. labkit.kernel_switch()
already picks it for you; Lab 0 check 6 told you whether your machine can do it.
"""
from __future__ import annotations

from typing import Literal

import labkit
from mininet.net import Mininet
from mininet.node import Host, OVSSwitch
from mininet.topo import Topo

IPERF_SECS = 6
FEATURES = ("tso", "gso", "gro")
OffloadState = Literal["default", "on", "off"]
OffloadToggle = Literal["on", "off"]


class T(Topo):
    def build(self) -> None:
        h1 = self.addHost("h1", ip="10.0.0.1/24")
        h2 = self.addHost("h2", ip="10.0.0.2/24")
        s1 = self.addSwitch("s1")
        self.addLink(h1, s1)     # plain veth, no shaping (think about why bw= would ruin this experiment)
        self.addLink(h2, s1)


def show_features(h: Host, iface: str) -> dict[str, labkit.FeatureState]:
    # TODO(A3-1): return the DEFAULT state of tso / gso / gro on this interface as a dict
    #   {"tso": "on"|"off", "gso": ..., "gro": ...}. labkit.read_features(h, iface) reads
    #   them back with `ethtool -k`. One of the three is off by default on a veth: name it
    #   in the report and say whether it is a sender-side or a receiver-side offload.
    return {}   # <-- fill in


def offload_flags(state: OffloadToggle) -> str:
    # TODO(A3-2): return the argument string that follows `ethtool -K <iface>` to set
    #   tso, gso AND gro to `state` at once; e.g. for state="off" something like
    #   "tso off gso off gro off". The program applies it to h1, h2 *and both ports of
    #   s1* -- think about why the switch side has to change too.
    return ""    # <-- fill in


def gbps_per_cpu(gbps: float, cpu_pct: float) -> float | None:
    # TODO(A3-3): compute Gbps per CPU = throughput / sender CPU utilisation, where
    #   100 % means one fully busy core. Your conclusion in the report must use this
    #   efficiency figure, not raw throughput.
    return None  # <-- fill in


def apply_offload(net: Mininet, state: OffloadToggle) -> None:
    flags = offload_flags(state)
    if not flags.strip():
        labkit.unimplemented("A3-2 offload_flags")
    nodes = (
        labkit.get_node(net, "h1", Host),
        labkit.get_node(net, "h2", Host),
        labkit.get_node(net, "s1", OVSSwitch),
    )
    for node in nodes:
        for intf in node.intfList():
            if intf.name != "lo":
                labkit.cmd(node, "ethtool -K %s %s 2>/dev/null" % (intf.name, flags))


def measure(state: OffloadState) -> dict[str, object]:
    labkit.setup()
    net = Mininet(topo=T(), switch=labkit.kernel_switch(), controller=None, waitConnected=False)
    labkit.start(net)
    try:
        h1 = labkit.get_node(net, "h1", Host)
        h2 = labkit.get_node(net, "h2", Host)
        s1 = labkit.get_node(net, "s1", OVSSwitch)
        rec: dict[str, object] = {
            "offload": state,
            "datapath_type": labkit.datapath_type(s1),
        }
        if state == "default":
            features = show_features(h1, "h1-eth0")
            rec["h1_features"] = features
            if set(features) != set(FEATURES):
                labkit.unimplemented("A3-1 show_features")
            print("DEFAULT FEATURES(h1-eth0):", features)
            return rec
        apply_offload(net, state)
        rec["h1_features"] = labkit.read_features(h1, "h1-eth0")   # read back, never assume
        rec["h2_features"] = labkit.read_features(h2, "h2-eth0")
        srv = labkit.start_iperf_server(h1)
        r = labkit.iperf_client(h2, labkit.host_ip(h1), "-t %d -O 1" % IPERF_SECS, server_proc=srv)
        gbps = r["receiver_mbps"] / 1e3
        eff = gbps_per_cpu(gbps, r["cpu_host_pct"])
        if eff is None:
            labkit.unimplemented("A3-3 gbps_per_cpu")
        rec.update({"gbps": round(gbps, 3), "cpu_host_pct": r["cpu_host_pct"],
                    "cpu_remote_pct": r["cpu_remote_pct"], "retransmits": r["retransmits"],
                    "gbps_per_cpu": round(eff, 3)})
        print("OFFLOAD_%-3s: %.2f Gbps | cpu host(sender)=%.1f%% remote=%.1f%% | Gbps/CPU=%.2f | h1=%s"
              % (state, gbps, r["cpu_host_pct"], r["cpu_remote_pct"], eff, rec["h1_features"]))
        return rec
    finally:
        net.stop()


def main() -> None:
    if not offload_flags("off").strip():
        labkit.unimplemented("A3-2 offload_flags")
    if gbps_per_cpu(1.0, 100.0) is None:
        labkit.unimplemented("A3-3 gbps_per_cpu")
    runs = [measure("default"), measure("on"), measure("off")]
    labkit.write_json("a3", {"exercise": "a3", "iperf_secs": IPERF_SECS, "runs": runs,
                             "openvswitch_module_loaded": "openvswitch" in open("/proc/modules").read()})


if __name__ == "__main__":
    main()
