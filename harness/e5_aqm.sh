#!/bin/bash
# A4 / B1 -- latency under load: one bottleneck queue + bulk TCP + a ping probe
#
# Run:   make a4                  (label `bloat`)
#        make b1                  (every label in harness/qdiscs.conf)
#        docker exec lab2 bash /workspace/harness/e5_aqm.sh <label>
# Writes: data/e5_<label>.{iperf,ping,csv,json}
#
# This one uses two network namespaces and a veth pair instead of Mininet, because
# a single, cleanly controlled bottleneck queue is easier to reason about that way.
# The leaf qdisc under test comes from harness/qdiscs.conf (see the TODOs there).
set -u
LABEL="${1:?usage: $0 <label>   (a label from harness/qdiscs.conf)}"
HERE="$(cd "$(dirname "$0")" && pwd)"
OUT="$HERE/../data"
CONF="$HERE/qdiscs.conf"
mkdir -p "$OUT"

# ---- parameters -------------------------------------------------------------
RATE="10mbit"          # the bottleneck rate. Fixed by the assignment -- do not change.
PING_COUNT=80          # RTT samples; a CDF needs this order of magnitude to show its tail
PING_INTERVAL=0.1
BULK_SEC=14
# -----------------------------------------------------------------------------

LEAF_QDISC=$(awk -v l="$LABEL" '$0 !~ /^[[:space:]]*#/ && $1==l { $1=""; sub(/^[[:space:]]+/, ""); print; exit }' "$CONF")
if [ -z "$LEAF_QDISC" ]; then
  echo "no line labelled '$LABEL' in harness/qdiscs.conf" >&2; exit 2
fi
case "$LEAF_QDISC" in *TODO*|*'?'*) echo "unfinished: TODO in harness/qdiscs.conf for label '$LABEL'" >&2; exit 2;; esac

cleanup() {
  ip netns del nsA 2>/dev/null
  ip netns del nsB 2>/dev/null
  ip link del vethA 2>/dev/null
}
trap cleanup EXIT
cleanup

ip netns add nsA; ip netns add nsB
ip link add vethA type veth peer name vethB
ip link set vethA netns nsA; ip link set vethB netns nsB
ip netns exec nsA ip addr add 10.10.0.1/24 dev vethA
ip netns exec nsB ip addr add 10.10.0.2/24 dev vethB
ip netns exec nsA ip link set vethA up; ip netns exec nsA ip link set lo up
ip netns exec nsB ip link set vethB up; ip netns exec nsB ip link set lo up

# The bottleneck: htb on nsA's egress, and the leaf qdisc under test below it.
ip netns exec nsA tc qdisc add dev vethA root handle 1: htb default 10
ip netns exec nsA tc class add dev vethA parent 1: classid 1:10 htb rate "$RATE"
if ! ip netns exec nsA tc qdisc add dev vethA parent 1:10 handle 20: $LEAF_QDISC; then
  echo "tc rejected the leaf qdisc spec for '$LABEL': $LEAF_QDISC" >&2; exit 2
fi

echo "QDISC($LABEL): $(ip netns exec nsA tc qdisc show dev vethA | tr '\n' ' ')"

# Idle RTT first (no bulk traffic) -- your control. The report has to use idle vs
# loaded RTT to show that the extra delay is queueing, not propagation.
IDLE_PING=$(ip netns exec nsA ping -c 10 -i 0.1 -q 10.10.0.2 | tail -1)
echo "IDLE_RTT($LABEL): $IDLE_PING"
IDLE_AVG=$(echo "$IDLE_PING" | sed -nE 's#.*= [0-9.]+/([0-9.]+)/.*#\1#p')

ip netns exec nsB iperf3 -s -1 -p 5201 >/dev/null 2>&1 &
for _ in $(seq 1 40); do ip netns exec nsB ss -ltn | grep -q ':5201 ' && break; sleep 0.25; done
ip netns exec nsA iperf3 -c 10.10.0.2 -t "$BULK_SEC" -O 1 -p 5201 -J > "$OUT/e5_${LABEL}.iperf" 2>&1 &
sleep 2
# The probe shares the same egress queue as the bulk flow, so what it measures IS the queueing delay.
ip netns exec nsA ping -c "$PING_COUNT" -i "$PING_INTERVAL" 10.10.0.2 > "$OUT/e5_${LABEL}.ping" 2>&1
# The bulk flow is still active here; after wait the queue has already drained.
TC_STATS=$(ip netns exec nsA tc -s qdisc show dev vethA)
wait

# TODO(A4-3): after the run, look at the saved `tc -s qdisc show` and put the backlog / drop
#   counters in your report -- they are the direct evidence of packets sitting in the queue.
echo "TC_STATS($LABEL):"; echo "$TC_STATS" | sed 's/^/    /'

grep "time=" "$OUT/e5_${LABEL}.ping" | sed -E 's/.*time=([0-9.]+).*/\1/' > "$OUT/e5_${LABEL}.csv"
N=$(wc -l < "$OUT/e5_${LABEL}.csv")
GOODPUT=$(python3 -c 'import json,sys
try:
    j=json.load(open(sys.argv[1])); print(round(j["end"]["sum_received"]["bits_per_second"]/1e6,3))
except Exception: print("")' "$OUT/e5_${LABEL}.iperf")
read -r P50 P90 P99 <<<"$(sort -n "$OUT/e5_${LABEL}.csv" | awk '
  function idx(q) { i = int(q * NR); if (i < 1) i = 1; return i }
  { a[NR] = $1 }
  END { if (NR == 0) { print "  "; exit } printf "%.3f %.3f %.3f", a[idx(0.50)], a[idx(0.90)], a[idx(0.99)] }')"

echo "IPERF($LABEL): goodput=${GOODPUT:-?} Mbps"
echo "PING($LABEL):  n=${N} p50=${P50:-?} p90=${P90:-?} p99=${P99:-?} ms   (idle avg ${IDLE_AVG:-?} ms)"

E5_LABEL="$LABEL" E5_LEAF="$LEAF_QDISC" E5_RATE="$RATE" E5_IDLE="${IDLE_AVG:-}" E5_GOODPUT="${GOODPUT:-}" \
E5_N="$N" E5_P50="${P50:-}" E5_P90="${P90:-}" E5_P99="${P99:-}" E5_TC="$TC_STATS" \
python3 - "$OUT/e5_${LABEL}.json" <<'PY'
import json, os, sys, time
e = os.environ
num = lambda k: (float(e[k]) if e.get(k, "").strip() else None)
json.dump({
  "exercise": "e5", "label": e["E5_LABEL"], "leaf_qdisc": e["E5_LEAF"], "rate": e["E5_RATE"],
  "idle_rtt_avg_ms": num("E5_IDLE"), "goodput_mbps": num("E5_GOODPUT"), "samples": int(e["E5_N"]),
  "p50_ms": num("E5_P50"), "p90_ms": num("E5_P90"), "p99_ms": num("E5_P99"),
  "tc_stats": e["E5_TC"],
  "written_at": time.strftime("%Y-%m-%dT%H:%M:%S"), "kernel": os.uname().release,
}, open(sys.argv[1], "w"), indent=2)
print("wrote data/e5_%s.json" % e["E5_LABEL"])
PY
