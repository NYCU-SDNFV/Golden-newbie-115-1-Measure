# Lab 2 — Measurement + Datapath Tuning

**SDNFV (CSIC30127), 115-1 — NYCU Institute of Network Engineering**

> Lectures this lab draws on: measurement methodology, kernel datapath and offloads,
> TCP congestion control and AQM. Deadline and the date of the in-person session are
> announced on E3. Lab 0 must be green before you start.
>
> **You may use AI tools for the take-home part.** You are responsible for being able
> to explain every line and every number you submit — see section 6.

---

## 0. What this lab is really asking

Not "type the commands". Three things:

1. **Measure correctly.** Tell line rate, throughput and goodput apart, and know *why*
   each number is what it is.
2. **Tune with understanding.** Know what each knob (socket window, offload,
   congestion control, qdisc / AQM) changes, and what it costs.
3. **Argue from data.** Given an anomaly, state two competing hypotheses and design
   single-variable experiments that decide between them.

Absolute numbers vary by ±10–20 % (more between a laptop, WSL 2 and the CI runner).
**Everything is graded on relations and explanations — who is bigger than whom, by
roughly how much, and why — never on hitting a particular value.** Copying someone
else's numbers therefore gains nothing and is easy to spot.

## 1. Grading and the AI policy — read this first

| part | conditions | weight |
|---|---|---|
| Take-home: A1–A4, B1–B2, report | at home, **AI allowed**, autograded on every push | 40 % of this lab |
| In-person checkpoint: diagnose an injected misconfiguration, 15 min | proctored, **no personal AI** | 35 % |
| In-person viva: predict-then-observe on *your own* harness, defend *your own* Part B | proctored, **no personal AI** | 25 % |

- The autograder (this repository's `tests/`) gives the take-home score out of 100;
  that score is 40 % of the lab. It is fully visible: `make test` runs the same checks
  as CI, and every failed relation prints what it expected and a hint.
- The in-person 60 % is where the grade is decided, and it is built **entirely on what
  you did at home** (section 6). That is deliberate: an expensive AI cannot buy those
  points; understanding your own experiment can.
- In the checkpoint and viva you may use `man`, `--help` and the lecture slides. No
  chat assistants, no notes from other people.
- Log how you used AI in `report/ai-usage.md` (what you asked, what it suggested,
  what you adopted or rejected and why). An honest log never costs points.

**Protected-file integrity is a whole-lab gate:** any mismatch before or during
grading makes the entire take-home score **0/100**, not just a loss of policy
points. An obsolete starter can also trigger this gate. Run `make check-update`
and `make update`, merge the resulting update branch, and resubmit;
never edit protected files or their hashes.

## 2. Environment

Same container as Lab 0, one difference: **this lab needs the OVS kernel datapath**
(A3 does not work on the userspace one — the docstring of `harness/e4_offload.py`
explains why). Lab 0 check 6 printed a `DATAPATH-PROBE` line for your machine; if it
said `kernel_dp=yes` you are fine.

Before starting, run the non-scoring `make pretest`. If it reports a
host prerequisite, follow the [course environment preparation guide](.github/golden/README.md)
on the machine that actually runs the Docker Engine. The pretest uses isolated
privileged probes and does not change host sysctl policy or your answers.
Probes can trigger normal Linux module autoload; use an authorized dedicated lab
VM, not a shared production Docker host.

- **Windows: work inside WSL 2**, never Git Bash or PowerShell (they rewrite paths and
  have no `make`). Docker Desktop + WSL 2 has been verified to run every check here.
- **Linux:** any distribution whose kernel ships the `openvswitch` module (all
  mainstream ones).
- **macOS:** the Docker VM kernel may lack the module. If `make up` fails check 0, do
  not fight it: **push, and take your numbers from the CI run** (every push runs the
  full measurement on GitHub and attaches the output to a Release). Say so in the
  report's environment line.

```bash
make pretest     # diagnose the Docker engine host; this does not award points
make up          # build + start the `lab2` container (compose file is given in full)
make test        # policy + every autograded check, exactly what CI runs
make a1 a2 a3    # run one exercise at a time while you work on it
make a4 b1 b2
make plot        # figures into figs/
make shell       # poke around inside the container
make clean       # tear down, including stale Mininet / netns state
```

### Keep the starter up to date

Run `make help` for the update and resubmission sequence. Commit or stash your
answers, measured `data/`, and figures before updating; do not delete your work
just to clear a dirty-tree warning.

Prefer committing and pushing your Classroom default branch from your Linux
or WSL checkout. `gh student submit` creates a remote snapshot, so verify that
your local work commits were pushed and fetch/merge any new remote commit
before continuing locally. The tested native-Windows v1.52.1 CLI can lose
executable modes while snapshotting; a normal Linux/WSL Git push preserves the
committed modes and history.

Install Python 3 on your host as well as Git, Make and Docker. `make test` first
checks the public template's latest release. A required update stops the command;
an optional one prints a notice. Network or metadata failures are explicit errors,
not proof that your checkout is current. Use `make check-update` to retry.
`make up` does not contact the release server.

The Python harness and plotting helpers include parameter and return annotations.
Mininet 2.3 itself does not publish typing metadata, so `typings/mininet/` supplies
only the small API surface this lab uses; `pyrightconfig.json` lets Pylance and
Pyright find it without installing Mininet on your host. `labkit.get_node()` also
checks and narrows named hosts and switches instead of leaving `net.get()` as
`Unknown`.
The stubs preserve binary subprocess output and optional command/address
results. `labkit.cmd()` and `labkit.host_ip()` check these boundaries instead
of promising text that Mininet did not return. Empty student collections also
retain their element types. Instructor CI checks the actual generated starter,
rejects intentionally wrong contracts, and tests the stubs against the pinned
Mininet runtime; these non-scoring checks do not require students to install
additional packages.
Collection declarations are kept separate from editable answer assignments so
the normal three-way updater can preserve completed work. The unfinished
`gbps_per_cpu()` placeholder retains its existing `None` sentinel, reflected
in its annotation; its caller already reports this as unfinished.

Updates are **manual**: publication does not open update PRs or modify accepted
student repositories. Your protected `.lab-release.json` selects the public
Measurement template for your channel; do not change it to switch assignments.

After committing or stashing all changes, including untracked files, `make update`
prepares an `instructor/update-<tag>` branch using a three-way diff between your old
and new template tags. It preserves your work and Classroom configuration, commits
with your Git identity, and never pushes. Review and merge the update branch using
the printed commands, run `make test`, then push your default branch to resubmit.
If there are conflicts, resolve and commit them on the update branch before merging;
do not rerun the updater over an existing update branch.
The final commit honors your configured Git hooks and signing policy. If either
rejects it, the updater does not bypass that policy: inspect the staged update,
fix the reported hook/signing issue and commit before merging.

For an explicitly offline checkpoint or viva, `make test-offline` runs the same
integrity and lab checks while clearly skipping remote freshness. This is never
a fallback for a failed online check. Official grading uses canonical protected
files and release metadata rather than relying on that network request.

Known traps, so that you do not lose time on things unrelated to this lab:

- Mininet: call `net.start()` only — never `net.build()` yourself (`veth File exists`).
- `controller=None` needs `failMode="standalone"`, or the switch forwards nothing.
  `labkit.kernel_switch()` sets both for you.
- A run that died half-way leaves namespaces behind: `make clean`, then retry.
- `iperf3 -s -D` is unreliable inside a container; `labkit.start_iperf_server()` does
  it properly. Do not "simplify" it back.
- Keep the supplied `ulimits.nofile` setting. Some Docker hosts otherwise give the
  container a billion-descriptor limit, making Mininet's `mnexec` spend minutes
  closing nonexistent descriptors before the first host starts. The preflight
  reports this separately from OVS or AppArmor failures.

## 3. What you change

| file | TODOs | exercise |
|---|---|---|
| `harness/e1_baseline.py` | A1-1 … A1-4 | A1 |
| `harness/e2_bdp.py` | A2-1 … A2-5 | A2 |
| `harness/e4_offload.py` | A3-1 … A3-3 | A3 |
| `harness/qdiscs.conf` | A4-1, B1-1 | A4, B1 |
| `harness/e5_aqm.sh` | A4-3 (report only) | A4, B1 |
| `harness/e3_cc_loss.py` | B2-1 … B2-3 | B2 |
| `report/REPORT.md`, `report/ai-usage.md` | fill in | all |

Everything else — `Makefile`, `Dockerfile`, `docker-compose.yml`, `harness/labkit.py`,
`tools/`, `tests/`, `.github/` — is given and **must not be modified**. Editing a test
to make it pass is an academic-integrity violation and gains nothing: CI runs from a
clean checkout and re-runs *your harness* itself; it never trusts the JSON you commit.

Each TODO is numbered. A skeleton that runs is not a skeleton that is right: wrong
parameters give numbers that look perfectly normal and are physically wrong. Telling
the two apart is the point of this lab.

## 4. Part A — harness and basic measurements

Topology throughout: `h1 — s1 — h2` (Mininet, TCLink, OVS kernel datapath, no
controller). For every exercise you hand in **numbers plus one paragraph on why each
number is what it is**.

### A1. Baseline throughput / goodput / RTT — `harness/e1_baseline.py`
Both links `bw=100 Mbit, delay=10 ms`. iperf3 for TCP throughput, ping for RTT.

Answer in the report: why do the iperf3 sender and receiver lines differ, and **which
one is goodput**? Why does it not reach 100 Mbit/s — break the gap down (which layer
does TCLink shape? how much is header overhead? retransmissions?). How does the
measured RTT relate to the delay you configured — write the formula. Why exclude
slow-start from the statistics?

### A2. Bandwidth-delay product — `harness/e2_bdp.py`
Raise the RTT to **200 ms** at the same 100 Mbit and sweep at least three socket
windows with `iperf3 -w` (one clearly too small, one in between, the default).

Answer: write the BDP formula and compute it for this path. **Predict** every window's
throughput ceiling from the BDP *before* looking at the measurement, then compare and
explain the gap. Conclude: what limits throughput here — bandwidth, receiver window,
socket buffer? Why does the default win, and what sysctl bounds it?

### A3. Offload vs CPU — `harness/e4_offload.py`
Unshaped veth (no `bw=`). Toggle TSO + GSO + GRO with `ethtool -K` and measure
throughput **and sender CPU** (`iperf3 -J` reports `cpu_utilization_percent`).

Answer: record the **default** state first (one of the three is off on a veth — which,
and why?). **Comparing throughput alone loses points**: compute Gbit/s per CPU and
conclude with that. What cost do TSO/GSO amortise? Why can the sender CPU be saturated
in both runs?

### A4. Latency under load — `harness/qdiscs.conf`, `harness/e5_aqm.sh`, `tools/plot_cdf.py`
A **10 Mbit** bottleneck (htb), a bulk TCP flow filling it, and a ping probe sharing
the same egress queue. Size the `bloat` FIFO yourself so that it builds up roughly
300 ms of queueing delay — show the calculation. Plot the RTT CDF.

Answer: idle vs loaded RTT — is the extra delay **propagation or queueing**, and how
do you prove it (`tc -s qdisc` backlog / drops)? What is this phenomenon called, and how
does it relate to buffer depth?

## 5. Part B — design and hypothesis testing

There is no single right answer. Marks go to method and to data that supports the
conclusion. AI may help you find commands; the reasoning is yours — the viva asks
about it.

### B1. Pareto frontier: goodput vs tail latency — `harness/qdiscs.conf`, `make b1`, `tools/plot_pareto.py`
Same 10 Mbit bottleneck. SLO: **goodput ≥ 9 Mbit/s and P99 RTT ≤ 20 ms.**

Add at least two more settings to `harness/qdiscs.conf` (a smaller FIFO, an AQM such
as `fq_codel` or `codel`, a shallow FIFO that starts dropping, …). `make b1` runs every
setting and builds `data/pareto.csv`; `make plot` draws goodput vs P99 and marks
dominated points.

Hand in: at least three points, each with goodput / P50 / P99; the plot with the
frontier and the SLO region; which points are **dominated** and why nobody should pick
them; where the real trade-off lies; which setting you would choose, defended with your
own numbers. One data point is not a frontier.

### B2. Measurement as science: two competing hypotheses — `harness/e3_cc_loss.py`
Scenario: a box on a **high-RTT path with random loss** has very low throughput.

Hand in: two **mutually exclusive, falsifiable** hypotheses (one sentence each, naming
the mechanism); one **single-variable** experiment per hypothesis (the harness gives
you the loop for both: vary the congestion-control algorithm with the window fixed;
vary the window with the algorithm fixed); the two results; and the verdict the numbers
force. "It is probably packet loss" without a controlled experiment is half marks.

## 6. The in-person session — how to prepare so that the work you did is enough

The in-person 60 % is not a separate exam with new material. Every question is anchored
in a TODO you completed at home. Concretely:

**Checkpoint (35).** A TA injects one misconfiguration into a fresh copy of your
environment and you have 15 minutes to observe, diagnose, fix and explain. The
misconfiguration is drawn from the **five knob families this lab makes you turn**:

| family | you met it in | commands to be fluent in |
|---|---|---|
| queue discipline / AQM and buffer depth | A4, B1 | `tc -s qdisc show`, `tc class show` |
| offloads | A3 | `ethtool -k`, `ethtool -K` |
| congestion control | B2 | `sysctl net.ipv4.tcp_congestion_control`, `…tcp_available_congestion_control` (know which algorithms are loss-based and which are not) |
| socket buffers / autotuning | A2 | `sysctl net.ipv4.tcp_rmem tcp_wmem`, `net.core.rmem_max` |
| emulated impairments | A1, A2, B2 | `tc qdisc show` (netem delay / loss), `ip -s link`, `ss -ti` |

Marks: diagnosis 15 (you name the right knob from observations, not by guessing),
fix 10, explanation 10. **A correct fix with no mechanism is capped at 25; a correct
mechanism with a failed fix also earns 25.**

**Viva (25).**
- *V1 — predict, then observe (15).* The TA opens **your** repository, changes **one**
  parameter you set in one of your TODOs, and asks you to write down what will happen
  to throughput and latency *before* the run. You then run it together. Marks for the
  direction and the stated premise of your prediction, and for explaining any gap
  afterwards. Every knob you turned in A1–B2 is fair game; nothing you did not touch is.
- *V2 — defend your Part B (10).* With your `report/REPORT.md` open: why this setting on
  the frontier and not a bigger buffer? How did you rule out the other hypothesis? Point
  at your own numbers.

How to prepare: for every TODO you filled in, be able to say **what it changes, in
which direction the result moves if you double or halve it, and why**. If you can do
that for all of them, you have prepared for the whole session. If you cannot answer a
question about a number in your own report, that question scores 0 and the take-home
part is re-examined.

## 7. Submission

Push to your Classroom repository; every push is autograded and the result appears as
a Release in your repository. **Commit your measurements and figures** (`data/*.json`,
`data/*.txt`, `data/*.csv`, `figs/*.png`) — they are part of the submission and the
report is checked against them. Also upload `report/REPORT.md` as a PDF on E3.

Your last push before the deadline is what counts. Commit as you work (the git check
wants at least three commits of your own), not one dump at the end.

### What check R (report, 3 points) looks at

The rules below are the whole check; nothing else in your report is parsed. The TA
reads the content itself.

- `report/REPORT.md`, `report/ai-usage.md`, both figures and `data/a1.json`,
  `data/a3.json`, `data/pareto.csv` are committed.
- `report/REPORT.md` keeps the six headings `## A1` ... `## B2`, and its title line no
  longer contains `<student id>`.
- Under each of `## A1`, `## A2`, `## A3`, `## B1` and `## B2`, the grader reads **only
  the first table whose first header cell is** `metric`, `window`, `setting`, `label`
  and `experiment` respectively (the template tables). Every row you keep needs text in
  every column (write `n/a` if a value does not apply); completely empty rows are
  ignored. Minimum complete rows: A1 3, A2 3, A3 2, B1 3, B2 2.
- Extra tables, lists and prose anywhere else are never parsed, so they cannot break
  the check. Words such as `TODO` are not searched for.
- `figs/a4_cdf.png` and `figs/b1_pareto.png` exist (more than 1 kB) and their file names
  appear in the report.
- `report/ai-usage.md`: at least one numbered row of the `| # | what I asked | ...` table
  has text in all five columns. If you used no AI at all, write
  `| 1 | no AI used | none | - | - |`.

### Trying a newer starter without losing your work

Lab 2 uses the `lab2-measure` assignment: staging is on `newbie-115-1`, and the
formal course is on `115-1`. Patches within your channel use `make update`.
Old Lab 1 assignments and their `Golden-newbie-Measure` template remain separate;
there is no automatic or cross-channel migration. If your instructor asks you
to move to Lab 2, accept its new assignment and keep your old repository as a
backup; its history and grades are not transferred. Bring over only your answers:

- `harness/e1_baseline.py`, `harness/e2_bdp.py`, `harness/e3_cc_loss.py`,
  `harness/e4_offload.py`, and `harness/qdiscs.conf`;
- your text in `report/REPORT.md` and `report/ai-usage.md`.

Keep the new starter's `Makefile`, `docker-compose.yml`, `harness/labkit.py`,
`harness/e5_aqm.sh`, `tools/`, `tests/`, and `.github/` unchanged. Do not copy the
entire old `harness/` directory over them. Run `make up`, regenerate your measurements
and figures, and run `make test` in the new repository before submitting.
