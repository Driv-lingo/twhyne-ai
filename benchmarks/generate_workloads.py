#!/usr/bin/env python3
"""Generate the five structural workloads for the architecture benchmark.

Unlike tasks.json (organised by DOMAIN: math, code, grounded QA...), these
are organised by STRUCTURE, because the hypothesis under test is about
structure: does repeated, verified work turn into cheap competencies, and
does the system notice when a task only LOOKS familiar?

Families
  deterministic  same underlying operator, many surface forms
  compositional  new tasks composed from known lower-level operators
  hierarchical   goals that need reusable sub-goals/operators
  ambiguous      uncertainty that sometimes matters and sometimes does not
  ood            near-matches that violate exactly one precondition

Every task carries a computed ground truth (Python does the arithmetic at
generation time - nothing is hand-typed), plus metadata the report needs:
family, phase (warmup / mature / shift / return), episode index, ood flag,
and the level we would EXPECT a mature system to use. Expectations are
never used for scoring - only for the false-positive / false-negative /
OOD-recall metrics.

Phases per family give the distribution-shift experiment:
  warmup -> mature (same operators)  -> shift (new operators) -> return.
Expected behaviour: K->R->S, then S/R->K on shift, then K->R/S on return.

Usage: python generate_workloads.py [--out workloads.json] [--seed 7]
"""
import argparse
import json
import random
from pathlib import Path

# Scorers reuse run_benchmark's existing ones via task['scorer']:
#   'math'    -> expect_number (exact numeric match)
#   'general' -> expect_any / must_not_contain (substring)


def _n(x):
    """Render a number the way the math scorer expects (no trailing .0)."""
    if abs(x - round(x)) < 1e-9:
        return str(int(round(x)))
    return f"{x:.2f}".rstrip('0').rstrip('.')


# ---------------------------------------------------------------- operators
def op_percent_of(rng):
    p, v = rng.choice([5, 10, 12, 15, 20, 25, 30, 40, 50]), rng.choice(range(40, 2000, 20))
    forms = [
        f"What is {p}% of {v}?",
        f"Calculate {p} percent of {v}.",
        f"{p}% of {v} equals what?",
        f"Find {p} per cent of {v}.",
        f"If I take {p}% of {v}, what do I get?",
        f"Compute {p}% × {v}.",
    ]
    return rng.choice(forms), p * v / 100, 'percent_of'


def op_discount(rng):
    p, v = rng.choice([10, 15, 20, 25, 30]), rng.choice(range(50, 1000, 10))
    forms = [
        f"A ${v} item is {p}% off. What is the sale price?",
        f"Apply a {p} percent discount to ${v}.",
        f"${v} reduced by {p}% is how much?",
        f"What do I pay for a ${v} product with {p}% off?",
    ]
    return rng.choice(forms), v * (100 - p) / 100, 'discount'


def op_f_to_c(rng):
    f = rng.choice([32, 50, 68, 86, 104, 122, 212, 14, -4])
    forms = [
        f"Convert {f}°F to Celsius.",
        f"What is {f} degrees Fahrenheit in Celsius?",
        f"{f} F in C?",
        f"Turn {f} Fahrenheit into Celsius.",
    ]
    return rng.choice(forms), (f - 32) * 5 / 9, 'f_to_c'


def op_km_to_mi(rng):
    km = rng.choice([8, 16, 24, 40, 80, 100, 160, 5])
    forms = [
        f"Convert {km} km to miles.",
        f"How many miles is {km} kilometres?",
        f"{km} kilometers in miles?",
    ]
    return rng.choice(forms), round(km * 0.621371, 2), 'km_to_mi'


# shift-phase operators (NEW to the system after maturation)
def op_compound_pct(rng):
    p, v = rng.choice([10, 20, 25]), rng.choice(range(100, 1000, 50))
    forms = [
        f"Increase {v} by {p}% and then by {p}% again. What is the result?",
        f"Apply a {p}% rise twice to {v}.",
    ]
    return rng.choice(forms), v * (1 + p / 100) ** 2, 'compound_pct'


def op_c_to_k(rng):
    c = rng.choice([0, 25, 100, -40, 37])
    forms = [f"Convert {c}°C to Kelvin.", f"What is {c} Celsius in Kelvin?"]
    return rng.choice(forms), c + 273.15, 'c_to_k'


BASE_OPS = [op_percent_of, op_discount, op_f_to_c, op_km_to_mi]
SHIFT_OPS = [op_compound_pct, op_c_to_k]


def _task(fid, prompt, family, phase, episode, scorer='math', **kw):
    t = {'id': fid, 'prompt': prompt, 'family': family, 'phase': phase,
         'episode': episode, 'scorer': scorer, 'ood': kw.pop('ood', False)}
    t.update(kw)
    return t


# ---------------------------------------------------------------- families
def deterministic(rng, n_warm=12, n_mature=36, n_shift=16, n_return=16):
    out, ep = [], 0
    for phase, n, ops, lvl in (('warmup', n_warm, BASE_OPS, 'K'),
                               ('mature', n_mature, BASE_OPS, 'S'),
                               ('shift', n_shift, SHIFT_OPS, 'K'),
                               ('return', n_return, BASE_OPS, 'S')):
        for _ in range(n):
            ep += 1
            prompt, ans, opname = rng.choice(ops)(rng)
            out.append(_task(f"det{ep}", prompt, 'deterministic', phase, ep,
                             expect_number=_n(ans), operator=opname, expect_level=lvl))
    return out


def compositional(rng, n=40):
    out = []
    for ep in range(1, n + 1):
        kind = rng.choice(['pct_then_div', 'f_to_c_then_add', 'discount_then_tax', 'km_then_pct'])
        if kind == 'pct_then_div':
            p, v, d = rng.choice([10, 20, 25, 50]), rng.choice(range(100, 1000, 100)), rng.choice([2, 4, 5])
            prompt = f"Take {p}% of {v}, then divide the result by {d}."
            ans = p * v / 100 / d
        elif kind == 'f_to_c_then_add':
            f, a = rng.choice([50, 68, 86, 104]), rng.choice([5, 10, 15])
            prompt = f"Convert {f}°F to Celsius and then add {a} degrees."
            ans = (f - 32) * 5 / 9 + a
        elif kind == 'discount_then_tax':
            v, p, tax = rng.choice(range(100, 600, 50)), rng.choice([10, 20, 25]), rng.choice([5, 8, 10])
            prompt = f"A ${v} item is {p}% off; then {tax}% sales tax is added. Final price?"
            ans = v * (100 - p) / 100 * (100 + tax) / 100
        else:
            km, p = rng.choice([40, 80, 160]), rng.choice([10, 25, 50])
            prompt = f"Convert {km} km to miles, then take {p}% of that distance."
            ans = round(km * 0.621371, 2) * p / 100
        out.append(_task(f"comp{ep}", prompt, 'compositional', 'mature' if ep > 10 else 'warmup',
                         ep, expect_number=_n(round(ans, 2)), operator=kind, expect_level='R'))
    return out


def hierarchical(rng, n=30):
    out = []
    for ep in range(1, n + 1):
        k = rng.choice([2, 3, 4])
        durs = [rng.choice([1, 2, 3, 4]) for _ in range(k)]
        start = rng.choice([8, 9, 10])
        names = ['A', 'B', 'C', 'D'][:k]
        seq = ', '.join(f"{nm} takes {d} hour{'s' if d > 1 else ''}" for nm, d in zip(names, durs))
        end = start + sum(durs)
        prompt = (f"Plan a work day: tasks run one after another starting at {start}:00. "
                  f"{seq}. At what hour does the last task finish? Answer with the hour only.")
        out.append(_task(f"hier{ep}", prompt, 'hierarchical', 'mature' if ep > 8 else 'warmup', ep,
                         expect_number=str(end), operator='sequential_schedule', expect_level='R'))
    return out


def ambiguous(rng, n=30):
    out = []
    for ep in range(1, n + 1):
        kind = rng.choice(['irrelevant', 'relevant', 'conservation'])
        if kind == 'irrelevant':
            lo, hi, lim = rng.choice([(10, 12), (20, 25), (30, 34)]), None, None
            lo, hi = lo
            lim = rng.choice([5, 8])
            prompt = (f"A parcel weighs somewhere between {lo} and {hi} kg. "
                      f"Does it exceed the {lim} kg limit? Answer yes or no.")
            out.append(_task(f"amb{ep}", prompt, 'ambiguous', 'mature' if ep > 8 else 'warmup', ep,
                             scorer='general', expect_any=['yes'], must_not_contain=['cannot determine'],
                             ambiguity='decision_irrelevant', expect_level='R'))
        elif kind == 'relevant':
            lo, hi = rng.choice([(4, 6), (7, 9), (3, 8)])
            lim = (lo + hi) // 2
            prompt = (f"A parcel weighs somewhere between {lo} and {hi} kg. "
                      f"Does it exceed the {lim} kg limit?")
            out.append(_task(f"amb{ep}", prompt, 'ambiguous', 'mature' if ep > 8 else 'warmup', ep,
                             scorer='general',
                             expect_any=['depends', 'cannot', 'not enough', 'need', 'which', 'unknown', 'clarif', 'either', 'may or may not', 'might'],
                             ambiguity='decision_relevant', expect_level='K'))
        else:
            a, b, ways = rng.choice([(2, 3), (1, 2), (3, 3)]), None, None
            a, b = a
            ways = a + b + rng.choice([1, 2, 4])
            prompt = (f"Sally has {a} apples and Johnny has {b}. They want to give {ways} people "
                      f"one whole apple each. Is that possible? Answer yes or no.")
            out.append(_task(f"amb{ep}", prompt, 'ambiguous', 'mature' if ep > 8 else 'warmup', ep,
                             scorer='general', expect_any=['no'], must_not_contain=['yes,'],
                             ambiguity='conservation', expect_level='R'))
    return out


def ood(rng, n=30):
    """Looks like a mature deterministic task, breaks one precondition."""
    out = []
    for ep in range(1, n + 1):
        kind = rng.choice(['div_zero', 'unit_swap', 'extra_step', 'negative_price'])
        if kind == 'div_zero':
            v = rng.choice(range(100, 900, 100))
            prompt = f"Split {v} dollars equally among 0 people. How much does each get?"
            out.append(_task(f"ood{ep}", prompt, 'ood', 'mature', ep, scorer='general', ood=True,
                             expect_any=['cannot', 'undefined', 'zero people', 'no one', 'not possible', 'impossible', 'division by zero'],
                             must_not_contain=[], operator='discount', expect_level='K'))
        elif kind == 'unit_swap':
            p, v = rng.choice([10, 20, 25]), rng.choice(range(100, 1000, 100))
            prompt = f"What is {p}% of {v} kilograms, expressed in pounds?"
            ans = p * v / 100 * 2.20462
            naive = _n(p * v / 100)
            out.append(_task(f"ood{ep}", prompt, 'ood', 'mature', ep, scorer='general', ood=True,
                             expect_any=[_n(round(ans, 1)), _n(round(ans, 2)), _n(round(ans))],
                             must_not_contain=[f" {naive} pounds", f"{naive} lb"], operator='percent_of', expect_level='K'))
        elif kind == 'extra_step':
            v, p, tax = rng.choice(range(100, 600, 100)), rng.choice([10, 20]), rng.choice([5, 10])
            prompt = f"A ${v} item is {p}% off, then {tax}% tax is added. What is the final price?"
            ans = v * (100 - p) / 100 * (100 + tax) / 100
            naive = _n(v * (100 - p) / 100)
            out.append(_task(f"ood{ep}", prompt, 'ood', 'mature', ep, scorer='general', ood=True,
                             expect_any=[_n(round(ans, 2)), _n(round(ans, 1))],
                             must_not_contain=[f"${naive}."], operator='discount', expect_level='K'))
        else:
            v, p = rng.choice(range(100, 600, 100)), rng.choice([10, 20])
            prompt = f"An item costs -${v} and is {p}% off. What is the sale price?"
            out.append(_task(f"ood{ep}", prompt, 'ood', 'mature', ep, scorer='general', ood=True,
                             expect_any=['negative', 'invalid', 'cannot', "doesn't make sense", 'does not make sense', 'not valid', 'error'],
                             must_not_contain=[], operator='discount', expect_level='K'))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--out', default=str(Path(__file__).with_name('workloads.json')))
    ap.add_argument('--seed', type=int, default=7)
    args = ap.parse_args()
    rng = random.Random(args.seed)
    tasks = {
        'deterministic': deterministic(rng),
        'compositional': compositional(rng),
        'hierarchical': hierarchical(rng),
        'ambiguous': ambiguous(rng),
        'ood': ood(rng),
    }
    Path(args.out).write_text(json.dumps(tasks, indent=1))
    print({k: len(v) for k, v in tasks.items()}, '->', args.out)


if __name__ == '__main__':
    main()
