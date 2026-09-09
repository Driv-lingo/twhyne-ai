#!/usr/bin/env python3
"""Compare benchmark runs across conditions A/B/C/D and compute the
architecture metrics the contract asks for - from measured traces only.

    python report.py --run A=results-plain.json --run B=results-current.json \
                     --run C=results-structured.json --run D=results-full.json

Every number here comes from the result files produced by run_benchmark.py
(which records the per-task trace returned by the server). If a run lacks a
measurement it prints n/a; nothing is estimated or back-filled.

Definitions
  success            local_pass (correct AND within the latency limit)
  neural task        trace.neural_calls > 0  or  trace.level == 'K'
  NDR                successful tasks that needed general neural reasoning /
                     successful tasks                       (should FALL with experience)
  cost               cpu_s when measured, else total_s
  CCR                mean cost of K-level tasks / mean cost of all tasks (per family)
  router overhead    mean trace.segments.router_s
  verify overhead    mean trace.segments.verification_s
  FP activation      ood task executed at R/S level (a competency fired where it must not)
  FN escalation      mature-phase task expected at S that ran at K (safe but wasteful)
  OOD recall         ood tasks that ran at K or refused / ood tasks
  break-even n*      first episode at which cumulative cost of D < cumulative cost of C
"""
import argparse
import json
from collections import defaultdict


def load(path):
    with open(path) as f:
        d = json.load(f)
    return d if isinstance(d, list) else d.get('results', [])


def tr(r, *keys, default=None):
    cur = r.get('trace') or {}
    for k in keys:
        if not isinstance(cur, dict):
            return default
        cur = cur.get(k)
    return default if cur is None else cur


def cost(r):
    c = tr(r, 'cpu_s')
    if c is None:
        c = tr(r, 'total_s')
    if c is None:
        c = r.get('elapsed_s')
    return float(c or 0.0)


def mean(xs):
    xs = [x for x in xs if x is not None]
    return (sum(xs) / len(xs)) if xs else None


def fmt(x, nd=3):
    if x is None:
        return 'n/a'
    if isinstance(x, float):
        return f"{x:.{nd}f}"
    return str(x)


def summarize(rows):
    n = len(rows)
    ok = [r for r in rows if r.get('local_pass')]
    neural_ok = [r for r in ok if (tr(r, 'neural_calls', default=0) or 0) > 0 or tr(r, 'level') == 'K']
    levels = defaultdict(int)
    for r in rows:
        levels[tr(r, 'level') or 'legacy'] += 1
    has_trace = any(r.get('trace') for r in rows)
    s = {
        'tasks': n,
        'accuracy': (len([r for r in rows if r.get('correct')]) / n) if n else None,
        'success': (len(ok) / n) if n else None,
        'latency_mean_s': mean([r.get('elapsed_s') for r in rows]),
        'ttft_s': mean([tr(r, 'ttft_s') for r in rows]) if has_trace else None,
        'tokens_out_mean': mean([tr(r, 'tokens_out') for r in rows]) if has_trace else None,
        'model_calls_mean': mean([tr(r, 'neural_calls') for r in rows]) if has_trace else None,
        'cpu_s_mean': mean([tr(r, 'cpu_s') for r in rows]) if has_trace else None,
        'rss_mb_mean': mean([tr(r, 'rss_mb') for r in rows]) if has_trace else None,
        'router_s_mean': mean([tr(r, 'segments', 'router_s') for r in rows]) if has_trace else None,
        'verify_s_mean': mean([tr(r, 'segments', 'verification_s') for r in rows]) if has_trace else None,
        'NDR': (len(neural_ok) / len(ok)) if ok else None,
        'levels': dict(levels),
        'cost_per_success': (sum(cost(r) for r in rows) / len(ok)) if ok else None,
        'cumulative_cost': sum(cost(r) for r in rows),
    }
    # competency metrics need task metadata (workloads.json runs)
    ood = [r for r in rows if r.get('ood')]
    if ood:
        fp = [r for r in ood if tr(r, 'level') in ('R', 'S')]
        recalled = [r for r in ood if tr(r, 'level') == 'K' or tr(r, 'result', 'refused') or tr(r, 'result', 'withheld')]
        s['ood_tasks'] = len(ood)
        s['fp_activation_rate'] = len(fp) / len(ood)
        s['ood_recall'] = len(recalled) / len(ood)
    mature_s = [r for r in rows if r.get('phase') == 'mature' and r.get('expect_level') == 'S']
    if mature_s:
        s['fn_escalation_rate'] = len([r for r in mature_s if tr(r, 'level') == 'K']) / len(mature_s)
    ev = [e for r in rows for e in (tr(r, 'events', default=[]) or [])]
    if has_trace:
        s['promotions'] = len([e for e in ev if str(e.get('type', '')).startswith('promot')])
        s['rollbacks'] = len([e for e in ev if 'rollback' in str(e.get('type', '')) or 'demot' in str(e.get('type', ''))])
        s['competency_reuse'] = len([r for r in rows if tr(r, 'level') in ('R', 'S')])
    return s


def ndr_curve(rows, window=10):
    """NDR over episode windows, per family - the 'does reasoning decrease' plot."""
    fams = defaultdict(list)
    for r in rows:
        if r.get('family') is not None and r.get('episode') is not None:
            fams[r['family']].append(r)
    out = {}
    for fam, rs in fams.items():
        rs.sort(key=lambda r: r['episode'])
        pts = []
        for i in range(0, len(rs), window):
            chunk = rs[i:i + window]
            ok = [r for r in chunk if r.get('local_pass')]
            neural = [r for r in ok if (tr(r, 'neural_calls', default=0) or 0) > 0 or tr(r, 'level') == 'K']
            pts.append({'episodes': f"{chunk[0]['episode']}-{chunk[-1]['episode']}",
                        'phase': chunk[0].get('phase'),
                        'NDR': (len(neural) / len(ok)) if ok else None,
                        'accuracy': len([r for r in chunk if r.get('correct')]) / len(chunk),
                        'mean_cost': mean([cost(r) for r in chunk])})
        out[fam] = pts
    return out


def ccr(rows):
    fams = defaultdict(list)
    for r in rows:
        fams[r.get('family') or r.get('category')].append(r)
    out = {}
    for fam, rs in fams.items():
        k = [cost(r) for r in rs if tr(r, 'level') == 'K']
        allc = [cost(r) for r in rs]
        out[fam] = (mean(k) / mean(allc)) if k and allc and mean(allc) else None
    return out


def break_even(rows_c, rows_d):
    """First episode where cumulative cost(D) < cumulative cost(C), per family."""
    def cum(rows):
        fams = defaultdict(list)
        for r in rows:
            if r.get('family') is not None:
                fams[r['family']].append(r)
        curves = {}
        for fam, rs in fams.items():
            rs.sort(key=lambda r: r['episode'])
            tot, pts = 0.0, {}
            for r in rs:
                tot += cost(r); pts[r['episode']] = tot
            curves[fam] = pts
        return curves
    cc, cd = cum(rows_c), cum(rows_d)
    out = {}
    for fam in cc:
        if fam not in cd:
            out[fam] = 'n/a'; continue
        n_star = next((ep for ep in sorted(cd[fam]) if ep in cc[fam] and cd[fam][ep] < cc[fam][ep]), None)
        out[fam] = n_star if n_star is not None else 'never (within run)'
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--run', action='append', required=True,
                    help='LABEL=path.json (repeatable), e.g. A=results-plain.json')
    ap.add_argument('--window', type=int, default=10)
    args = ap.parse_args()
    runs = {}
    for spec in args.run:
        label, path = spec.split('=', 1)
        runs[label] = load(path)

    keys = ['tasks', 'accuracy', 'success', 'latency_mean_s', 'ttft_s', 'tokens_out_mean',
            'model_calls_mean', 'cpu_s_mean', 'rss_mb_mean', 'router_s_mean', 'verify_s_mean',
            'NDR', 'cost_per_success', 'cumulative_cost', 'ood_tasks', 'fp_activation_rate',
            'ood_recall', 'fn_escalation_rate', 'promotions', 'rollbacks', 'competency_reuse', 'levels']
    sums = {k: summarize(v) for k, v in runs.items()}
    labels = list(runs)
    print('| metric | ' + ' | '.join(labels) + ' |')
    print('|---|' + '---|' * len(labels))
    for k in keys:
        print(f"| {k} | " + ' | '.join(fmt(sums[l].get(k)) for l in labels) + ' |')

    for l in labels:
        curve = ndr_curve(runs[l], args.window)
        if curve:
            print(f"\n### NDR(n) — condition {l}")
            for fam, pts in curve.items():
                print(f"- {fam}: " + ', '.join(
                    f"[{p['episodes']} {p['phase']}] NDR={fmt(p['NDR'],2)} acc={fmt(p['accuracy'],2)} cost={fmt(p['mean_cost'],2)}"
                    for p in pts))
            print(f"CCR (K cost / all cost) per family: " +
                  ', '.join(f"{f}={fmt(v,2)}" for f, v in ccr(runs[l]).items()))

    if 'C' in runs and 'D' in runs:
        print("\n### Break-even n* (cumulative cost D < C), per family")
        for fam, n in break_even(runs['C'], runs['D']).items():
            print(f"- {fam}: {n}")
        sc, sd = sums['C'], sums['D']
        print("\n### C vs D (does competency maturation itself pay?)")
        for k in ('success', 'NDR', 'cost_per_success', 'model_calls_mean', 'tokens_out_mean',
                  'fp_activation_rate', 'ood_recall', 'fn_escalation_rate'):
            print(f"- {k}: C={fmt(sc.get(k))}  D={fmt(sd.get(k))}")
        print("\nRead this honestly: if D does not beat C on cost_per_success / NDR while "
              "holding success and OOD recall, the K<->R<->S layer is not paying for itself "
              "on this workload - and that is the finding.")


if __name__ == '__main__':
    main()
