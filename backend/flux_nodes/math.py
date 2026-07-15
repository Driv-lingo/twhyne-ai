#!/usr/bin/env python3
"""Math Node.

Uses SymPy for EXACT symbolic and numeric computation (arithmetic, algebra,
calculus). Falls back to the shared Mistral LLM only for word problems that
SymPy cannot parse. This guarantees correct answers for real math instead of
relying on a language model's approximate arithmetic.
"""

import logging
import re
from pathlib import Path
from typing import Any, Optional

from .base import FluxNode
from . import MODELS_DIR

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

try:
    import sympy
    from sympy import symbols, solve, diff, integrate, simplify, Eq, N, Integer, Float, Rational
    from sympy.parsing.sympy_parser import (
        parse_expr, standard_transformations,
        implicit_multiplication_application, convert_xor,
    )
    SYMPY_AVAILABLE = True
    _TRANSFORMS = standard_transformations + (implicit_multiplication_application, convert_xor)
    # For plain arithmetic, implicit multiplication is dangerous: it turns any
    # leftover word ("Compute") into a product of symbols (C*o*m*p*u*t*e).
    _ARITH_TRANSFORMS = standard_transformations + (convert_xor,)
except Exception as e:  # pragma: no cover
    SYMPY_AVAILABLE = False
    logger.error(f"SymPy not available: {e}")

try:
    from llama_cpp import Llama
except ImportError:
    Llama = None


# Natural-language operators -> symbols, applied before parsing.
_WORD_OPS = [("divided by", "/"), ("multiplied by", "*"), ("times", "*"),
             ("plus", "+"), ("minus", "-"), ("to the power of", "**"),
             ("power of", "**"), ("squared", "**2"), ("cubed", "**3")]
_FILLER_RE = re.compile(r"^(what\s+is|what's|compute|calculate|evaluate|find|tell\s+me|give\s+me)\b[\s:]*", re.I)
# Longest run of expression-safe characters (digits, x/y/z/t vars, operators).
_EXPR_RUN_RE = re.compile(r"[0-9xyzt\.\s\+\-\*/\^\(\)=]+")


def _normalize(query: str) -> str:
    """Trim punctuation and replace word operators with symbols."""
    s = query.strip().rstrip('?.!').strip()
    # Real users type unicode operators and thousands separators:
    # "47 × 8,912" must become "47 * 8912" before parsing.
    s = (s.replace('×', '*').replace('÷', '/')
          .replace('−', '-').replace('·', '*'))
    s = re.sub(r'(?<=\d),(?=\d)', '', s)
    # The classic trick: "divide 30 by half" means 30/0.5 (=60), not 30/2.
    # "half OF x" is multiplication and stays untouched.
    s = re.sub(r'\bby\s+half\b', 'by 0.5', s, flags=re.I)
    s = re.sub(r'\bhalf\s+of\s+', '0.5 * ', s, flags=re.I)
    # Chain form ANYWHERE in the sentence ("If you divide 30 by 0.5 and add
    # 10, what do you get?"): the anchored version missed every phrasing
    # that wrapped the imperative in a question.
    s = re.sub(r'divide\s+([\d.]+)\s+by\s+([\d.]+)\s+and\s+(add|plus)\s+([\d.]+)',
               r'((\1 / \2) + \4)', s, flags=re.I)
    s = re.sub(r'divide\s+([\d.]+)\s+by\s+([\d.]+)\s+and\s+subtract\s+([\d.]+)',
               r'((\1 / \2) - \3)', s, flags=re.I)
    s = re.sub(r'divide\s+([\d.]+)\s+by\s+([\d.]+)', r'(\1 / \2)', s, flags=re.I)
    sl = ' ' + s + ' '
    for w, o in _WORD_OPS:
        # Replacement via lambda: '*' must be inserted literally. Escaping it
        # in a replacement STRING leaves a literal backslash behind ('58 \* 73'),
        # which broke every 'times'/'multiplied by' query.
        sl = re.sub(r'\s' + w + r'\s', lambda _m, _o=o: f' {_o} ', sl, flags=re.I)
    return sl.strip()


def _extract_expression(q: str) -> Optional[str]:
    """Pull the arithmetic expression out of a natural-language question.

    "What is 23 * 244866?" -> "23 * 244866". Returns None if no expression
    containing a digit is found (then the LLM fallback handles it).
    """
    s = q
    prev = None
    while prev != s:
        prev = s
        s = _FILLER_RE.sub('', s).strip()
    runs = _EXPR_RUN_RE.findall(s)
    if not runs:
        return None
    cand = max(runs, key=len).strip()
    return cand if re.search(r'\d', cand) else None


class MathNode(FluxNode):
    """Exact math via SymPy, with an LLM fallback for natural-language problems."""

    def __init__(self, model_path: Optional[Path] = None, node_id: str = "math-llm-eval",
                 name: str = "Math (SymPy Symbolic)",
                 description: str = "Exact arithmetic, algebra and calculus using SymPy, with an LLM fallback.",
                 **kwargs: Any):
        super().__init__(node_id, name, description, **kwargs)
        self.keywords = {"math", "calculate", "compute", "solve", "equation", "derivative",
                         "integral", "integrate", "differentiate", "simplify", "sum", "product"}
        self.metadata = {"engine": "sympy", "capabilities": "arithmetic,algebra,calculus,symbolic"}
        self.model_path = model_path or (MODELS_DIR / 'mistral-7b-instruct-q4.gguf')
        # Node is available as long as SymPy loaded; the LLM fallback is a bonus.
        self.is_available = SYMPY_AVAILABLE

    # -- SymPy path ---------------------------------------------------------
    def _try_sympy(self, query: str) -> Optional[str]:
        if not SYMPY_AVAILABLE:
            return None
        q = _normalize(query)
        ql = q.lower()
        x, y, z, t = symbols('x y z t')
        local = {'x': x, 'y': y, 'z': z, 't': t}
        try:
            # Answers ship as LaTeX ($$...$$): the UI typesets it with KaTeX;
            # any other client still sees readable TeX source.
            from sympy import latex as _ltx

            # Derivative
            m = re.search(r'(?:derivative|differentiate)\s+(?:of\s+)?(.+?)(?:\s+with respect to\s+(\w+))?$', ql)
            if m:
                expr = parse_expr(m.group(1), transformations=_TRANSFORMS, local_dict=local)
                var = symbols(m.group(2)) if m.group(2) else x
                return (f"$$\\frac{{d}}{{d{var}}}\\left({_ltx(expr)}\\right)"
                        f" = {_ltx(diff(expr, var))}$$")

            # Integral
            m = re.search(r'(?:integral|integrate)\s+(?:of\s+)?(.+?)(?:\s+with respect to\s+(\w+))?$', ql)
            if m:
                expr = parse_expr(m.group(1), transformations=_TRANSFORMS, local_dict=local)
                var = symbols(m.group(2)) if m.group(2) else x
                return (f"$$\\int {_ltx(expr)}\\, d{var}"
                        f" = {_ltx(integrate(expr, var))} + C$$")

            # Equation solving
            if 'solve' in ql or ('=' in q and '==' not in q):
                eq_str = re.sub(r'^\s*solve\s*(for\s+\w+\s*[:,]?)?\s*', '', ql).strip()
                eq_str = re.sub(r'\bfor\s+\w+\s*$', '', eq_str).strip()
                if '=' in eq_str:
                    lhs, rhs = eq_str.split('=', 1)
                    equation = Eq(parse_expr(lhs, transformations=_TRANSFORMS, local_dict=local),
                                  parse_expr(rhs, transformations=_TRANSFORMS, local_dict=local))
                else:
                    equation = parse_expr(eq_str, transformations=_TRANSFORMS, local_dict=local)
                syms = sorted(equation.free_symbols, key=lambda s: s.name) if hasattr(equation, 'free_symbols') else [x]
                target = syms[0] if syms else x
                sol = solve(equation, target)
                sol_tex = ",\\; ".join(_ltx(s) for s in sol) if isinstance(sol, list) else _ltx(sol)
                return f"$${_ltx(target)} = {sol_tex}$$"

            # Plain expression -> exact value. Extract the expression from the
            # sentence first so surrounding words never become symbols.
            expr_str = _extract_expression(q)
            if not expr_str:
                return None
            expr = parse_expr(expr_str, transformations=_ARITH_TRANSFORMS, local_dict=local)
            val = simplify(expr)
            if not val.free_symbols:
                # numeric result: exact value typeset with the expression it
                # came from - unless the parser already evaluated it (then
                # "expr = val" would print "256 = 256").
                lhs = _ltx(expr)
                eq = f"{lhs} = " if lhs != _ltx(val) else ""
                if isinstance(val, Integer):
                    return f"$${eq}{_ltx(val)}$$"
                if isinstance(val, Float) and val == int(val):
                    return f"$${eq}{int(val)}$$"
                approx = str(N(val, 12)).rstrip('0').rstrip('.')
                if str(val) != str(N(val, 12)):
                    return f"$${eq}{_ltx(val)} \\approx {approx}$$"
                return f"$${eq}{approx}$$"
            return f"$${_ltx(val)}$$"
        except Exception as e:
            logger.info(f"SymPy could not parse '{query}': {e}")
            return None

    # -- LLM fallback -------------------------------------------------------
    def generate(self, query: str, **kwargs: Any) -> Optional[str]:
        exact = self._try_sympy(query)
        if exact is not None:
            logger.info(f"Math solved exactly via SymPy: {query} -> {exact}")
            return exact
        # Word problem: let the LLM restate it, but note it's an estimate.
        try:
            if Llama is None or not Path(self.model_path).exists():
                return "I couldn't parse that as a math expression."
            # Fetch at call time (do not cache): the shared cache keeps one
            # resident model and may evict/reload between calls.
            from .shared_model import get_shared_model, INFER_LOCK
            # The SymPy path above is lock-free; only this LLM fallback
            # must serialize with other generations.
            with INFER_LOCK:
                llm = get_shared_model(self.model_path)
                out = llm(f"Solve this math problem step by step and give the final numeric answer:\n{query}\nAnswer:",
                          max_tokens=768, stop=["</s>"], temperature=0.2, echo=False)
            return out['choices'][0]['text'].strip()
        except Exception as e:
            logger.error(f"Math LLM fallback error: {e}")
            return f"Error: {e}"
