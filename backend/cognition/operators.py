"""Operator templates: the deterministic building blocks competencies are
made of, and the machinery that recognises when a K-level answer was
"really" an instance of one.

IMPORTANT for the experiment's honesty: these templates are NOT
pre-installed competencies. They are available to every condition as
(a) verifiers - "does a known formula reproduce the model's answer?" -
and (b) executors that a competency MAY bind to once it has been INDUCED
from verified K-level solves and promoted on evidence. Condition C uses
them only for verification; condition D may additionally learn to execute
them. That is exactly the difference the C-vs-D comparison isolates.

Each template has four DISTINCT mechanisms:
  parser          regex extraction of typed parameters (structural match)
  executor        the formula
  semantic guard  meaning cues that must be present / must be absent -
                  a different signal from the parser on purpose, so the
                  two guards can disagree
  verifier        post-condition on the result
"""
from __future__ import annotations

import math
import re
from typing import Any, Dict, List, Optional, Tuple

from .competency import (register_executor, register_parser, register_semantic_guard,
                         register_verifier, task_features, Envelope)

_NUM = r'-?\$?\s?(\d[\d,]*(?:\.\d+)?)'


def _f(s: str) -> float:
    return float(str(s).replace(',', '').replace('$', '').strip())


def extract_number(text: str) -> Optional[float]:
    """The number an answer commits to: prefer '= N' / 'is N' / final line,
    else the last number in the text. None if there is no number."""
    if not text:
        return None
    t = text.replace(',', '')
    m = re.findall(r'(?:=|is|equals|:)\s*\$?\s*(-?\d+(?:\.\d+)?)', t)
    if m:
        return float(m[-1])
    nums = re.findall(r'-?\d+(?:\.\d+)?', t)
    return float(nums[-1]) if nums else None


def _has(p: str, *pats: str) -> bool:
    return any(re.search(x, p) for x in pats)


TEMPLATES: Dict[str, Dict[str, Any]] = {}


def template(signature: str, domain_path: List[str], envelope: Envelope,
             perturbations: List[Tuple[str, str]], tol: float = 0.011):
    """Register a template. perturbations: [(feature, suffix)] used to
    generate near-match counterexamples the guards must REJECT."""
    def deco(cls):
        name = cls.__name__
        register_parser(name)(cls.parse)
        register_executor(name)(cls.execute)
        register_semantic_guard(name)(cls.semantic)
        register_verifier(name)(cls.verify)
        TEMPLATES[signature] = {'name': name, 'signature': signature,
                                'domain_path': domain_path, 'envelope': envelope,
                                'perturbations': perturbations, 'tol': tol, 'cls': cls}
        return cls
    return deco


# ------------------------------------------------------------ templates ----
@template('percent_of(p,v)', ['finance', 'proportion', 'percent', 'percent_of'],
          Envelope(required_params=['p', 'v'], param_types={'p': 'float', 'v': 'float'},
                   param_ranges={'p': [0, 100], 'v': [0, None]},
                   forbidden_features=['unit_conversion', 'extra_step', 'tax', 'negative_amount']),
          [('extra_step', ', then add 10% tax'), ('unit_conversion', ', expressed in pounds'),
           ('tax', ' plus 8% tax')])
class PercentOf:
    @staticmethod
    def parse(p: str):
        p = p.lower()
        m = (re.search(r'(\d[\d,]*(?:\.\d+)?)\s*(?:%|percent|per cent)\s*(?:of|×|x|\*)\s*\$?\s*(\d[\d,]*(?:\.\d+)?)', p)
             or re.search(r'take\s+(\d[\d,]*(?:\.\d+)?)\s*(?:%|percent)\s+of\s+\$?\s*(\d[\d,]*(?:\.\d+)?)', p))
        return {'p': _f(m.group(1)), 'v': _f(m.group(2))} if m else None

    @staticmethod
    def execute(p: float, v: float) -> float:
        return p * v / 100.0

    @staticmethod
    def semantic(prompt: str, params: Dict[str, Any]):
        p = prompt.lower()
        if not _has(p, r'%|percent|per cent'):
            return False, 'no percentage cue'
        if _has(p, r'\boff\b|discount|sale price|reduced'):
            return False, 'discount semantics, not percent-of'
        if _has(p, r'\bthen\b|tax|pounds|kg|kilogram|lb'):
            return False, 'additional step or unit change requested'
        return True, 'percent-of meaning confirmed'

    @staticmethod
    def verify(params, result):
        return (math.isfinite(result) and 0 <= result <= params['v']), 'result within [0, v]'


@template('discount(p,v)', ['finance', 'pricing', 'percent', 'discount'],
          Envelope(required_params=['p', 'v'], param_types={'p': 'float', 'v': 'float'},
                   param_ranges={'p': [0, 100], 'v': [0, None]},
                   forbidden_features=['unit_conversion', 'extra_step', 'tax', 'negative_amount', 'division_by_zero']),
          [('tax', ', then 10% tax is added'), ('extra_step', ' and then take half of that'),
           ('negative_amount', ' (the price is actually -$50)')])
class Discount:
    @staticmethod
    def parse(p: str):
        p = p.lower()
        pct = re.search(r'(\d[\d,]*(?:\.\d+)?)\s*(?:%|percent|per cent)', p)
        amt = re.search(r'\$\s?(\d[\d,]*(?:\.\d+)?)', p) or re.search(r'(\d[\d,]*(?:\.\d+)?)\s*(?:dollars?|usd)', p)
        if not (pct and amt):
            return None
        if not _has(p, r'\boff\b|discount|reduced|sale'):
            return None
        return {'p': _f(pct.group(1)), 'v': _f(amt.group(1))}

    @staticmethod
    def execute(p: float, v: float) -> float:
        return v * (100.0 - p) / 100.0

    @staticmethod
    def semantic(prompt: str, params: Dict[str, Any]):
        p = prompt.lower()
        if not _has(p, r'\boff\b|discount|reduced|sale'):
            return False, 'no discount cue'
        if _has(p, r'\btax\b|\bthen\b|negative|-\$'):
            return False, 'extra step / tax / negative amount'
        return True, 'discount meaning confirmed'

    @staticmethod
    def verify(params, result):
        return (math.isfinite(result) and 0 <= result <= params['v']), 'sale price within [0, v]'


@template('f_to_c(f)', ['units', 'temperature', 'convert', 'f_to_c'],
          Envelope(required_params=['f'], param_types={'f': 'float'}, param_ranges={'f': [-500, 5000]},
                   forbidden_features=['extra_step']),
          [('extra_step', ' and then add 10 degrees')])
class FtoC:
    @staticmethod
    def parse(p: str):
        p = p.lower()
        m = re.search(r'(-?\d+(?:\.\d+)?)\s*(?:°\s*f\b|degrees?\s+fahrenheit|fahrenheit|\bf\b)', p)
        if not m or not _has(p, r'celsius|\bc\b|centigrade'):
            return None
        return {'f': _f(m.group(1))}

    @staticmethod
    def execute(f: float) -> float:
        return (f - 32.0) * 5.0 / 9.0

    @staticmethod
    def semantic(prompt: str, params):
        p = prompt.lower()
        if not (_has(p, r'fahrenheit|°\s*f\b|\bf\b') and _has(p, r'celsius|centigrade|\bc\b')):
            return False, 'not an F->C conversion'
        if _has(p, r'\bthen\b|\badd\b|kelvin'):
            return False, 'additional step or different target unit'
        return True, 'F->C meaning confirmed'

    @staticmethod
    def verify(params, result):
        return math.isfinite(result), 'finite'


@template('km_to_mi(km)', ['units', 'distance', 'convert', 'km_to_mi'],
          Envelope(required_params=['km'], param_types={'km': 'float'}, param_ranges={'km': [0, None]},
                   forbidden_features=['extra_step']),
          [('extra_step', ', then take 25% of that distance')], tol=0.05)
class KmToMi:
    @staticmethod
    def parse(p: str):
        p = p.lower()
        m = re.search(r'(\d[\d,]*(?:\.\d+)?)\s*(?:km|kilomet(?:er|re)s?)\b', p)
        if not m or not _has(p, r'\bmiles?\b|\bmi\b'):
            return None
        return {'km': _f(m.group(1))}

    @staticmethod
    def execute(km: float) -> float:
        return round(km * 0.621371, 2)

    @staticmethod
    def semantic(prompt: str, params):
        p = prompt.lower()
        if not (_has(p, r'\bkm\b|kilomet') and _has(p, r'\bmiles?\b')):
            return False, 'not km->miles'
        if _has(p, r'\bthen\b|percent|%'):
            return False, 'additional step requested'
        return True, 'km->miles meaning confirmed'

    @staticmethod
    def verify(params, result):
        return result >= 0, 'non-negative'


@template('compound_pct(p,v)', ['finance', 'growth', 'percent', 'compound'],
          Envelope(required_params=['p', 'v'], param_types={'p': 'float', 'v': 'float'},
                   param_ranges={'p': [0, 100], 'v': [0, None]}, forbidden_features=['unit_conversion', 'tax']),
          [('tax', ' plus tax')])
class CompoundPct:
    @staticmethod
    def parse(p: str):
        p = p.lower()
        if not _has(p, r'twice|again|and then by'):
            return None
        pct = re.search(r'(\d[\d,]*(?:\.\d+)?)\s*(?:%|percent)', p)
        base = re.search(r'(?:increase|apply|rise)[^\d]*?(\d[\d,]*(?:\.\d+)?)(?!\s*%)', p) or \
            re.search(r'to\s+(\d[\d,]*(?:\.\d+)?)\.?', p)
        if not (pct and base):
            return None
        return {'p': _f(pct.group(1)), 'v': _f(base.group(1))}

    @staticmethod
    def execute(p: float, v: float) -> float:
        return v * (1 + p / 100.0) ** 2

    @staticmethod
    def semantic(prompt: str, params):
        p = prompt.lower()
        if not _has(p, r'twice|again'):
            return False, 'no repeated-application cue'
        return True, 'compound meaning confirmed'

    @staticmethod
    def verify(params, result):
        return result >= params['v'], 'grows'


@template('c_to_k(c)', ['units', 'temperature', 'convert', 'c_to_k'],
          Envelope(required_params=['c'], param_types={'c': 'float'}, param_ranges={'c': [-273.15, None]}),
          [('extra_step', ' and then double it')])
class CtoK:
    @staticmethod
    def parse(p: str):
        p = p.lower()
        m = re.search(r'(-?\d+(?:\.\d+)?)\s*(?:°\s*c\b|degrees?\s+celsius|celsius)', p)
        if not m or not _has(p, r'kelvin|\bk\b'):
            return None
        return {'c': _f(m.group(1))}

    @staticmethod
    def execute(c: float) -> float:
        return c + 273.15

    @staticmethod
    def semantic(prompt: str, params):
        p = prompt.lower()
        return (_has(p, r'kelvin') and _has(p, r'celsius|°\s*c'), 'C->K cues')

    @staticmethod
    def verify(params, result):
        return result >= 0, 'absolute temperature non-negative'


@template('sequential_schedule(start,durations)', ['planning', 'scheduling', 'sequence', 'finish_time'],
          Envelope(required_params=['start', 'durations'], param_types={'start': 'float'},
                   forbidden_features=['unit_conversion']),
          [('extra_step', ' Then add a 2 hour break before the last task.')])
class SequentialSchedule:
    @staticmethod
    def parse(p: str):
        pl = p.lower()
        st = re.search(r'starting at\s+(\d{1,2})(?::(\d{2}))?', pl)
        durs = re.findall(r'takes\s+(\d+(?:\.\d+)?)\s*hour', pl)
        if not (st and durs) or not _has(pl, r'one after another|sequential|in order'):
            return None
        return {'start': _f(st.group(1)) + (_f(st.group(2)) / 60 if st.group(2) else 0),
                'durations': [float(d) for d in durs]}

    @staticmethod
    def execute(start: float, durations: List[float]) -> float:
        return start + sum(durations)

    @staticmethod
    def semantic(prompt: str, params):
        p = prompt.lower()
        if not _has(p, r'finish|end|done'):
            return False, 'not asking for a finish time'
        if _has(p, r'\bbreak\b|parallel|at the same time|overlap'):
            return False, 'non-sequential structure'
        return True, 'sequential finish-time meaning confirmed'

    @staticmethod
    def verify(params, result):
        return result >= params['start'], 'finish after start'


# ---- compositional (known operators combined) ----------------------------
@template('pct_then_div(p,v,d)', ['finance', 'proportion', 'percent', 'compose'],
          Envelope(required_params=['p', 'v', 'd'], param_ranges={'d': [1e-9, None]},
                   required_features=['extra_step']),
          [('unit_conversion', ', expressed in pounds')])
class PctThenDiv:
    @staticmethod
    def parse(p: str):
        pl = p.lower()
        m = re.search(r'(\d+(?:\.\d+)?)\s*%\s*of\s*(\d[\d,]*(?:\.\d+)?),?\s*then divide (?:the result )?by\s*(\d+(?:\.\d+)?)', pl)
        return {'p': _f(m.group(1)), 'v': _f(m.group(2)), 'd': _f(m.group(3))} if m else None

    @staticmethod
    def execute(p, v, d):
        return round(p * v / 100.0 / d, 2)

    @staticmethod
    def semantic(prompt, params):
        return (_has(prompt.lower(), r'then divide'), 'divide-after cue')

    @staticmethod
    def verify(params, result):
        return math.isfinite(result), 'finite'


@template('discount_then_tax(v,p,t)', ['finance', 'pricing', 'percent', 'compose'],
          Envelope(required_params=['v', 'p', 't'], required_features=['tax']),
          [('unit_conversion', ' in euros')])
class DiscountThenTax:
    @staticmethod
    def parse(p: str):
        pl = p.lower()
        m = re.search(r'\$\s?(\d[\d,]*(?:\.\d+)?)\s*item is\s*(\d+(?:\.\d+)?)%\s*off[;,]?\s*then\s*(\d+(?:\.\d+)?)%\s*(?:sales\s*)?tax', pl)
        return {'v': _f(m.group(1)), 'p': _f(m.group(2)), 't': _f(m.group(3))} if m else None

    @staticmethod
    def execute(v, p, t):
        return round(v * (100 - p) / 100.0 * (100 + t) / 100.0, 2)

    @staticmethod
    def semantic(prompt, params):
        pl = prompt.lower()
        return (_has(pl, r'\boff\b') and _has(pl, r'\btax\b'), 'discount + tax cues')

    @staticmethod
    def verify(params, result):
        return 0 <= result, 'non-negative'


# ----------------------------------------------------------- fitting ----
def fit_templates(prompt: str, target: Optional[float]) -> List[Dict[str, Any]]:
    """Which templates (a) parse this prompt AND (b) reproduce the target
    number? This is the deterministic V_L check for a K-level answer and the
    seed of induction. Returns [] when nothing reproduces it."""
    if target is None:
        return []
    out = []
    from .competency import PARSERS, EXECUTORS
    for sig, t in TEMPLATES.items():
        try:
            params = PARSERS[t['name']](prompt)
            if not params:
                continue
            val = EXECUTORS[t['name']](**params)
            if isinstance(val, (int, float)) and math.isfinite(val) and abs(val - target) <= max(t['tol'], abs(target) * 0.005):
                out.append({'signature': sig, 'name': t['name'], 'params': params, 'result': val})
        except Exception:
            continue
    return out


def all_parses(prompt: str) -> List[Dict[str, Any]]:
    """Every template whose parser accepts the prompt (regardless of answer)."""
    from .competency import PARSERS
    out = []
    for sig, t in TEMPLATES.items():
        try:
            params = PARSERS[t['name']](prompt)
            if params:
                out.append({'signature': sig, 'name': t['name'], 'params': params})
        except Exception:
            continue
    return out
