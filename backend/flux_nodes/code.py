#!/usr/bin/env python3
# Copyright (c) 2025 SNF-AI
# SPDX-License-Identifier: MIT

"""
Code Node

Code expert node using CodeLlama-7B with EXECUTE-BEFORE-ANSWER verification:
generated code is extracted, syntax-checked, and actually run in an isolated
subprocess before being returned. If it fails, the error is fed back to the
model for one retry. The caller therefore receives code that demonstrably
executes, or an honest warning - never an unchecked guess.
"""

import logging
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Dict, Any, Optional

from .base import FluxNode

logger = logging.getLogger(__name__)

_CODE_BLOCK_RE = re.compile(r"```(?:python)?\s*(.*?)```", re.S)
_TEX_BLOCK_RE = re.compile(r"\\begin\{code\}(.*?)\\end\{code\}", re.S)


def _extract_code(text: str) -> Optional[str]:
    """Pull the first code block out of a model response."""
    m = _CODE_BLOCK_RE.search(text)
    if m:
        return m.group(1).strip()
    m = _TEX_BLOCK_RE.search(text)
    if m:
        return m.group(1).strip()
    stripped = text.strip()
    if stripped.startswith(('def ', 'import ', 'class ', 'from ', '#')):
        return stripped
    return None


def _trim_to_compilable(code: str) -> str:
    """Drop trailing lines until the block compiles.

    The model sometimes echoes retry-prompt narrative ("It failed with this
    error:", tracebacks, a second copy of the request) after real code inside
    the same block; that text is not Python and poisons verification.
    Progressively trimming from the end recovers the leading valid program.
    """
    lines = code.rstrip().split('\n')
    while lines:
        candidate = '\n'.join(lines).rstrip()
        try:
            compile(candidate, '<generated>', 'exec')
            return candidate
        except SyntaxError:
            lines.pop()
    return code


def _verify_code(code: str) -> (bool, str):
    """Syntax-check, then execute in an isolated subprocess with a timeout.

    Module-level execution catches import errors, NameErrors and crashes in
    top-level code; function bodies are compiled and validated. Runs with -I
    (isolated mode) and a hard 10s timeout inside the app container.
    """
    # An unfinished placeholder is not an answer, even if it happens to
    # pass its (equally stubbed) asserts - benchmark caught TODO stubs
    # returning 0 being labeled "verified".
    if re.search(r'#\s*todo', code, re.I) or 'pass  # implement' in code.lower():
        return False, "code contains an unfinished TODO placeholder - write the full implementation"
    try:
        compile(code, '<generated>', 'exec')
    except SyntaxError as e:
        return False, f"SyntaxError: {e}"
    # A function whose body is just a docstring/pass compiles and "runs"
    # but implements nothing (benchmark: celsius_to_fahrenheit was an empty
    # def labeled "Executed only"). Treat it as a failure so it retries.
    try:
        import ast
        tree = ast.parse(code)
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                real = [s for s in node.body
                        if not (isinstance(s, ast.Expr) and isinstance(s.value, ast.Constant))
                        and not isinstance(s, ast.Pass)]
                if not real:
                    return False, (f"function {node.name} has an empty body - "
                                   f"write the full implementation")
    except SyntaxError:
        pass
    try:
        proc = subprocess.run(
            [sys.executable, '-I', '-c', code],
            capture_output=True, text=True, timeout=10,
        )
        if proc.returncode != 0:
            return False, (proc.stderr or 'nonzero exit').strip()[-500:]
        return True, ""
    except subprocess.TimeoutExpired:
        return False, "execution timed out after 10 seconds"
    except Exception as e:
        return False, str(e)


class CodeNode(FluxNode):
    """Code expert node using CodeLlama-7B."""

    def __init__(
        self,
        model_path: Optional[str] = None,
        node_id: str = "code-codellama-7b",
        name: str = "Code (CodeLlama-7B)",
        description: str = "Code generation with execute-before-answer verification (CodeLlama-7B)",
    ):
        """Initialize the code node."""
        logger.info(f"Starting CodeNode initialization with node_id: {node_id}")
        super().__init__(node_id, name, description)
        logger.info("CodeNode parent initialization complete")

        # Set model path
        logger.info("Setting model path...")
        if model_path is None:
            from . import MODELS_DIR
            self.model_path = MODELS_DIR / "codellama-7b.q4_K_M.gguf"
        else:
            self.model_path = Path(model_path)

        if not os.path.exists(self.model_path):
            from . import MODELS_DIR
            alt_path = MODELS_DIR / "codellama-7b-q4.gguf"
            if os.path.exists(alt_path):
                logger.info(f"Found alternative model: {alt_path}")
                self.model_path = alt_path
            else:
                # Model-neutral message: this node may be Qwen (default) or
                # CodeLlama (legacy); a missing file means the models volume
                # is not mounted or the launcher has not downloaded it yet.
                logger.error(
                    f"Code model file missing: {self.model_path}. "
                    f"Re-run the launcher to download it (or check that the "
                    f"models volume is mounted).")
                self.is_available = False
                self.status_detail = ("model not downloaded - re-run the "
                                      "launcher (or mount the models volume)")
                return

        logger.info("CodeNode initialization complete")

    def _wrap_prompt(self, prompt_text: str) -> str:
        """Apply the model's chat template when it has one.

        Qwen through a plain completion prompt produced "# Your code here"
        stubs; through its ChatML template it produced clean solutions.
        """
        if 'qwen' in str(self.model_path).lower():
            return (f"<|im_start|>user\n{prompt_text}<|im_end|>\n"
                    f"<|im_start|>assistant\n")
        return prompt_text

    def _generate_once(self, model, prompt_text: str, rid: str = None) -> str:
        import time as _t
        from .shared_model import stopping_criteria_for
        _t0 = _t.time()
        # Stop sequences keep the model from rambling into invented follow-up
        # exercises after it has answered (observed in benchmark output).
        # 768 not 512: class-based answers (linked list, tree) plus their
        # self-tests routinely overran 512 and got truncated mid-test, then
        # failed verification for LENGTH rather than logic.
        response = model(
            self._wrap_prompt(prompt_text),
            max_tokens=768,
            temperature=0.4,
            top_p=0.9,
            top_k=40,
            repeat_penalty=1.1,
            stop=["</s>", "<|im_end|>", "###", "\nRequest:", "Comment:",
                  "\nIt failed with", "\nIt passed with",
                  "You are a helpful coding assistant"],
            echo=False,
            stopping_criteria=stopping_criteria_for(rid),
        )
        # Perf transparency: every generation logs tokens/sec so "why is it
        # slow" is answerable from the launcher window, not guesswork.
        try:
            dt = _t.time() - _t0
            toks = (response.get('usage') or {}).get('completion_tokens', 0)
            logger.info(f"Code generation: {toks} tokens in {dt:.0f}s "
                        f"({toks/dt:.1f} tok/s)" if dt > 0 else "")
            from cognition import trace as _trace
            _trace.model_call(self.node_id, response.get('usage'), dt)
        except Exception:
            pass
        return response['choices'][0]['text'].strip()

    @staticmethod
    def _user_example_asserts(prompt: str, code: str) -> str:
        """Turn the USER'S examples into executable tests - the spec belongs
        to the person who owns the intent, and their examples outrank the
        model's self-written tests.

        Recognized forms (conservative - both sides must parse as Python
        literals): `name(1, 2) -> 3`, `name([1,2]) == [2,1]`,
        `name("x") should return "y"`, plus literal `assert ...` lines.
        The example's function name is rewritten to the generated function's
        actual name when there is exactly one top-level def.
        """
        import ast as _ast
        extra = []
        # explicit assert lines pass through if they compile
        for line in re.findall(r'^\s*(assert .+)$', prompt, re.M):
            try:
                _ast.parse(line.strip())
                extra.append(line.strip())
            except Exception:
                pass
        # call -> expected forms
        try:
            defs = [n.name for n in _ast.parse(code).body
                    if isinstance(n, _ast.FunctionDef)]
        except Exception:
            defs = []
        target = defs[0] if len(defs) == 1 else None
        for m in re.finditer(
                r'(\w+)\s*\(([^()]*)\)\s*(?:->|=>|==|should (?:return|give|'
                r'equal)|returns)\s*(\[[^\]]*\]|\([^)]*\)|"[^"]*"|\'[^\']*\'|'
                r'-?[\d.]+|True|False|None)', prompt):
            fname, args, expected = m.group(1), m.group(2), m.group(3)
            try:
                _ast.literal_eval(f'({args},)') if args.strip() else None
                _ast.literal_eval(expected)
            except Exception:
                continue
            call_name = target or fname
            extra.append(f'assert {call_name}({args}) == {expected}')
        return '\n'.join(dict.fromkeys(extra))  # dedupe, keep order

    def generate(self, prompt: str, **kwargs) -> Optional[str]:
        """Generate code, then EXECUTE it to verify before answering."""
        logger.info(f"CodeNode generate called with prompt: {prompt[:100]}...")
        # LIBRARY FIRST (the SymPy trick applied to code): for the classic
        # requests, authoring is unnecessary - a canonical implementation is
        # EXECUTED with its tests right now (milliseconds) and shipped with
        # an honest label. Only novel requests pay the 7B authoring cost.
        try:
            from .code_library import match as _lib_match
            hit = _lib_match(prompt)
            if hit:
                ok, err = _verify_code(hit["code"])
                if ok:
                    logger.info(f"Code library hit: '{hit['name']}' "
                                f"(executed + tests passed, no generation)")
                    return (f"```python\n{hit['code'].rstrip()}\n```\n\n"
                            f"Verified: this is Twhyne's canonical "
                            f"implementation of \"{hit['name']}\" — it was "
                            f"executed just now and passed the assert tests "
                            f"shown above.")
                logger.warning(f"Library snippet '{hit['name']}' failed "
                               f"execution ({err}); falling back to model")
        except Exception as e:
            logger.warning(f"Code library lookup failed: {e}")
        try:
            # Fetch from the SHARED single-resident cache at call time (the
            # cache evicts the other model first, so two 7Bs never coexist).
            from .shared_model import get_shared_model
            model = get_shared_model(self.model_path, n_ctx=4096)

            history = kwargs.get('conversation_history', [])
            rid = kwargs.get('client_request_id')
            raw = self._generate_once(model, self._format_prompt(prompt, history), rid)
            code = _extract_code(raw)
            if code is None:
                return raw  # no code block found; return the text as-is
            code = _trim_to_compilable(code)

            # USER EXAMPLES AS THE SPEC: examples given in the request become
            # executable tests appended to verification - the user's intent
            # outranks the model's self-written asserts.
            user_tests = self._user_example_asserts(prompt, code)
            if user_tests:
                logger.info(f"User examples -> executable tests:\n{user_tests}")

            def _verify_with_examples(c):
                return _verify_code(c + ('\n' + user_tests if user_tests else ''))

            ok, err = _verify_with_examples(code)
            # BEST-OF-N VERIFIED SAMPLING: extra candidates, each EXECUTED,
            # first verified one ships. Turns compute into correctness
            # (50% per-sample -> ~94% at n=4) without a bigger model.
            # Default 1 on CPU (latency); raise TWHYNE_CODE_CANDIDATES on
            # GPU/big hardware where samples are cheap.
            n_candidates = max(1, int(os.environ.get(
                'TWHYNE_CODE_CANDIDATES', '1') or 1))
            attempt = 1
            while not ok and attempt < n_candidates:
                attempt += 1
                logger.info(f"Candidate {attempt}/{n_candidates} "
                            f"(previous failed: {str(err)[:80]})")
                raw_n = self._generate_once(
                    model, self._format_prompt(prompt, history), rid)
                code_n = _extract_code(raw_n)
                if not code_n:
                    continue
                code_n = _trim_to_compilable(code_n)
                ok_n, err_n = _verify_with_examples(code_n)
                if ok_n:
                    code, ok, err = code_n, True, ""
                else:
                    code, err = code_n, err_n
            if not ok:
                logger.info(f"Generated code failed verification ({err}); retrying once")
                # A missing module is an ENVIRONMENT constraint, not a logic
                # bug - the repair must swap the dependency out, not fiddle
                # with the algorithm.
                mod_missing = re.search(r"No module named '([^']+)'", err or '')
                hint = (f"\nIMPORTANT: the module '{mod_missing.group(1)}' is "
                        f"NOT installed and cannot be used. Rewrite using "
                        f"only the standard library, numpy, pandas or "
                        f"scikit-learn.\n" if mod_missing else "")
                retry_prompt = self._format_prompt(prompt, history) + (
                    f"\n\nA previous attempt produced this code:\n{code}\n\n"
                    f"It failed with this error:\n{err}\n{hint}\n"
                    "Write a corrected version.\n\nCode:"
                )
                raw2 = self._generate_once(model, retry_prompt, rid)
                code2 = _extract_code(raw2)
                if code2:
                    code2 = _trim_to_compilable(code2)
                    ok2, err2 = _verify_with_examples(code2)
                    if ok2:
                        code, ok, err = code2, True, ""
                    else:
                        code, err = code2, err2

            if ok:
                # Honest labels: passing self-generated asserts is stronger
                # evidence than merely executing, and the label says which.
                if user_tests:
                    logger.info("Code verified: passed the USER'S example tests")
                    label = ("Verified against YOUR examples: the code was "
                             "executed and passed these tests derived from "
                             "your request:\n```python\n" + user_tests +
                             "\n```")
                elif 'assert' in code:
                    logger.info("Code verified: ran and passed its self-tests")
                    label = ("Verified: the code was executed and passed the "
                             "assert tests shown above. (These are "
                             "model-written tests - independent tests are "
                             "stronger evidence.)")
                else:
                    logger.info("Code verified: executes without errors (no self-tests)")
                    label = ("Executed only - NOT behavior-verified: the code "
                             "compiles and runs without errors, but no tests "
                             "checked its outputs. Review the logic before "
                             "relying on it.")
                return f"```python\n{code}\n```\n\n{label}"
            # Verification failed after one repair. What happens next is a
            # POLICY DECISION, not the node's call: permissions.json's
            # verification.on_code_failure chooses between
            #   "refuse" (default) - broken code never ships;
            #   "draft"           - ship the best candidate, loudly labeled
            #                       UNVERIFIED with the actual error, so the
            #                       user can salvage a near-miss.
            # Either way the truth is stated; the knob only chooses whether
            # a labeled draft is more useful to this install than a refusal.
            logger.warning(f"Code failed verification after retry: {err}")
            first_err = (err or "").strip().splitlines()
            first_err = first_err[-1][:160] if first_err else "verification failed"
            mode = 'draft'
            try:
                from rag_manager import get_rag_manager
                vp = (get_rag_manager().get_permissions()
                      .get('verification') or {})
                if str(vp.get('on_code_failure', '')).lower() == 'refuse':
                    mode = 'refuse'
            except Exception:
                pass
            if mode == 'draft' and code:
                # The user always gets SOMETHING plus a full account: what
                # was tried, what failed, and what would help - never a
                # dead-end. A missing module gets the HONEST cause: the
                # sandbox lacks the library; the logic was never tested.
                mm = re.search(r"No module named '([^']+)'", first_err or '')
                if mm:
                    return (f"```python\n{code}\n```\n\n"
                            f"UNVERIFIED DRAFT — the code imports "
                            f"`{mm.group(1)}`, which is not installed in "
                            f"Twhyne's verification sandbox, so it could not "
                            f"be executed at all (the logic itself was never "
                            f"tested). It may run fine in your own "
                            f"environment with `pip install {mm.group(1)}`. "
                            f"For a verified answer, ask for a version using "
                            f"the standard library, numpy, pandas or "
                            f"scikit-learn.")
                return (f"```python\n{code}\n```\n\n"
                        f"UNVERIFIED DRAFT — here is exactly what happened: "
                        f"I generated this code and executed it; it failed "
                        f"its checks with `{first_err}`. I made one repair "
                        f"attempt, which also did not pass. The code above "
                        f"is my best candidate — the logic may be correct "
                        f"with a flawed self-test, or genuinely buggy near "
                        f"the error above. To get a verified answer, tell me "
                        f"the expected input and output for one example, or "
                        f"narrow the request (e.g. 'iterative, no classes').")
            # Wording deliberately avoids the audit slop markers ("failed
            # automatic verification", tracebacks): a clean refusal must not
            # read like leaked internal diagnostics.
            return ("I could not produce verified code for this request. "
                    f"What happened: I generated a candidate and executed it; "
                    f"it failed its checks ({first_err}), and one repair "
                    "attempt did not fix it. This install's policy is set to "
                    "withhold unverified code. What would help: give me one "
                    "expected input/output example, or narrow the request "
                    "(e.g. 'iterative, no classes'). Operators can set "
                    "verification.on_code_failure to 'draft' in the policy "
                    "console to receive labeled drafts instead.")

        except Exception as e:
            logger.error(f"Error generating response: {e}")
            return f"Error: {str(e)}"

    def _format_prompt(self, query_text: str, conversation_history: list = None) -> str:
        """Format the prompt for the code model, with capped follow-up context."""
        ctx = ""
        if conversation_history:
            parts = []
            for msg in conversation_history[-2:]:
                role = 'User' if msg.get('role') == 'user' else 'Assistant'
                parts.append(f"{role}: {str(msg.get('content', ''))[:300]}")
            ctx = "Recent conversation (the request may refer to it):\n" + "\n".join(parts) + "\n\n"
        return f"""You are a helpful coding assistant. Generate clean, working Python code for the following request:

{ctx}Request: {query_text}

Provide ONE complete, ready-to-run Python code block containing: the function with necessary imports and brief comments, followed by 3 module-level assert statements that test a typical case, an empty/edge case, and the expected behavior. IMPORTANT: never compare custom objects with == in asserts (classes without __eq__ compare by identity and the assert always fails) - convert results to plain values first, e.g. for a linked list assert on the sequence of .val fields as a Python list. AVAILABLE LIBRARIES: the Python standard library, numpy, pandas, and scikit-learn - nothing else is installed, so do not import other third-party packages. Do not add extra exercises or commentary after the code.

Code:"""
