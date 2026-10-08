# SDNFV Lab 2 Report -- <student id> <name>

Environment: host OS / Docker flavour (Docker Desktop + WSL 2, Linux, ...), host kernel
(`uname -r` inside the container), CPU count, date of the runs.

> The TAs re-run your harness. Every number below must be traceable to a file in
> `data/`. Keep the section headings exactly as they are: the autograder looks for them.
> The autograder reads only the first table under A1, A2, A3, B1 and B2 (the tables below,
> found by their first header cell). Every row you keep needs text in every column; write
> `n/a` if a value does not apply. Your own extra tables are welcome and are not parsed.
> Submit this same report as a PDF on E3 as well.

---

## A1. Baseline throughput / goodput

| metric | value |
|---|---|
| iperf3 sender (Mbit/s) | |
| iperf3 receiver (Mbit/s) | |
| RTT min/avg/max/mdev (ms) | |

- Which number is receiver goodput? Explain the two application-byte counters, their
  measurement intervals, and buffered/in-flight bytes. Retransmissions are a separate counter.
- Why is it not 100 Mbit/s? Break the gap down: at which layer does TCLink shape? how
  much is header overhead? retransmissions?
- Formula relating the measured RTT to the configured link delay:
- Why did you exclude slow-start (`-O`) from the statistics?

## A2. Bandwidth-Delay Product

- BDP formula and value for this path:
- Prediction vs measurement:

| window | predicted ceiling (Mbit/s) | measured (Mbit/s) | why they differ |
|---|---|---|---|
| | | | |
| | | | |
| | | | |

- Conclusion: what limits throughput here? Why does the default window win? (quote the
  sysctl values you read)

## A3. Offload and CPU efficiency

| setting | goodput (Gbit/s) | sender CPU (%) | Gbit/s per CPU |
|---|---|---|---|
| offload on | | | |
| offload off | | | |

- Which of the three features is off by default on a veth, and why?
- Mechanism: what cost do TSO/GSO amortise? Why can the sender CPU be saturated in both runs?
- One-sentence conclusion, stated in Gbit/s per CPU, not raw throughput:

## A4. Latency under load

- Idle RTT vs loaded RTT:
- How you sized the `bloat` buffer (show the calculation):
- CDF figure: `figs/a4_cdf.png` -- p50 / p90 / p99:
- Is the extra delay queueing or propagation? Evidence (include the `tc -s qdisc`
  backlog / drop counters):

---

## B1. Pareto frontier (goodput vs tail latency)

SLO: goodput >= 9 Mbit/s AND P99 RTT <= 20 ms

| label | leaf qdisc | goodput | P50 | P99 | meets SLO? |
|---|---|---|---|---|---|
| | | | | | |
| | | | | | |
| | | | | | |

- Figure: `figs/b1_pareto.png`
- Which points are dominated, and why is there no reason to pick them?
- Where is the real trade-off? (At what point does tuning start to cost you something?)
- Which setting would you choose? Defend it with your own numbers -- the viva asks about this.

## B2. Two competing hypotheses

- Hypothesis H1 (mechanism, one sentence):
- Hypothesis H2 (mechanism, one sentence):
- Why they are mutually exclusive and falsifiable:

| experiment | variable changed | held fixed | result |
|---|---|---|---|
| E1 (tests H_) | | | |
| E2 (tests H_) | | | |

- Verdict and evidence (point at the numbers):
- If both experiments had shown an effect, how would you cut next?

---

## Appendix: how to reproduce

```
make up
make a1 a2 a3 a4 b1 b2 plot
```
