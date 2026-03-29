"""CLI prompts and argument parsing."""

from __future__ import annotations

import random
from io import StringIO

import pytest

from app.actions import Action
from app.cli import build_parser, prompt_action_from_view
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


def test_prompt_action_from_view_checks_on_second_choice(monkeypatch: pytest.MonkeyPatch) -> None:
    cfg = _small_cfg()
    view = _p1_view(cfg)
    monkeypatch.setattr("builtins.input", lambda *_: "2")
    out = StringIO()
    act = prompt_action_from_view(random.Random(0), view, file=out)
    assert act == Action.check()
    assert "Your card: 5" in out.getvalue()
    assert str(cfg.card_max) in out.getvalue()


def test_build_parser_default_config_path() -> None:
    p = build_parser()
    args = p.parse_args([])
    assert args.config.parts[-2:] == ("config", "game.example.yaml")


def test_build_parser_accepts_seed() -> None:
    p = build_parser()
    args = p.parse_args(["--seed", "42"])
    assert args.seed == 42
