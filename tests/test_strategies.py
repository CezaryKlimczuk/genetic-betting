"""T6: scripted queue strategies, random legal strategy, match integration."""

from __future__ import annotations

import random
from typing import Any

import pytest

from app.actions import Action, ActionKind
from app.actor_view import ActorView
from app.config import GameConfig
from app.match import MatchResult, run_match
import app.legal_actions as legal_actions_mod
import app.strategies as strategies_mod
from app.legal_actions import legal_actions_for_view
from app.strategies import RandomLegalStrategy, ScriptedStrategy


def test_strategies_reexports_legal_actions_for_view() -> None:
    assert strategies_mod.legal_actions_for_view is legal_actions_mod.legal_actions_for_view

_VIEW_CFG = GameConfig(
    starting_stack=50,
    ante=1,
    min_raise=1,
    max_raise=10,
    max_rounds_per_match=20,
    card_min=1,
    card_max=10,
)


def _example_view(**kwargs: Any) -> ActorView:
    defaults: dict[str, Any] = dict(
        seat=1,
        own_card=5,
        opponent_card=None,
        wallet_self=50,
        wallet_opponent=50,
        pot=2,
        amount_to_call=0,
        can_check=True,
        can_fold=True,
        can_call=False,
        can_raise=True,
        raise_amount_min=1,
        raise_amount_max=3,
        decision_phase="p1_open",
    )
    defaults.update(kwargs)
    return ActorView.from_config(_VIEW_CFG, **defaults)


def test_legal_actions_after_check_line_excludes_fold_when_can_fold_false() -> None:
    view = _example_view(
        can_fold=False, seat=1, decision_phase="p2_after_check"
    )
    legal = legal_actions_for_view(view)
    assert all(a.kind != ActionKind.FOLD for a in legal)
    assert Action.check() in legal
    assert Action.raise_(1) in legal
    assert Action.raise_(3) in legal


_TABLE_CFG = GameConfig(
    starting_stack=100,
    ante=2,
    min_raise=2,
    max_raise=5,
    max_rounds_per_match=10,
    card_min=1,
    card_max=10,
)


def _table_view(**kwargs: Any) -> ActorView:
    base: dict[str, Any] = dict(
        seat=0,
        own_card=3,
        opponent_card=None,
        wallet_self=40,
        wallet_opponent=40,
        pot=4,
        amount_to_call=0,
        can_check=True,
        can_fold=True,
        can_call=False,
        can_raise=False,
        raise_amount_min=None,
        raise_amount_max=None,
        decision_phase="p1_open",
    )
    base.update(kwargs)
    return ActorView.from_config(_TABLE_CFG, **base)


@pytest.mark.parametrize(
    ("name", "view_kwargs", "expected"),
    [
        (
            "p1_open_with_raises",
            dict(
                seat=0,
                wallet_self=50,
                amount_to_call=0,
                can_check=True,
                can_fold=True,
                can_call=False,
                can_raise=True,
                raise_amount_min=2,
                raise_amount_max=5,
                decision_phase="p1_open",
            ),
            [
                Action.fold(),
                Action.check(),
                *[Action.raise_(a) for a in range(2, 6)],
            ],
        ),
        (
            "p1_open_no_raise_stack_below_min",
            dict(
                seat=1,
                wallet_self=1,
                amount_to_call=0,
                can_check=True,
                can_fold=True,
                can_call=False,
                can_raise=False,
                raise_amount_min=None,
                raise_amount_max=None,
                decision_phase="p1_open",
            ),
            [Action.fold(), Action.check()],
        ),
        (
            "facing_raise_fold_call",
            dict(
                seat=1,
                amount_to_call=7,
                can_check=False,
                can_fold=True,
                can_call=True,
                can_raise=False,
                raise_amount_min=None,
                raise_amount_max=None,
                decision_phase="p2_facing_raise",
            ),
            [Action.fold(), Action.call()],
        ),
        (
            "facing_raise_fold_only_zero_wallet",
            dict(
                seat=0,
                wallet_self=0,
                amount_to_call=4,
                can_check=False,
                can_fold=True,
                can_call=False,
                can_raise=False,
                raise_amount_min=None,
                raise_amount_max=None,
                decision_phase="p1_facing_raise",
            ),
            [Action.fold()],
        ),
        (
            "p2_after_p1_check_check_and_raises",
            dict(
                seat=1,
                amount_to_call=0,
                can_check=True,
                can_fold=False,
                can_call=False,
                can_raise=True,
                raise_amount_min=2,
                raise_amount_max=4,
                decision_phase="p2_after_check",
            ),
            [
                Action.check(),
                Action.raise_(2),
                Action.raise_(3),
                Action.raise_(4),
            ],
        ),
    ],
)
def test_legal_actions_characterization_table(
    name: str, view_kwargs: dict[str, Any], expected: list[Action]
) -> None:
    _ = name
    assert legal_actions_for_view(_table_view(**view_kwargs)) == expected


def test_scripted_strategy_drains_in_order() -> None:
    s = ScriptedStrategy([Action.check(), Action.fold(), Action.call()])
    assert s(random.Random(0), _example_view()) == Action.check()
    assert s(random.Random(0), _example_view()) == Action.fold()
    assert s(random.Random(0), _example_view()) == Action.call()


def test_scripted_strategy_exhausted_raises() -> None:
    s = ScriptedStrategy([Action.check()])
    s(random.Random(0), _example_view())
    with pytest.raises(RuntimeError, match="no remaining"):
        s(random.Random(0), _example_view())


def test_match_integration_scripted_strategies_deterministic() -> None:
    cfg = GameConfig(
        starting_stack=50,
        ante=1,
        min_raise=1,
        max_raise=10,
        max_rounds_per_match=3,
        card_min=1,
        card_max=10,
    )
    span = cfg.card_max - cfg.card_min + 1

    class _RepeatDealRng(random.Random):
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

    rng = _RepeatDealRng(0, 0, span)
    per_hand = (Action.check(), Action.check())
    s0 = ScriptedStrategy(per_hand * 10)
    s1 = ScriptedStrategy(per_hand * 10)
    r = run_match(cfg, rng, s0, s1)
    assert isinstance(r, MatchResult)
    assert r.reason == "max_hands"
    assert r.hands_played == 3
    assert r.final_stacks == (50, 50)
    assert r.winner is None


def test_match_random_legal_strategy_completes() -> None:
    cfg = GameConfig(
        starting_stack=30,
        ante=1,
        min_raise=1,
        max_raise=5,
        max_rounds_per_match=25,
        card_min=1,
        card_max=6,
    )
    rng = random.Random(42)
    s0 = RandomLegalStrategy()
    s1 = RandomLegalStrategy()
    r = run_match(cfg, rng, s0, s1)
    assert r.hands_played >= 1
    assert r.hands_played <= cfg.max_rounds_per_match
    assert sum(r.final_stacks) == 2 * cfg.starting_stack
