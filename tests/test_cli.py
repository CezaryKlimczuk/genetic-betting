"""CLI prompts and argument parsing."""

from __future__ import annotations

import random
from io import StringIO

import pytest

from app.actions import Action
from app.cli import build_parser, hotseat_action_completes_hand, prompt_action_from_view
from app.config import GameConfig
from app.actor_view import ActorView


def _small_cfg() -> GameConfig:
    return GameConfig(
        starting_stack=100,
        ante=5,
        min_raise=5,
        max_raise=15,
        max_rounds_per_match=10,
        card_min=1,
        card_max=10,
    )


def _p1_view(cfg: GameConfig) -> ActorView:
    return ActorView.from_config(
        cfg,
        seat=0,
        own_card=5,
        opponent_card=None,
        wallet_self=95,
        wallet_opponent=95,
        pot=10,
        amount_to_call=0,
        can_check=True,
        can_fold=True,
        can_call=False,
        can_raise=False,
        raise_amount_min=None,
        raise_amount_max=None,
    )


def test_hotseat_action_completes_hand_matches_fsm() -> None:
    cfg = _small_cfg()
    p1 = _p1_view(cfg)
    assert not hotseat_action_completes_hand(p1, Action.check())
    assert hotseat_action_completes_hand(p1, Action.fold())

    p2_check_back = ActorView.from_config(
        cfg,
        seat=1,
        own_card=7,
        opponent_card=None,
        wallet_self=95,
        wallet_opponent=95,
        pot=10,
        amount_to_call=0,
        can_check=True,
        can_fold=False,
        can_call=False,
        can_raise=True,
        raise_amount_min=5,
        raise_amount_max=10,
    )
    assert hotseat_action_completes_hand(p2_check_back, Action.check())
    assert not hotseat_action_completes_hand(p2_check_back, Action.raise_(5))

    facing = ActorView.from_config(
        cfg,
        seat=1,
        own_card=7,
        opponent_card=None,
        wallet_self=80,
        wallet_opponent=70,
        pot=25,
        amount_to_call=10,
        can_check=False,
        can_fold=True,
        can_call=True,
        can_raise=False,
        raise_amount_min=None,
        raise_amount_max=None,
    )
    assert hotseat_action_completes_hand(facing, Action.call())
    assert hotseat_action_completes_hand(facing, Action.fold())


def test_prompt_action_from_view_checks_on_second_choice(monkeypatch: pytest.MonkeyPatch) -> None:
    cfg = _small_cfg()
    view = _p1_view(cfg)
    monkeypatch.setattr("builtins.input", lambda *_: "2")
    out = StringIO()
    act = prompt_action_from_view(
        random.Random(0), view, cfg, file=out, submit_pause=False
    )
    assert act == Action.check()
    out_s = out.getvalue()
    assert "Your card: 5" in out_s
    assert str(cfg.card_max) in out_s
    assert "(NOT AVAILABLE)" in out_s
    assert "call (match" in out_s


def test_prompt_submission_shows_hand_results_when_hand_ends(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    cfg = _small_cfg()
    view = _p1_view(cfg)
    inputs = iter(["1", ""])
    monkeypatch.setattr("builtins.input", lambda *_: next(inputs))
    out = StringIO()
    act = prompt_action_from_view(
        random.Random(0), view, cfg, file=out, submit_pause=True
    )
    assert act == Action.fold()
    assert "hand results" in out.getvalue()


def test_prompt_submission_shows_pass_keyboard_when_hand_continues(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    cfg = _small_cfg()
    view = _p1_view(cfg)
    inputs = iter(["2", ""])
    monkeypatch.setattr("builtins.input", lambda *_: next(inputs))
    out = StringIO()
    act = prompt_action_from_view(
        random.Random(0), view, cfg, file=out, submit_pause=True
    )
    assert act == Action.check()
    out_s = out.getvalue()
    assert "Pass the keyboard" in out_s
    assert "hand results" not in out_s


def test_build_parser_default_config_path() -> None:
    p = build_parser()
    args = p.parse_args([])
    assert args.config.parts[-2:] == ("config", "game.example.yaml")


def test_build_parser_accepts_seed() -> None:
    p = build_parser()
    args = p.parse_args(["--seed", "42"])
    assert args.seed == 42
