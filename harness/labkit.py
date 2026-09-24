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
import json
import os
import re
import time
from functools import partial

from mininet.node import OVSSwitch

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
DATA = os.path.join(REPO, 'data')


def kernel_switch():
    """OVS kernel datapath; with no controller it degrades to a learning switch.

    A3 *requires* the kernel datapath: the userspace (netdev) datapath does not
    fix up the partial checksums that TX offload leaves behind, so with
    offload=on the TCP handshake never completes and there is no on/off pair
    to compare. Lab 0 check 6 told you whether your machine can do this.
    """
    return partial(OVSSwitch, datapath='kernel', failMode='standalone')


def mn_clean():
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


def setup():
    """Call first in every harness: clean stale Mininet state."""
    mn_clean()


def start(net):
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


def datapath_type(switch):
    dp = switch.cmd('ovs-vsctl get bridge %s datapath_type' % switch.name).strip().strip('"')
    return dp or 'system'


def start_iperf_server(host, port=5201, timeout=10.0):
    """Start `iperf3 -s -1` on host and return only once it is really listening."""
    proc = host.popen('iperf3 -s -1 -p %d' % port)
    deadline = time.time() + timeout
    while time.time() < deadline:
        if (':%d ' % port) in host.cmd('ss -ltn'):
            return proc
        time.sleep(0.2)
    proc.kill()
    raise RuntimeError('iperf3 server on %s never listened on port %d' % (host.name, port))


def iperf_client(client, server_ip, opts='', port=5201, server_proc=None):
    """Run the iperf3 client with JSON output. `opts` is the option string you wrote."""
    out = client.cmd('iperf3 -c %s -p %d -J --connect-timeout 5000 %s' % (server_ip, port, opts))
    if server_proc is not None:
        try:
            server_proc.wait(timeout=10)
        except Exception:
            server_proc.kill()
    try:
        j = json.loads(out[out.index('{'):])
    except Exception:
        raise RuntimeError('iperf3 output is not JSON:\n' + out[:1500])
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


def ping(src, dst_ip, count=5, interval=0.2):
    """Return {'min','avg','max','mdev','samples','raw'} (ms)."""
    out = src.cmd('ping -c %d -i %s -W 2 %s' % (count, interval, dst_ip)).replace('\r', '')
    m = re.search(r'= ([\d.]+)/([\d.]+)/([\d.]+)/([\d.]+) ms', out)
    res = {'raw': out.strip(), 'samples': len(re.findall(r'time=', out))}
    if m:
        res.update(dict(zip(('min', 'avg', 'max', 'mdev'), (float(x) for x in m.groups()))))
    return res


def read_tc(node, intf):
    """Read back what TCLink hung on an interface: htb rate, netem delay / loss."""
    out = node.cmd('tc qdisc show dev %s' % intf).replace('\r', '')
    cls = node.cmd('tc class show dev %s' % intf).replace('\r', '')
    res = {'qdisc': out.strip(), 'class': cls.strip(),
           'rate_mbit': None, 'delay_ms': None, 'loss_pct': None}
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


FEATURE_NAMES = {'tso': 'tcp-segmentation-offload', 'gso': 'generic-segmentation-offload',
                 'gro': 'generic-receive-offload', 'tx': 'tx-checksumming',
                 'rx': 'rx-checksumming', 'sg': 'scatter-gather'}


def read_features(node, intf, keys=('tso', 'gso', 'gro')):
    """Read offload state back with `ethtool -k` -- read, never assume."""
    out = node.cmd('ethtool -k %s' % intf)
    got = {}
    for k in keys:
        m = re.search(r'^%s:\s*(on|off)' % re.escape(FEATURE_NAMES[k]), out, re.M)
        got[k] = m.group(1) if m else 'unknown'
    return got


def sysctl(node, key):
    return node.cmd('sysctl -n %s' % key).strip()


def write_json(name, obj):
    os.makedirs(DATA, exist_ok=True)
    path = os.path.join(DATA, name + '.json')
    obj = dict(obj)
    obj.setdefault('written_at', time.strftime('%Y-%m-%dT%H:%M:%S'))
    obj.setdefault('kernel', os.uname().release)
    with open(path, 'w') as f:
        json.dump(obj, f, indent=2)
    print('\nwrote %s' % os.path.relpath(path, REPO))
    return path


def unimplemented(tag):
    raise SystemExit('unfinished: %s -- read the comment above that TODO' % tag)
