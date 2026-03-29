"""Reusable strategies: scripted queues and uniformly random legal moves."""

from __future__ import annotations

import random
from collections import deque
from collections.abc import Iterable

from app.actions import Action
from app.actor_view import ActorView
from app.hand import Strategy


def legal_actions_for_view(view: ActorView) -> list[Action]:
    """Reconstruct legal actions from an :class:`~app.actor_view.ActorView`.

    Matches the engine in ``app.hand`` when ``can_fold`` reflects the active
    node (notably Player 2 after Player 1 checked may not fold).
    """
    actions: list[Action] = []
    if view.can_fold:
        actions.append(Action.fold())
    if view.can_check:
        actions.append(Action.check())
    if view.can_call:
        actions.append(Action.call())
    if view.can_raise:
        if view.raise_amount_min is None or view.raise_amount_max is None:
            raise ValueError("can_raise requires raise_amount_min/max.")
        actions.extend(
            Action.raise_(a)
            for a in range(view.raise_amount_min, view.raise_amount_max + 1)
        )
    return actions


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
