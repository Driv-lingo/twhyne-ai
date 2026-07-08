"""Unit tests for the math node's exact (SymPy) path.

These are the same prompts the benchmark harness uses. They must all solve
EXACTLY via SymPy - if any falls through to the LLM fallback the answer is
not guaranteed correct and the test fails.
"""

import pathlib
import sys

import pytest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from flux_nodes.math import MathNode, _extract_expression, _normalize  # noqa: E402


def _node():
    # Point at a nonexistent model path: these tests must pass WITHOUT any
    # LLM, because the whole point of the SymPy path is exactness.
    return MathNode(model_path=pathlib.Path('/nonexistent/model.gguf'))


@pytest.mark.parametrize("prompt,expected", [
    ("What is 23 * 244866?", "5631918"),
    ("What is 12 * 244688?", "2936256"),
    ("Compute 987654 + 123456.", "1111110"),
    ("What is 144 divided by 12?", "12"),
    ("2+2", "4"),
    ("what is 2 plus 2", "4"),
    # Live-test regressions: unicode operators and thousands separators.
    ("what is 47 × 8,912?", "418864"),
    ("6 ÷ 2", "3"),
    ("1,000 + 2,500", "3500"),
    # Exhaustive-benchmark regression: the '*' word-operator replacement
    # left a literal backslash and broke every times/multiplied-by query.
    ("58 times 73", "4234"),
    ("6 multiplied by 7", "42"),
    ("What is 0.5 * 8?", "4"),
])
def test_exact_arithmetic(prompt, expected):
    out = _node()._try_sympy(prompt)
    assert out is not None, f"SymPy failed to parse: {prompt!r}"
    assert expected in out


def test_solve_equation():
    out = _node()._try_sympy("Solve for x: 3*x + 6 = 21")
    assert out is not None
    assert "5" in out


def test_filler_words_do_not_become_symbols():
    # Regression: "Compute" once parsed as C*o*m*p*u*t*e via implicit
    # multiplication and produced symbolic garbage.
    out = _node()._try_sympy("Compute 987654 + 123456.")
    assert out == "1111110"


def test_extraction_helpers():
    assert _extract_expression(_normalize("What is 23 * 244866?")) == "23 * 244866"
    assert _extract_expression(_normalize("What is 144 divided by 12?")) == "144 / 12"
    assert _extract_expression(_normalize("58 times 73")) == "58 * 73"
    assert _extract_expression(_normalize("tell me a story")) is None


def test_non_math_returns_none():
    # Non-math prompts must fall through (router handles them elsewhere).
    assert _node()._try_sympy("How can I build a fence for a giraffe?") is None
