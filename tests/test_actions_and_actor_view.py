"""T3: construct ``Action`` and ``ActorView`` without engine FSM imports."""

from __future__ import annotations

import pytest

from app.actions import Action, ActionKind
from app.actor_view import ActorView
from app.config import GameConfig


def _sample_config() -> GameConfig:
    return GameConfig(
        starting_stack=100,
        ante=1,
        min_raise=1,
        max_raise=10,
        max_rounds_per_match=10,
        card_min=1,
        card_max=10,
    )


def test_action_factories_and_kinds() -> None:
    c = Action.check()
    f = Action.fold()
    ca = Action.call()
    r = Action.raise_(5)

    assert c.kind is ActionKind.CHECK and c.amount_dollars is None
    assert f.kind is ActionKind.FOLD and f.amount_dollars is None
    assert ca.kind is ActionKind.CALL and ca.amount_dollars is None
    assert r.kind is ActionKind.RAISE and r.amount_dollars == 5


def test_action_raise_validation() -> None:
    with pytest.raises(ValueError, match="raise requires"):
        Action(kind=ActionKind.RAISE, amount_dollars=None)
    with pytest.raises(ValueError, match="at least 1"):
        Action(kind=ActionKind.RAISE, amount_dollars=0)
    with pytest.raises(ValueError, match="only valid for raise"):
        Action(kind=ActionKind.CHECK, amount_dollars=1)
    with pytest.raises(ValueError, match="must be an integer, not a boolean"):
        Action(kind=ActionKind.RAISE, amount_dollars=True)
    with pytest.raises(ValueError, match="must be an integer, got float"):
        Action(kind=ActionKind.RAISE, amount_dollars=3.0)


def test_action_equality_hashable() -> None:
    a = Action.raise_(3)
    b = Action.raise_(3)
    c = Action.raise_(4)
    assert a == b
    assert a != c
    assert hash(a) == hash(b)


def test_actor_view_from_config_and_showdown() -> None:
    cfg = _sample_config()
    v = ActorView.from_config(
        cfg,
        seat=1,
        own_card=7,
        opponent_card=None,
        wallet_self=90,
        wallet_opponent=88,
        pot=20,
        amount_to_call=0,
        can_check=True,
        can_fold=False,
        can_call=False,
        can_raise=True,
        raise_amount_min=2,
        raise_amount_max=10,
        decision_phase="p2_after_check",
    )
    assert v.card_min == cfg.card_min and v.card_max == cfg.card_max
    assert v.opponent_card is None

    at_showdown = ActorView.from_config(
        cfg,
        seat=1,
        own_card=4,
        opponent_card=9,
        wallet_self=50,
        wallet_opponent=50,
        pot=100,
        amount_to_call=0,
        can_check=False,
        can_fold=False,
        can_call=False,
        can_raise=False,
        raise_amount_min=None,
        raise_amount_max=None,
        decision_phase="p1_open",
    )
    assert at_showdown.opponent_card == 9


def test_actor_view_validation() -> None:
    base = dict(
        seat=0,
        own_card=5,
        opponent_card=None,
        card_min=1,
        card_max=10,
        wallet_self=10,
        wallet_opponent=10,
        pot=4,
        amount_to_call=0,
        can_check=True,
        can_fold=False,
        can_call=False,
        can_raise=False,
        raise_amount_min=None,
        raise_amount_max=None,
        decision_phase="p1_open",
    )
    with pytest.raises(ValueError, match="seat must be 0 or 1"):
        ActorView(**{**base, "seat": 2})
    with pytest.raises(ValueError, match="own_card must be in \\[1, 10\\]"):
        ActorView(**{**base, "own_card": 0})
    with pytest.raises(ValueError, match="opponent_card must be in"):
        ActorView(**{**base, "opponent_card": 0})
    with pytest.raises(ValueError, match="card_min must be less than or equal"):
        ActorView(**{**base, "card_min": 5, "card_max": 3})
    with pytest.raises(ValueError, match="wallet_self must be non-negative"):
        ActorView(**{**base, "wallet_self": -1})
    with pytest.raises(ValueError, match="raise bounds required"):
        ActorView(
            **{
                **base,
                "can_raise": True,
                "raise_amount_min": None,
                "raise_amount_max": 5,
            }
        )
    with pytest.raises(ValueError, match="raise bounds must be None"):
        ActorView(
            **{
                **base,
                "can_raise": False,
                "raise_amount_min": 1,
                "raise_amount_max": None,
            }
        )
    with pytest.raises(ValueError, match="raise_amount_min must be at least"):
        ActorView(
            **{
                **base,
                "can_raise": True,
                "raise_amount_min": 0,
                "raise_amount_max": 5,
            }
        )
    with pytest.raises(ValueError, match="raise_amount_min must be <="):
        ActorView(
            **{
                **base,
                "can_raise": True,
                "raise_amount_min": 5,
                "raise_amount_max": 2,
            }
        )
    with pytest.raises(ValueError, match="decision_phase must be one of"):
        ActorView(**{**base, "decision_phase": "showdown"})  # type: ignore[arg-type]
