#!/usr/bin/env python3
"""labkit -- shared *given* code for the Lab 2 harness. Do not modify (protected).

Everything in here is glue that has nothing to do with what this lab teaches but
breaks in subtle ways inside a container if written naively: how the iperf3
server is started, JSON parsing, reading tc / ethtool state back, writing
results. All measurement logic and every parameter you are graded on lives in
e1 ... e5, not here.

Why popen() + polling `ss` instead of `iperf3 -s -D`?
  Mininet's host.cmd() loses track of a daemonised process. In a container the
  client frequently connects before the server is listening, or the previous
  server is still holding the port for the next run. popen() gives us a process
  handle we can wait on and kill.
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import time
from collections.abc import Callable, Mapping, Sequence
from functools import partial
from typing import Literal, NoReturn, NotRequired, TypeVar, TypedDict, cast

from mininet.net import Mininet
from mininet.node import Host, Node, OVSSwitch, Switch

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
DATA = os.path.join(REPO, 'data')

FeatureName = Literal['tso', 'gso', 'gro', 'tx', 'rx', 'sg']
FeatureState = Literal['on', 'off', 'unknown']
NodeT = TypeVar('NodeT', bound=Node)


class IperfResult(TypedDict):
    sender_mbps: float
    receiver_mbps: float
    retransmits: int | None
    seconds: float
    cpu_host_pct: float
    cpu_remote_pct: float
    omitted_intervals: int


class PingResult(TypedDict):
    raw: str
    samples: int
    min: NotRequired[float]
    avg: NotRequired[float]
    max: NotRequired[float]
    mdev: NotRequired[float]


TcResult = TypedDict('TcResult', {
    'qdisc': str,
    'class': str,
    'rate_mbit': float | None,
    'delay_ms': float | None,
    'loss_pct': float | None,
})


def kernel_switch() -> Callable[..., OVSSwitch]:
    """OVS kernel datapath; with no controller it degrades to a learning switch.

    A3 *requires* the kernel datapath: the userspace (netdev) datapath does not
    fix up the partial checksums that TX offload leaves behind, so with
    offload=on the TCP handshake never completes and there is no on/off pair
    to compare. Lab 0 check 6 told you whether your machine can do this.
    """
    return partial(OVSSwitch, datapath='kernel', failMode='standalone')


def mn_clean() -> None:
    os.system('mn -c >/dev/null 2>&1')


# The kernel clamps SO_SNDBUF / SO_RCVBUF to net.core.wmem_max / rmem_max (212992
# bytes by default) and iperf3 aborts with "socket buffer size not set correctly"
# when its -w request is clamped. These two sysctls belong to the *host* kernel's
# root network namespace: they cannot be changed from inside the container or a
# Mininet host, only read. Host preparation is an explicit administrator action;
# `make pretest` diagnoses it and links the shared guide. Here we only check, so
# that A2/B2 fail with a clear message instead of a cryptic iperf3 error. Without
# preparation, the ceiling -- not your window -- would be the hidden variable.
# This is exactly the kind of knob A2-5 asks you to name.
SOCKET_CEILING = 8 * 1024 * 1024


def setup() -> None:
    """Call first in every harness: clean stale Mininet state."""
    mn_clean()


def start(net: Mininet) -> Mininet:
    """net.start() plus a check of the socket-buffer ceilings. Use instead of net.start()."""
    net.start()
    h = net.hosts[0]
    low = [k for k in ('net.core.rmem_max', 'net.core.wmem_max')
           if not sysctl(h, k).isdigit() or int(sysctl(h, k)) < SOCKET_CEILING]
    if low:
        print('warning: %s below %d on this host -> iperf3 -w above ~200K will fail. '
              'run `make pretest` on the Docker Engine host and follow '
              '.github/golden/README.md'
              % (', '.join(low), SOCKET_CEILING))
    return net


def get_node(net: Mininet, name: str, node_type: type[NodeT]) -> NodeT:
    """Return a named Mininet node and verify the topology supplied its expected type."""
    node = net.get(name)
    if not isinstance(node, node_type):
        raise TypeError('%s is %s, expected %s' % (
            name, type(node).__name__, node_type.__name__))
    return node


def cmd(node: Node, command: str) -> str:
    """Run a Mininet command, failing explicitly if its shell has exited."""
    output = node.cmd(command)
    if not isinstance(output, str):
        raise RuntimeError('%s returned no text for command: %s' % (node.name, command))
    return output


def host_ip(host: Host) -> str:
    """Return the configured host address, not an absent interface address."""
    address = host.IP()
    if address is None:
        raise RuntimeError('%s has no configured IP address' % host.name)
    return address


def datapath_type(switch: Switch) -> str:
    dp = cmd(
        switch, 'ovs-vsctl get bridge %s datapath_type' % switch.name).strip().strip('"')
    return dp or 'system'


def start_iperf_server(
        host: Host, port: int = 5201, timeout: float = 10.0) -> subprocess.Popen[bytes]:
    """Start `iperf3 -s -1` on host and return only once it is really listening."""
    proc = host.popen('iperf3 -s -1 -p %d' % port)
    deadline = time.time() + timeout
    while time.time() < deadline:
        if (':%d ' % port) in cmd(host, 'ss -ltn'):
            return proc
        time.sleep(0.2)
    proc.kill()
    raise RuntimeError('iperf3 server on %s never listened on port %d' % (host.name, port))


def iperf_client(
        client: Host,
        server_ip: str,
        opts: str = '',
        port: int = 5201,
        server_proc: subprocess.Popen[bytes] | None = None) -> IperfResult:
    """Run the iperf3 client with JSON output. `opts` is the option string you wrote."""
    out = cmd(
        client,
        'iperf3 -c %s -p %d -J --connect-timeout 5000 %s' % (
            server_ip, port, opts))
    if server_proc is not None:
        try:
            server_proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            server_proc.kill()
    try:
        j = json.loads(out[out.index('{'):])
    except ValueError as error:
        raise RuntimeError('iperf3 output is not JSON:\n' + out[:1500]) from error
    if 'error' in j:
        raise RuntimeError('iperf3: ' + j['error'])
    end = j['end']
    cpu = end.get('cpu_utilization_percent', {})
    sent = end.get('sum_sent', {})
    recv = end.get('sum_received', {})
    return {
        'sender_mbps': round(sent.get('bits_per_second', 0) / 1e6, 3),
        'receiver_mbps': round(recv.get('bits_per_second', 0) / 1e6, 3),
        'retransmits': sent.get('retransmits'),
        'seconds': round(recv.get('seconds', sent.get('seconds', 0)), 2),
        'cpu_host_pct': round(cpu.get('host_total', 0), 1),
        'cpu_remote_pct': round(cpu.get('remote_total', 0), 1),
        'omitted_intervals': sum(1 for i in j.get('intervals', []) if i.get('sum', {}).get('omitted')),
    }


def ping(
        src: Host, dst_ip: str, count: int = 5, interval: float = 0.2) -> PingResult:
    """Return {'min','avg','max','mdev','samples','raw'} (ms)."""
    out = cmd(
        src, 'ping -c %d -i %s -W 2 %s' % (
            count, interval, dst_ip)).replace('\r', '')
    m = re.search(r'= ([\d.]+)/([\d.]+)/([\d.]+)/([\d.]+) ms', out)
    res: PingResult = {
        'raw': out.strip(),
        'samples': len(re.findall(r'time=', out)),
    }
    if m:
        res['min'], res['avg'], res['max'], res['mdev'] = (
            float(value) for value in m.groups())
    return res


def read_tc(node: Node, intf: str) -> TcResult:
    """Read back what TCLink hung on an interface: htb rate, netem delay / loss."""
    out = cmd(node, 'tc qdisc show dev %s' % intf).replace('\r', '')
    cls = cmd(node, 'tc class show dev %s' % intf).replace('\r', '')
    res: TcResult = {
        'qdisc': out.strip(),
        'class': cls.strip(),
        'rate_mbit': None,
        'delay_ms': None,
        'loss_pct': None,
    }
    m = re.search(r'rate (\d+(?:\.\d+)?)([KMG])bit', cls + out)
    if m:
        v, u = float(m.group(1)), m.group(2)
        res['rate_mbit'] = v * {'K': 1e-3, 'M': 1, 'G': 1e3}[u]
    m = re.search(r'delay (\d+(?:\.\d+)?)(us|ms|s)\b', out)
    if m:
        v, u = float(m.group(1)), m.group(2)
        res['delay_ms'] = v * {'us': 1e-3, 'ms': 1, 's': 1e3}[u]
    m = re.search(r'loss (\d+(?:\.\d+)?)%', out)
    if m:
        res['loss_pct'] = float(m.group(1))
    return res


FEATURE_NAMES: dict[FeatureName, str] = {
    'tso': 'tcp-segmentation-offload',
    'gso': 'generic-segmentation-offload',
    'gro': 'generic-receive-offload',
    'tx': 'tx-checksumming',
    'rx': 'rx-checksumming',
    'sg': 'scatter-gather',
}


def read_features(
        node: Node,
        intf: str,
        keys: Sequence[FeatureName] = ('tso', 'gso', 'gro')) -> dict[str, FeatureState]:
    """Read offload state back with `ethtool -k` -- read, never assume."""
    out = cmd(node, 'ethtool -k %s' % intf)
    got: dict[str, FeatureState] = {}
    for k in keys:
        m = re.search(r'^%s:\s*(on|off)' % re.escape(FEATURE_NAMES[k]), out, re.M)
        got[k] = cast(FeatureState, m.group(1)) if m else 'unknown'
    return got


def sysctl(node: Node, key: str) -> str:
    return cmd(node, 'sysctl -n %s' % key).strip()


def write_json(name: str, obj: Mapping[str, object]) -> str:
    os.makedirs(DATA, exist_ok=True)
    path = os.path.join(DATA, name + '.json')
    obj = dict(obj)
    obj.setdefault('written_at', time.strftime('%Y-%m-%dT%H:%M:%S'))
    obj.setdefault('kernel', os.uname().release)
    with open(path, 'w') as f:
        json.dump(obj, f, indent=2)
    print('\nwrote %s' % os.path.relpath(path, REPO))
    return path


def unimplemented(tag: str) -> NoReturn:
    raise SystemExit('unfinished: %s -- read the comment above that TODO' % tag)
