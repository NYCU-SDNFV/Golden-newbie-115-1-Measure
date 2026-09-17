#!/bin/sh
# Check 0 - the container is up, has the tools, sees the repo, and can run the
# OVS kernel datapath (A3 needs it). Do not modify.
. "$(dirname "$0")/lib.sh"
banner "check 0: environment"

require_container
pass "container '$CONTAINER' is running"

for tool in mn ovs-vsctl ovs-dpctl iperf3 ethtool tc ip ping ss python3; do
  dexec sh -c "command -v $tool >/dev/null 2>&1" \
    || die "'$tool' not found inside the container" "the image should provide it; did you change the Dockerfile?"
done
dexec python3 -c 'import matplotlib' 2>/dev/null \
  || die "python3-matplotlib missing inside the container" "pull the current base image: make clean && make up"
pass "toolchain present (mn ovs iperf3 ethtool tc ss matplotlib)"

dexec test -f /workspace/harness/labkit.py \
  || die "/workspace/harness/labkit.py is not visible inside the container" "the repository must be mounted at /workspace"
pass "repository mounted at /workspace"

# Kernel datapath: `ovs-vsctl add-br` returns 0 even when the datapath is never
# created, so ask the datapath itself.
BR=lab2dpchk
dexec ovs-vsctl --if-exists del-br "$BR" >/dev/null 2>&1
dexec ovs-vsctl add-br "$BR" -- set bridge "$BR" datapath_type=system >/dev/null 2>&1
sleep 1
if dexec ovs-dpctl show 2>/dev/null | grep -q '^system@'; then
  dexec ovs-vsctl --if-exists del-br "$BR" >/dev/null 2>&1
  pass "OVS kernel datapath is available (system@ovs-system)"
else
  dexec ovs-vsctl --if-exists del-br "$BR" >/dev/null 2>&1
  die "the OVS kernel datapath could not be created on this host" \
      "Lab 0 check 6 predicts this. On Linux/WSL 2: is the openvswitch module loadable? On macOS this lab's numbers come from CI"
fi

WMAX=$(dexec sysctl -n net.core.wmem_max 2>/dev/null)
if [ "${WMAX:-0}" -ge 8388608 ]; then
  pass "socket-buffer ceiling net.core.wmem_max=$WMAX (iperf3 -w up to that value works)"
else
  die "net.core.wmem_max=$WMAX is too low for A2/B2 (iperf3 -w above ~200K fails)" \
      "make up lifts it via nsenter; if that failed, on a Linux host run: sudo sysctl -w net.core.rmem_max=67108864 net.core.wmem_max=67108864"
fi

CC=$(dexec sysctl -n net.ipv4.tcp_available_congestion_control 2>/dev/null)
printf '      available congestion control: %s\n' "$CC"
echo "$CC" | grep -qw bbr || printf '      note: bbr is not loaded here; B2 needs it (host: sudo modprobe tcp_bbr)\n'
printf '      kernel %s | %s\n' "$(dexec uname -r)" "$(dexec ovs-vsctl --version | head -1)"
