"""Reusable strategies: scripted queues and uniformly random legal moves."""

from __future__ import annotations

import random
from collections import deque
from collections.abc import Iterable

from app.actions import Action
from app.actor_view import ActorView
from app.hand import Strategy
from app.legal_actions import legal_actions_for_view

__all__ = [
    "HotseatStrategy",
    "RandomLegalStrategy",
    "ScriptedStrategy",
    "legal_actions_for_view",
]


class HotseatStrategy:
    """Delegate action selection to a callable (e.g. stdin prompts in ``app.cli``)."""

    def __init__(self, choose: Strategy) -> None:
        self._choose = choose

    def __call__(self, rng: random.Random, view: ActorView) -> Action:
        return self._choose(rng, view)


class ScriptedStrategy:
    """Play a fixed sequence of actions (testing / demos).

    Each call consumes the next queued action. Exhaustion raises
    ``RuntimeError``.
    """

    def __init__(self, actions: Iterable[Action]) -> None:
        self._queue: deque[Action] = deque(actions)

    def __call__(self, _rng: random.Random, _view: ActorView) -> Action:
        if not self._queue:
            msg = "ScriptedStrategy has no remaining actions."
            raise RuntimeError(msg)
        return self._queue.popleft()


class RandomLegalStrategy:
    """Choose uniformly among actions consistent with ``view``."""

    def __call__(self, rng: random.Random, view: ActorView) -> Action:
        legal = legal_actions_for_view(view)
        if not legal:
            msg = "No legal actions derived from view (engine mismatch?)."
            raise RuntimeError(msg)
        return rng.choice(legal)
