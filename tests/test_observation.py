"""Encoding :class:`~app.actor_view.ActorView` for batch / GA encoders."""

from __future__ import annotations

import pytest

from app.actor_view import (
    OBSERVATION_PHASE_ORDER,
    OBSERVATION_VECTOR_LEN,
    ActorView,
    Observation,
    as_observation,
)
from app.config import GameConfig


def _cfg() -> GameConfig:
    return GameConfig(
        starting_stack=100,
        ante=1,
        min_raise=1,
        max_raise=10,
        max_rounds_per_match=10,
        card_min=1,
        card_max=10,
    )


def _base_view(**kwargs: object) -> ActorView:
    base: dict[str, object] = dict(
        seat=0,
        own_card=5,
        opponent_card=None,
        wallet_self=40,
        wallet_opponent=40,
        pot=20,
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
    return ActorView.from_config(_cfg(), **base)


def test_as_observation_length_and_observation_validation() -> None:
    v = _base_view()
    obs = as_observation(v)
    assert len(obs.values) == OBSERVATION_VECTOR_LEN
    with pytest.raises(ValueError, match="must have length"):
        Observation(values=(0.0,))


def test_phase_one_hot_ignores_seat() -> None:
    v0 = _base_view(seat=0, decision_phase="p2_after_check")
    v1 = _base_view(seat=1, decision_phase="p2_after_check")
    assert as_observation(v0).values == as_observation(v1).values

    facing = _base_view(seat=0, decision_phase="p1_facing_raise")
    phase_slice = as_observation(facing).values[13:17]
    assert sum(phase_slice) == pytest.approx(1.0)
    idx = OBSERVATION_PHASE_ORDER.index("p1_facing_raise")
    assert phase_slice[idx] == pytest.approx(1.0)


def test_money_features_sum_to_one() -> None:
    v = _base_view(wallet_self=30, wallet_opponent=50, pot=20)
    o = as_observation(v).values
    assert o[3] + o[4] + o[5] == pytest.approx(1.0)
    assert o[6] == pytest.approx(0.0)


def test_card_and_opponent_encoding() -> None:
    v_hidden = _base_view(own_card=1, opponent_card=None)
    h = as_observation(v_hidden).values
    assert h[0] == pytest.approx(0.0)
    assert h[1] == pytest.approx(0.0)
    assert h[2] == pytest.approx(0.0)

    v_high = _base_view(own_card=10)
    assert as_observation(v_high).values[0] == pytest.approx(1.0)

    v_show = _base_view(own_card=1, opponent_card=10)
    s = as_observation(v_show).values
    assert s[1] == pytest.approx(1.0)
    assert s[2] == pytest.approx(1.0)


def test_raise_slice_when_can_raise() -> None:
    v = _base_view(
        can_raise=True,
        raise_amount_min=2,
        raise_amount_max=8,
        wallet_self=40,
        wallet_opponent=40,
        pot=20,
    )
    o = as_observation(v).values
    denom = 100.0
    assert o[10] == pytest.approx(1.0)  # can_raise
    assert o[11] == pytest.approx(2.0 / denom)
    assert o[12] == pytest.approx(8.0 / denom)
