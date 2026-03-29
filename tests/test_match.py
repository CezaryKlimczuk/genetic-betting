"""T5: match loop, alternating first actor, bankruptcy and hand cap."""

from __future__ import annotations

import random
from collections import deque
from unittest.mock import patch

from app.actions import Action
from app.config import GameConfig
from app.hand import HandResult
from app.match import MatchResult, run_match


def _cfg(**kwargs: int) -> GameConfig:
    defaults = dict(
        starting_stack=100,
        ante=1,
        min_raise=1,
        max_raise=10,
        max_rounds_per_match=20,
        card_min=1,
        card_max=10,
    )
    defaults.update(kwargs)
    return GameConfig(**defaults)


class _RepeatDealRng(random.Random):
    """Cycles ``(off0, off1)`` for successive ``randrange(span)`` calls (per hand)."""

    def __init__(self, off0: int, off1: int, span: int) -> None:
        super().__init__(0)
        self._span = span
        self._pair = (off0, off1)
        self._i = 0

    def randrange(self, n: int) -> int:
        assert n == self._span
        v = self._pair[self._i % 2]
        self._i += 1
        return v


def _strategies(seat0: list[Action], seat1: list[Action]):
    q0 = deque(seat0)
    q1 = deque(seat1)

    def s0(_rng: random.Random, _v: object) -> Action:
        return q0.popleft()

    def s1(_rng: random.Random, _v: object) -> Action:
        return q1.popleft()

    return s0, s1


def test_max_hands_stops_after_configured_hands() -> None:
    cfg = _cfg(max_rounds_per_match=3, starting_stack=50)
    span = cfg.card_max - cfg.card_min + 1
    rng = _RepeatDealRng(0, 0, span)
    # Repeated check-check ties preserve stacks (split pot returns antes).
    actions = [Action.check(), Action.check()]
    s0, s1 = _strategies(actions * 10, actions * 10)
    r = run_match(cfg, rng, s0, s1)
    assert isinstance(r, MatchResult)
    assert r.reason == "max_hands"
    assert r.hands_played == 3
    assert r.final_stacks == (50, 50)
    assert r.winner is None


def test_bankruptcy_when_opponent_cannot_ante() -> None:
    cfg = _cfg(
        starting_stack=10,
        ante=1,
        min_raise=1,
        max_raise=5,
        max_rounds_per_match=50,
    )
    span = cfg.card_max - cfg.card_min + 1
    # Seat 0 always wins showdown; seat 1 bleeds one dollar net per hand.
    rng = _RepeatDealRng(cfg.card_max - cfg.card_min, 0, span)
    actions = [Action.check(), Action.check()]
    s0, s1 = _strategies(actions * 60, actions * 60)
    init = cfg.starting_stack
    r = run_match(cfg, rng, s0, s1)
    assert r.reason == "bankruptcy"
    assert r.winner == 0
    assert r.final_stacks[1] < cfg.ante
    assert sum(r.final_stacks) == 2 * init
    assert r.hands_played == init


def test_alternating_first_to_act_each_hand() -> None:
    cfg = _cfg(max_rounds_per_match=4, starting_stack=20)
    dummy = HandResult(
        winner=0,
        reason="fold",
        final_stacks=(20, 20),
        cards=(1, 1),
        first_to_act=0,
    )
    with patch("app.match.play_hand", return_value=dummy) as mock_ph:
        run_match(cfg, random.Random(0), lambda r, v: Action.check(), lambda r, v: Action.check())

    first_args = [c.args[3] for c in mock_ph.call_args_list]
    assert first_args == [0, 1, 0, 1]


def test_run_match_calls_optional_hand_hooks() -> None:
    cfg = _cfg(max_rounds_per_match=2)
    span = cfg.card_max - cfg.card_min + 1
    rng = _RepeatDealRng(0, 0, span)
    actions = [Action.check(), Action.check()]
    s0, s1 = _strategies(actions * 10, actions * 10)
    before: list[tuple[int, tuple[int, int], int]] = []
    after: list[HandResult] = []

    def _b(h: int, st: tuple[int, int], ft: int) -> None:
        before.append((h, st, ft))

    def _a(hr: HandResult) -> None:
        after.append(hr)

    r = run_match(cfg, rng, s0, s1, before_each_hand=_b, after_each_hand=_a)
    assert r.reason == "max_hands"
    assert [x[0] for x in before] == [1, 2]
    assert [x[2] for x in before] == [0, 1]
    assert len(after) == 2


def test_max_hands_winner_by_stack_tie_is_none() -> None:
    cfg = _cfg(max_rounds_per_match=2, starting_stack=30)
    dummy = HandResult(
        winner=0,
        reason="fold",
        final_stacks=(29, 31),
        cards=(1, 1),
        first_to_act=0,
    )
    dummy2 = HandResult(
        winner=1,
        reason="fold",
        final_stacks=(30, 30),
        cards=(1, 1),
        first_to_act=1,
    )
    with patch("app.match.play_hand", side_effect=[dummy, dummy2]):
        r = run_match(
            cfg,
            random.Random(0),
            lambda r, v: Action.check(),
            lambda r, v: Action.check(),
        )
    assert r.reason == "max_hands"
    assert r.final_stacks == (30, 30)
    assert r.winner is None
    assert r.hands_played == 2
