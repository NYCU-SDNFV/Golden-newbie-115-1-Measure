#!/usr/bin/env python3
"""Lab 2 relational grader. Do not modify (protected).

Usage: python3 tests/grade.py <a1|a2|a3|a4|b1|b2|report>

Reads the JSON your harness just wrote under data/ and checks RELATIONS, never
absolute numbers: who is bigger than whom, by roughly how much, whether what you
configured is what the kernel reports back. Every rule prints its verdict so you
can see exactly which relation failed and why. Exit 0 = all rules hold.

Thresholds are deliberately loose (2x, 5x, +-10 %) because the same experiment
lands at very different absolute values on a laptop, in WSL 2 and on a CI runner.
The physics is the same everywhere; that is what is checked.
"""
import json
import math
import os
import re
import sys

# Classroom 50 runs this file from its bundle, with cwd set to the student repo.
ROOT = os.path.abspath(os.getcwd())
DATA = os.path.join(ROOT, 'data')

_fails = 0


def ok(msg):
    print('  PASS  ' + msg)


def fail(msg, hint=None):
    global _fails
    _fails += 1
    print('  FAIL  ' + msg)
    if hint:
        print('        hint: ' + hint)


def check(cond, msg, hint=None):
    (ok if cond else lambda m: fail(m, hint))(msg)
    return bool(cond)


def load(name):
    path = os.path.join(DATA, name + '.json')
    if not os.path.exists(path):
        fail('%s does not exist' % os.path.relpath(path, ROOT),
             'the harness did not finish; read its output above (unfinished TODO? error?)')
        finish()
    with open(path) as f:
        return json.load(f)


def finish():
    print('\n--- %s ---' % ('all relations hold' if _fails == 0 else '%d relation(s) failed' % _fails))
    sys.exit(0 if _fails == 0 else 1)


def num(x, default=0.0):
    try:
        return float(x)
    except (TypeError, ValueError):
        return default


def opt_value(opts, flag):
    m = re.search(r'(?:^|\s)%s\s*(\S+)' % re.escape(flag), opts or '')
    return m.group(1) if m else None


# ---------------------------------------------------------------------------
def grade_a1():
    j = load('a1')
    link = j.get('link', {})
    rate, delay = link.get('rate_mbit'), link.get('one_way_delay_ms')
    check(j.get('datapath_type') == 'system', 'switch runs the kernel datapath (%s)' % j.get('datapath_type'))
    if check(rate is not None and delay is not None,
             'both links are shaped (tc reports rate=%s Mbit, delay=%s ms)' % (rate, delay),
             'TODO(A1-1): addLink(..., bw=..., delay=...) -- nothing was found on h2-eth0'):
        check(abs(num(rate) - 100) < 1, 'link rate is 100 Mbit (got %s)' % rate)
        check(abs(num(delay) - 10) < 0.5, 'one-way link delay is 10 ms (got %s)' % delay,
              'TCLink delay is per link, one direction; the assignment says 10 ms')
    opts = j.get('client_opts', '')
    t, o = opt_value(opts, '-t'), opt_value(opts, '-O')
    check(t is not None and num(t) >= 5, 'iperf3 runs for >= 5 s (-t %s)' % t, 'TODO(A1-2)')
    check(o is not None and num(o) >= 1, 'slow-start is omitted from the statistics (-O %s)' % o,
          'TODO(A1-2): iperf3 -O <seconds>')
    ip = j.get('iperf', {})
    s, r = num(ip.get('sender_mbps')), num(ip.get('receiver_mbps'))
    if rate:
        check(0.80 * num(rate) <= r <= 1.02 * num(rate),
              'receiver goodput is 80-100 %% of the shaped rate (%.1f of %s Mbit)' % (r, rate),
              'far below: something else is limiting (RTT? window?); far above: the link is not shaped')
    check(s >= 0.97 * r, 'sender and receiver agree within 3 %% or sender is higher (%.1f vs %.1f)' % (s, r),
          'the receiver can never see more than was sent; with -O the two sums may differ slightly')
    check(j.get('goodput_is') == 'receiver', 'goodput taken from the receiver side (you chose: %s)' % j.get('goodput_is'),
          'TODO(A1-3): sender counts application bytes accepted by the socket; receiver counts delivered bytes. '
          'Buffered/in-flight data and measurement intervals can differ; TCP retransmissions are counted separately')
    rtt = j.get('rtt_ms', {})
    check(num(rtt.get('samples')) >= 5, 'RTT measured with >= 5 samples (%s)' % rtt.get('samples'))
    if delay:
        avg = num(rtt.get('min'))
        check(3.4 * num(delay) <= avg <= 4.6 * num(delay),
              'RTT ~= 4 x one-way link delay (min %.1f ms vs delay %s ms)' % (avg, delay),
              'two links, two directions -- how many delay stages does a round trip cross?')


def grade_a2():
    j = load('a2')
    rtt = num(j.get('rtt_ms'))
    check(180 <= rtt <= 230, 'RTT is ~200 ms (measured %.1f ms)' % rtt,
          'TODO(A2-1): recall the RTT/delay relation you found in A1')
    rate = num(j.get('link', {}).get('rate_mbit'), 100)
    bdp_expect = rate * 1e6 * (rtt / 1000.0) / 8.0
    bdp = num(j.get('bdp_bytes'))
    check(bdp > 0 and abs(bdp - bdp_expect) / bdp_expect < 0.10,
          'bdp_bytes matches bandwidth x RTT (%.0f vs expected %.0f bytes)' % (bdp, bdp_expect),
          'TODO(A2-3): Mbit/s x seconds gives bits; bytes are bits / 8')
    runs = j.get('runs', [])
    explicit = [r for r in runs if r.get('window')]
    default = [r for r in runs if not r.get('window')]
    check(len(runs) >= 3, 'at least three windows were swept (%d)' % len(runs), 'TODO(A2-2)')
    check(len(default) == 1, 'exactly one default/autotune run ("" in WINDOWS)')
    check(len(explicit) >= 2, 'at least two explicit windows')
    if explicit and bdp > 0:
        smallest = min(explicit, key=lambda r: num(r.get('window_bytes')))
        check(num(smallest['window_bytes']) < 0.5 * bdp,
              'smallest window is clearly below the BDP (%s bytes < 0.5 x %.0f)' % (smallest['window_bytes'], bdp),
              'TODO(A2-2): one window has to be small enough to be the bottleneck')
        for r in explicit:
            pred_expect = num(r.get('window_bytes')) * 8 / (rtt / 1000.0) / 1e6
            pred = num(r.get('predicted_mbps'))
            check(pred > 0 and abs(pred - pred_expect) / pred_expect < 0.10,
                  'prediction for -w %s follows window x 8 / RTT (%.2f vs %.2f Mbps)' % (r['window'], pred, pred_expect),
                  'TODO(A2-4)')
        ratio = num(smallest.get('receiver_mbps')) / max(num(smallest.get('predicted_mbps')), 1e-9)
        check(0.4 <= ratio <= 2.0,
              'smallest window: measured/predicted = %.2f (window really is the bottleneck)' % ratio,
              'window scaling and buffer doubling explain up to ~2x; more means the window was not the limit')
        ordered = sorted(explicit, key=lambda r: num(r.get('window_bytes')))
        mono = all(num(ordered[i + 1]['receiver_mbps']) >= 0.9 * num(ordered[i]['receiver_mbps'])
                   for i in range(len(ordered) - 1))
        check(mono, 'throughput does not decrease as the window grows (%s)' %
              ', '.join('%s:%.1f' % (r['window'], num(r['receiver_mbps'])) for r in ordered))
        if default:
            d = num(default[0].get('receiver_mbps'))
            check(d >= 0.9 * max(num(r['receiver_mbps']) for r in explicit),
                  'autotune (default) is at least as fast as the best explicit window (%.1f Mbps)' % d,
                  'if autotune loses, check the sysctl ceilings you recorded in A2-5')
    check(len(j.get('autotune_sysctl', {})) >= 1, 'autotune ceiling sysctl(s) recorded (%s)' %
          ', '.join(j.get('autotune_sysctl', {}).keys()), 'TODO(A2-5)')


def grade_a3():
    j = load('a3')
    runs = {r.get('offload'): r for r in j.get('runs', [])}
    for k in ('default', 'on', 'off'):
        if not check(k in runs, 'run "%s" present' % k):
            finish()
    for k in ('on', 'off'):
        check(runs[k].get('datapath_type') == 'system', '%s: kernel datapath (%s)' % (k, runs[k].get('datapath_type')),
              'the userspace datapath cannot do this experiment; see e4_offload.py docstring')
    d = runs['default'].get('h1_features', {})
    check(set(d) == {'tso', 'gso', 'gro'} and all(v in ('on', 'off') for v in d.values()),
          'default tso/gso/gro recorded via ethtool (%s)' % d, 'TODO(A3-1)')
    on, off = runs['on'].get('h1_features', {}), runs['off'].get('h1_features', {})
    check(all(on.get(k) == 'on' for k in ('tso', 'gso', 'gro')), 'read-back after "on": %s' % on,
          'TODO(A3-2): all three must really be on -- read back, not assumed')
    check(all(off.get(k) == 'off' for k in ('tso', 'gso', 'gro')), 'read-back after "off": %s' % off, 'TODO(A3-2)')
    g_on, g_off = num(runs['on'].get('gbps')), num(runs['off'].get('gbps'))
    c_on, c_off = num(runs['on'].get('cpu_host_pct')), num(runs['off'].get('cpu_host_pct'))
    check(g_on > 0 and g_off > 0, 'both runs moved traffic (%.2f / %.2f Gbps)' % (g_on, g_off))
    check(c_on > 0 and c_off > 0, 'sender CPU was sampled in both runs (%.0f%% / %.0f%%)' % (c_on, c_off))
    check(g_on > 2.0 * g_off, 'offload on > 2 x offload off (%.2f vs %.2f Gbps, %.1fx)' % (g_on, g_off, g_on / max(g_off, 1e-9)),
          'on a real kernel datapath with all three features toggled on both hosts AND the switch this is 4-7x')
    for k, g, c in (('on', g_on, c_on), ('off', g_off, c_off)):
        e = num(runs[k].get('gbps_per_cpu'))
        expect = g / max(c / 100.0, 1e-9)
        check(e > 0 and abs(e - expect) / expect < 0.10,
              '%s: Gbps per CPU = throughput / (sender CPU/100) (%.2f vs %.2f)' % (k, e, expect), 'TODO(A3-3)')
    check(num(runs['on'].get('gbps_per_cpu')) > num(runs['off'].get('gbps_per_cpu')),
          'efficiency: on beats off in Gbps per CPU')


def grade_e5_common(j, label):
    check(num(j.get('samples')) >= 50, '%s: >= 50 RTT samples (%s)' % (label, j.get('samples')))
    check(j.get('goodput_mbps') is not None and num(j.get('goodput_mbps')) >= 8.0,
          '%s: bulk flow fills the 10 Mbit bottleneck (goodput %s Mbps >= 8)' % (label, j.get('goodput_mbps')))
    check(j.get('idle_rtt_avg_ms') is not None, '%s: idle RTT recorded (%s ms)' % (label, j.get('idle_rtt_avg_ms')))


def grade_a4():
    j = load('e5_bloat')
    check(re.match(r'^\s*[bp]fifo\b', j.get('leaf_qdisc', '')) is not None,
          'bloat point is a plain FIFO (%s)' % j.get('leaf_qdisc'), 'TODO(A4-1): bfifo limit <bytes>')
    grade_e5_common(j, 'bloat')
    idle, p50, p99 = num(j.get('idle_rtt_avg_ms')), num(j.get('p50_ms')), num(j.get('p99_ms'))
    check(p50 >= 20.0, 'loaded P50 RTT shows a standing queue (%.1f ms >= 20)' % p50,
          'the buffer is too shallow to bloat; recompute bytes = rate x target delay')
    check(p99 > 10 * max(idle, 0.01), 'loaded P99 >> idle RTT (%.1f ms vs %.2f ms idle)' % (p99, idle))
    check('backlog' in j.get('tc_stats', ''), 'tc -s qdisc statistics captured (backlog/drops)')


def labels_from_conf():
    conf = os.path.join(ROOT, 'harness', 'qdiscs.conf')
    labels = []
    with open(conf) as f:
        for line in f:
            if line.strip().startswith('#') or len(line.split()) < 2:
                continue
            labels.append(line.split()[0])
    return labels


def grade_b1():
    labels = labels_from_conf()
    check(len(labels) >= 3, 'at least 3 settings in harness/qdiscs.conf (%s)' % ', '.join(labels), 'TODO(B1-1)')
    check('bloat' in labels, '"bloat" is one of them')
    pts = {}
    for l in labels:
        path = os.path.join(DATA, 'e5_%s.json' % l)
        if check(os.path.exists(path), 'data/e5_%s.json exists' % l, 'every label must run: make b1'):
            with open(path) as f:
                pts[l] = json.load(f)
    for l, j in pts.items():
        grade_e5_common(j, l)
    if 'bloat' in pts and len(pts) >= 2:
        b = pts['bloat']
        dom = [l for l, j in pts.items() if l != 'bloat'
               and num(j.get('goodput_mbps')) >= 0.9 * num(b.get('goodput_mbps'))
               and num(j.get('p99_ms')) <= num(b.get('p99_ms')) / 5.0]
        check(len(dom) >= 1, 'some setting dominates "bloat" (same goodput within 10 %%, P99 at least 5x lower): %s' % (dom or 'none'),
              'an AQM (fq_codel, codel) or a right-sized buffer does this; a huge FIFO is never on the frontier')
        slo = [l for l, j in pts.items() if num(j.get('goodput_mbps')) >= 9.0 and num(j.get('p99_ms')) <= 20.0]
        check(len(slo) >= 1, 'at least one setting meets the SLO (goodput >= 9 Mbps and P99 <= 20 ms): %s' % (slo or 'none'))
        distinct = len(set(round(num(j.get('p99_ms')), 1) for j in pts.values()))
        check(distinct >= 3, 'the points are really different settings (%d distinct P99 values)' % distinct,
              'three labels with the same qdisc spec are one point, not a frontier')
    csvp = os.path.join(DATA, 'pareto.csv')
    rows = 0
    if os.path.exists(csvp):
        with open(csvp) as f:
            rows = max(0, sum(1 for _ in f) - 1)
    check(rows >= 3, 'data/pareto.csv has >= 3 rows (%d)' % rows, 'make b1 regenerates it')


def grade_b2():
    j = load('b2')
    link = j.get('link', {})
    meas = link.get('measured', {})
    check(num(link.get('loss_pct')) >= 0.5, 'random loss configured (%s %%)' % link.get('loss_pct'), 'TODO(B2-1)')
    check(num(meas.get('rtt_ms')) >= 50, 'high-RTT path (%.1f ms)' % num(meas.get('rtt_ms')), 'TODO(B2-1)')
    e1 = {r['cc']: r for r in j.get('exp1_vary_cc', [])}
    for r in j.get('exp1_vary_cc', []) + j.get('exp2_vary_window', []):
        goodput = num(r.get('receiver_mbps'))
        check(math.isfinite(goodput) and goodput > 0,
              '%s/%s: a finite, positive goodput was measured (%s Mbps)' %
              (r.get('cc'), r.get('window') or 'default', r.get('receiver_mbps')),
              'a failed or empty iperf3 run cannot test either hypothesis')
    loss_based = [c for c in e1 if c in ('cubic', 'reno', 'htcp', 'highspeed', 'scalable', 'bic', 'westwood')]
    model_based = [c for c in e1 if c in ('bbr', 'bbr2', 'bbr3')]
    check(len(e1) >= 2, 'experiment 1 compares >= 2 congestion controls (%s)' % ', '.join(e1), 'TODO(B2-2)')
    check(loss_based and model_based, 'they come from different families (loss-based %s vs model-based %s)' % (loss_based, model_based),
          'TODO(B2-2): e.g. cubic vs bbr; check tcp_available_congestion_control')
    model_goodput = None
    if loss_based and model_based:
        lo = min(num(e1[c].get('receiver_mbps')) for c in loss_based)
        hi = max(num(e1[c].get('receiver_mbps')) for c in model_based)
        model_goodput = hi
        ratio1 = hi / max(lo, 1e-9)
        check(ratio1 > 2.0, 'model-based beats loss-based under loss by > 2x (%.1f vs %.1f Mbps, %.1fx)' % (hi, lo, ratio1),
              'with >= 0.5 %% loss and a long RTT this is typically 10-40x; if not, is the loss really on the path?')
    e2 = j.get('exp2_vary_window', [])
    check(len(e2) >= 2 and all(r.get('cc') == e2[0].get('cc') for r in e2), 'experiment 2 holds the congestion control fixed (%s)' %
          (e2[0].get('cc') if e2 else None), 'TODO(B2-3)')
    if e2:
        check(e2[0].get('cc') in loss_based or e2[0].get('cc') in ('cubic', 'reno'),
              'experiment 2 uses the loss-based algorithm (%s)' % e2[0].get('cc'), 'TODO(B2-3): test the window on the algorithm that was slow')
        dflt = [r for r in e2 if not r.get('window')]
        big = [r for r in e2 if r.get('window')]
        if check(dflt and big, 'experiment 2 has a default and an enlarged window'):
            wb = big[0].get('window', '')
            m = re.match(r'(\d+(?:\.\d+)?)([KMG])', wb.upper())
            wbytes = float(m.group(1)) * {'K': 1024, 'M': 1024 ** 2, 'G': 1024 ** 3}[m.group(2)] if m else 0
            bdp = 100e6 * num(meas.get('rtt_ms')) / 1000.0 / 8.0
            check(wbytes >= 0.5 * bdp, 'enlarged window is at least half the BDP (%s vs BDP %.0f bytes)' % (wb, bdp), 'TODO(B2-3)')
            ratio2 = num(big[0].get('receiver_mbps')) / max(num(dflt[0].get('receiver_mbps')), 1e-9)
            if model_goodput is not None:
                best_window = max(num(r.get('receiver_mbps')) for r in e2)
                check(model_goodput > 2.0 * best_window,
                      'model-based goodput stays > 2x every loss-based window run '
                      '(%.1f vs best %.1f Mbps; enlarged/default %.2fx)' %
                      (model_goodput, best_window, ratio2),
                      'compare achieved goodput, not the ratio of two noisy, slow loss-based runs; '
                      'if the enlarged window reaches the model-based result, the window hypothesis is not ruled out')


# Check R reads only these tables: the FIRST table under each heading whose first
# header cell matches. Other tables, bullets and prose anywhere are never parsed.
REPORT_TABLES = (
    # (section, first header cell, minimum complete rows)
    ('A1', 'metric', 3),
    ('A2', 'window', 3),
    ('A3', 'setting', 2),
    ('B1', 'label', 3),
    ('B2', 'experiment', 2),
)
AI_USAGE_EXAMPLE = '| 1 | no AI used | none | - | - |'


def md_cells(line):
    """Cells of one markdown table row; HTML comments are ignored."""
    line = re.sub(r'<!--.*?-->', '', line).strip()
    if not line.startswith('|'):
        return None
    return [c.strip() for c in line.strip('|').split('|')]


def is_separator(cells):
    return bool(cells) and all(re.fullmatch(r':?-+:?', c) for c in cells)


def md_tables(text):
    """Yield (header cells, data rows) for every markdown table in text."""
    lines = text.splitlines()
    i = 0
    while i < len(lines):
        head = md_cells(lines[i])
        sep = md_cells(lines[i + 1]) if i + 1 < len(lines) else None
        if head and sep and is_separator(sep):
            rows = []
            i += 2
            while i < len(lines):
                row = md_cells(lines[i])
                if row is None:
                    break
                rows.append(row)
                i += 1
            yield head, rows
            continue
        i += 1


def section(text, heading):
    m = re.search(r'^## %s\b.*$' % re.escape(heading), text, re.M)
    if not m:
        return None
    rest = text[m.end():]
    nxt = re.search(r'^## ', rest, re.M)
    return rest[:nxt.start()] if nxt else rest


def grade_report_table(text, heading, first_header, minimum):
    body = section(text, heading)
    if body is None:
        return  # the missing heading is already reported
    table = next(((h, r) for h, r in md_tables(body) if h[0].lower() == first_header), None)
    where = 'the "%s | ..." table under "## %s"' % (first_header, heading)
    if not check(table is not None, 'report: %s is present' % where,
                 'keep the template table (its first header cell is "%s"); only that table is graded'
                 % first_header):
        return
    header, rows = table
    rows = [r for r in rows if any(r)]                       # completely empty rows are ignored
    bad = [i for i, r in enumerate(rows, 1) if len(r) != len(header) or not all(r)]
    if bad:
        hint = ('row(s) %s of that table have an empty cell or a different number of columns; '
                'every row you keep needs text in all %d columns (write n/a if a value does not '
                'apply) -- or delete the row' % (', '.join(map(str, bad)), len(header)))
    else:
        hint = 'that table needs at least %d rows with text in all %d columns' % (minimum, len(header))
    check(len(rows) >= minimum and not bad,
          'report: %s is filled in (%d complete row(s), at least %d needed)'
          % (where, len(rows) - len(bad), minimum),
          hint + '. Only this table is graded here; your other tables and text are not parsed')


def grade_report():
    rep = os.path.join(ROOT, 'report', 'REPORT.md')
    if not check(os.path.exists(rep), 'report/REPORT.md exists'):
        finish()
    txt = open(rep, encoding='utf-8', errors='replace').read()
    for h in ('A1', 'A2', 'A3', 'A4', 'B1', 'B2'):
        check(re.search(r'^## %s\b' % h, txt, re.M) is not None, 'section "## %s" present' % h, 'keep the template headings')
    check('<student id>' not in txt, 'title line filled in (no "<student id>" placeholder)')
    for heading, first_header, minimum in REPORT_TABLES:
        grade_report_table(txt, heading, first_header, minimum)
    for fig in ('figs/a4_cdf.png', 'figs/b1_pareto.png'):
        p = os.path.join(ROOT, fig)
        check(os.path.exists(p) and os.path.getsize(p) > 1000, '%s exists' % fig, 'make plot')
        check(os.path.basename(fig) in txt, '%s is referenced in the report' % fig)
    ai = os.path.join(ROOT, 'report', 'ai-usage.md')
    if check(os.path.exists(ai), 'report/ai-usage.md exists'):
        ai_text = open(ai, encoding='utf-8', errors='replace').read()
        log = next((r for h, r in md_tables(ai_text) if h[0] == '#'), None)
        rows = [r for r in (log or []) if r and re.fullmatch(r'\d+', r[0]) and len(r) >= 5 and all(r[:5])]
        check(len(rows) >= 1, 'AI usage log has at least one complete row (%d)' % len(rows),
              'fill all five columns of at least one numbered row in the "| # | what I asked | ..." table; '
              'if you used no AI at all, write: ' + AI_USAGE_EXAMPLE)


GRADERS = {'a1': grade_a1, 'a2': grade_a2, 'a3': grade_a3, 'a4': grade_a4,
           'b1': grade_b1, 'b2': grade_b2, 'report': grade_report}

if __name__ == '__main__':
    if len(sys.argv) != 2 or sys.argv[1] not in GRADERS:
        sys.exit('usage: %s <%s>' % (sys.argv[0], '|'.join(GRADERS)))
    GRADERS[sys.argv[1]]()
    finish()
