"""Process-wide cognition runtime: one WorkDomainModel, one CompetencyLibrary,
one Controller - lazily built, local-only, shared by the server hooks.

Mode (per request `mode`, else TWHYNE_MODE env, else 'current'):
  plain       condition A - bare model (handled by /query/plain)
  current     condition B - today's pipeline; cognition layer inert
  structured  condition C - state/router/verification dims active,
              competencies NEVER induced or executed
  full        condition D - C plus K->R->S maturation and Tier-0 execution
"""
from __future__ import annotations

import os
import threading
from typing import Optional

from .state import WorkDomainModel
from .competency import CompetencyLibrary, PromotionPolicy
from .controller import Controller
from . import operators  # noqa: F401  (registers templates)

_lock = threading.Lock()
_ctl: Optional[Controller] = None
_wda: Optional[WorkDomainModel] = None
_lib: Optional[CompetencyLibrary] = None


def policy_from_env() -> PromotionPolicy:
    p = PromotionPolicy()
    p.min_successes_for_R = int(os.environ.get('TWHYNE_PROMOTE_R', p.min_successes_for_R))
    p.min_successes_for_S = int(os.environ.get('TWHYNE_PROMOTE_S', p.min_successes_for_S))
    p.min_expected_value_ratio = float(os.environ.get('TWHYNE_EV_RATIO', p.min_expected_value_ratio))
    return p


def get_wda() -> WorkDomainModel:
    global _wda
    with _lock:
        if _wda is None:
            _wda = WorkDomainModel()
        return _wda


def get_library() -> CompetencyLibrary:
    global _lib
    with _lock:
        if _lib is None:
            _lib = CompetencyLibrary(policy=policy_from_env())
        return _lib


def get_controller() -> Controller:
    global _ctl
    if _ctl is None:
        lib, wda = get_library(), get_wda()
        with _lock:
            if _ctl is None:
                _ctl = Controller(lib, wda)
    return _ctl


def reset() -> None:
    """Tests only: drop the singletons so a fresh state dir takes effect."""
    global _ctl, _wda, _lib
    with _lock:
        _ctl = _wda = _lib = None


def mode_active(mode: str) -> bool:
    return mode in ('structured', 'full')
