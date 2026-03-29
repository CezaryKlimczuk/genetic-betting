"""T4: single-hand FSM, refunds, split pot, conservation."""

from __future__ import annotations

import random
from collections import deque

import pytest

from app.actions import Action
from app.config import GameConfig
from app.hand import HandResult, RaiseTruncationNotice, _award_split_pot, play_hand


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


class _DealRng(random.Random):
    """``randrange(span)`` returns fixed offsets for two hole cards."""

    def __init__(self, off0: int, off1: int, span: int) -> None:
        super().__init__(0)
        self._span = span
        self._q: deque[int] = deque([off0, off1])

    def randrange(self, n: int) -> int:
        assert n == self._span
        return self._q.popleft()


def _strategies(
    seat0: list[Action], seat1: list[Action]
):
    q0 = deque(seat0)
    q1 = deque(seat1)

    def s0(_rng: random.Random, _v: object) -> Action:
        return q0.popleft()

    def s1(_rng: random.Random, _v: object) -> Action:
        return q1.popleft()

    return s0, s1


def _conserved(initial: tuple[int, int], result: HandResult) -> bool:
    return sum(initial) == sum(result.final_stacks)


def test_p1_raise_p2_fold_winner_takes_full_pot() -> None:
    cfg = _cfg()
    span = cfg.card_max - cfg.card_min + 1
    rng = _DealRng(4, 2, span)
    stacks = (50, 50)
    total = sum(stacks)
    s0, s1 = _strategies([Action.raise_(5)], [Action.fold()])
    r = play_hand(cfg, rng, stacks, first_to_act=0, strategy0=s0, strategy1=s1)
    assert r.winner == 0
    assert r.reason == "fold"
    assert r.cards == (cfg.card_min + 4, cfg.card_min + 2)
    assert r.final_stacks[0] == stacks[0] - cfg.ante - 5 + (2 * cfg.ante + 5)
    assert r.final_stacks[1] == stacks[1] - cfg.ante
    assert _conserved(stacks, r)
    assert total == sum(r.final_stacks)


def test_p1_raise_p2_call_showdown_higher_card_wins() -> None:
    cfg = _cfg()
    span = cfg.card_max - cfg.card_min + 1
    rng = _DealRng(0, 5, span)
    stacks = (40, 40)
    s0, s1 = _strategies([Action.raise_(3)], [Action.call()])
    r = play_hand(cfg, rng, stacks, first_to_act=0, strategy0=s0, strategy1=s1)
    assert r.reason == "showdown"
    assert r.winner == 1
    assert _conserved(stacks, r)


def test_p1_check_p2_check_showdown() -> None:
    cfg = _cfg()
    span = cfg.card_max - cfg.card_min + 1
    rng = _DealRng(8, 1, span)
    stacks = (20, 20)
    s0, s1 = _strategies([Action.check()], [Action.check()])
    r = play_hand(cfg, rng, stacks, first_to_act=0, strategy0=s0, strategy1=s1)
    assert r.reason == "showdown"
    assert r.winner == 0
    assert _conserved(stacks, r)


def test_p1_check_p2_raise_p1_fold() -> None:
    cfg = _cfg()
    span = cfg.card_max - cfg.card_min + 1
    rng = _DealRng(0, 0, span)
    stacks = (30, 30)
    s0, s1 = _strategies([Action.check(), Action.fold()], [Action.raise_(4)])
    r = play_hand(cfg, rng, stacks, first_to_act=0, strategy0=s0, strategy1=s1)
    assert r.winner == 1
    assert r.reason == "fold"
    assert _conserved(stacks, r)


def test_p1_check_p2_raise_p1_call_showdown() -> None:
    cfg = _cfg()
    span = cfg.card_max - cfg.card_min + 1
    rng = _DealRng(2, 7, span)
    stacks = (50, 50)
    s0, s1 = _strategies([Action.check(), Action.call()], [Action.raise_(2)])
    r = play_hand(cfg, rng, stacks, first_to_act=0, strategy0=s0, strategy1=s1)
    assert r.reason == "showdown"
    assert r.winner == 1
    assert _conserved(stacks, r)


def test_showdown_tie_split_even_pot() -> None:
    cfg = _cfg()
    span = cfg.card_max - cfg.card_min + 1
    rng = _DealRng(3, 3, span)
    stacks = (25, 25)
    s0, s1 = _strategies([Action.check()], [Action.check()])
    r = play_hand(cfg, rng, stacks, first_to_act=0, strategy0=s0, strategy1=s1)
    assert r.reason == "showdown_tie"
    assert r.winner is None
    assert r.final_stacks[0] == r.final_stacks[1]
    assert _conserved(stacks, r)


def test_award_split_pot_halves_even_showdown_pot() -> None:
    """Showdown tie pots are even; each seat gets ``pot // 2`` (see ``hand``)."""
    st = [100, 100]
    _award_split_pot(24, st)
    assert st == [112, 112]


def test_p2_raise_truncated_when_p1_broke_showdown_no_p1_decision() -> None:
    """Facing player has $0 after ante; oversized raise is refunded → showdown."""
    cfg = _cfg(ante=10, min_raise=1, max_raise=10)
    span = cfg.card_max - cfg.card_min + 1
    rng = _DealRng(5, 2, span)
    stacks = (10, 20)
    total = sum(stacks)
    s0, s1 = _strategies([Action.check()], [Action.raise_(5)])
    r = play_hand(cfg, rng, stacks, first_to_act=0, strategy0=s0, strategy1=s1)
    assert r.reason in ("showdown", "showdown_tie")
    assert total == sum(r.final_stacks)


def test_p1_raise_truncated_when_p2_stack_smaller() -> None:
    cfg = _cfg(ante=2, min_raise=1, max_raise=20)
    span = cfg.card_max - cfg.card_min + 1
    rng = _DealRng(0, 1, span)
    stacks = (50, 12)
    total = sum(stacks)
    s0, s1 = _strategies([Action.raise_(15)], [Action.call()])
    r = play_hand(cfg, rng, stacks, first_to_act=0, strategy0=s0, strategy1=s1)
    assert r.reason == "showdown"
    assert r.winner == 1
    assert total == sum(r.final_stacks)


def test_on_raise_truncated_callback() -> None:
    notes: list[RaiseTruncationNotice] = []

    def record(n: RaiseTruncationNotice) -> None:
        notes.append(n)

    cfg = _cfg(ante=5, min_raise=1, max_raise=20)
    span = cfg.card_max - cfg.card_min + 1
    rng = _DealRng(0, 1, span)
    stacks = (15, 50)
    s0, s1 = _strategies([Action.check(), Action.call()], [Action.raise_(15)])
    play_hand(
        cfg,
        rng,
        stacks,
        first_to_act=0,
        strategy0=s0,
        strategy1=s1,
        on_raise_truncated=record,
    )
    assert len(notes) == 1
    assert notes[0].raiser_seat == 1
    assert notes[0].responder_seat == 0
    assert notes[0].requested_extra == 15
    assert notes[0].effective_extra == 10


def test_p2_raise_truncated_to_p1_stack_p1_can_call() -> None:
    cfg = _cfg(ante=5, min_raise=1, max_raise=20)
    span = cfg.card_max - cfg.card_min + 1
    rng = _DealRng(0, 1, span)
    stacks = (15, 50)
    total = sum(stacks)
    s0, s1 = _strategies([Action.check(), Action.call()], [Action.raise_(15)])
    r = play_hand(cfg, rng, stacks, first_to_act=0, strategy0=s0, strategy1=s1)
    assert r.reason == "showdown"
    assert r.winner == 1
    assert total == sum(r.final_stacks)


def test_all_in_short_call_refund_then_showdown() -> None:
    cfg = _cfg(ante=2, min_raise=1, max_raise=20)
    span = cfg.card_max - cfg.card_min + 1
    rng = _DealRng(0, 0, span)
    stacks = (12, 8)
    total = sum(stacks)
    s0, s1 = _strategies([Action.raise_(10)], [Action.call()])
    r = play_hand(cfg, rng, stacks, first_to_act=0, strategy0=s0, strategy1=s1)
    assert r.reason == "showdown_tie"
    assert r.winner is None
    assert total == sum(r.final_stacks)


def test_first_to_act_seat1_mapping() -> None:
    cfg = _cfg()
    span = cfg.card_max - cfg.card_min + 1
    rng = _DealRng(0, 0, span)
    stacks = (40, 40)
    s0, s1 = _strategies([Action.fold()], [Action.raise_(2)])
    r = play_hand(cfg, rng, stacks, first_to_act=1, strategy0=s0, strategy1=s1)
    assert r.winner == 1
    assert r.reason == "fold"
    assert _conserved(stacks, r)


def test_p1_fold_opens_pot_to_p2() -> None:
    cfg = _cfg()
    span = cfg.card_max - cfg.card_min + 1
    rng = _DealRng(0, 0, span)
    stacks = (15, 15)
    s0, s1 = _strategies([Action.fold()], [])
    r = play_hand(cfg, rng, stacks, first_to_act=0, strategy0=s0, strategy1=s1)
    assert r.winner == 1
    assert r.final_stacks[0] == stacks[0] - cfg.ante
    assert r.final_stacks[1] == stacks[1] - cfg.ante + 2 * cfg.ante
    assert _conserved(stacks, r)


def test_illegal_call_first_actor_raises() -> None:
    cfg = _cfg()
    span = cfg.card_max - cfg.card_min + 1
    rng = _DealRng(0, 0, span)

    def bad(_r: random.Random, _v: object) -> Action:
        return Action.call()

    with pytest.raises(ValueError, match="Illegal action"):
        play_hand(
            cfg,
            rng,
            (20, 20),
            first_to_act=0,
            strategy0=bad,
            strategy1=bad,
        )


def test_stacks_below_ante_rejected() -> None:
    cfg = _cfg()
    rng = random.Random(0)
    s0, s1 = _strategies([], [])

    with pytest.raises(ValueError, match="at least ante"):
        play_hand(cfg, rng, (0, 10), 0, s0, s1)
