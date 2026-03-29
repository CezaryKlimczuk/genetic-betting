"""Tests for YAML game config loading and validation."""

from __future__ import annotations

import textwrap
from pathlib import Path

import pytest
import yaml

from app.config import GameConfig, load_game_config


def _repo_root() -> Path:
    return Path(__file__).resolve().parent.parent


def test_load_example_yaml() -> None:
    path = _repo_root() / "config" / "game.example.yaml"
    cfg = load_game_config(path)
    assert isinstance(cfg, GameConfig)
    assert cfg.starting_stack == 100
    assert cfg.ante == 5
    assert cfg.min_raise == 5
    assert cfg.max_raise == 25
    assert cfg.max_rounds_per_match == 500
    assert cfg.card_min == 1
    assert cfg.card_max == 10


def test_invalid_yaml_raises(tmp_path: Path) -> None:
    bad = tmp_path / "bad.yaml"
    bad.write_text("not: valid: yaml: [[", encoding="utf-8")
    with pytest.raises(ValueError, match="Invalid YAML"):
        load_game_config(bad)


def test_empty_yaml_raises(tmp_path: Path) -> None:
    empty = tmp_path / "empty.yaml"
    empty.write_text("", encoding="utf-8")
    with pytest.raises(ValueError, match="empty"):
        load_game_config(empty)


def test_null_yaml_raises(tmp_path: Path) -> None:
    f = tmp_path / "null.yaml"
    f.write_text("null\n", encoding="utf-8")
    with pytest.raises(ValueError, match="null"):
        load_game_config(f)


def test_non_mapping_root_raises(tmp_path: Path) -> None:
    f = tmp_path / "list.yaml"
    f.write_text("- a\n", encoding="utf-8")
    with pytest.raises(ValueError, match="mapping"):
        load_game_config(f)


def test_missing_key_raises(tmp_path: Path) -> None:
    f = tmp_path / "partial.yaml"
    f.write_text(
        yaml.dump({"starting_stack": 10, "ante": 1}),
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="Missing config keys"):
        load_game_config(f)


def test_unknown_key_raises(tmp_path: Path) -> None:
    f = tmp_path / "extra.yaml"
    base = {
        "starting_stack": 100,
        "ante": 5,
        "min_raise": 5,
        "max_raise": 25,
        "max_rounds_per_match": 10,
        "card_min": 1,
        "card_max": 10,
        "extra_field": 1,
    }
    f.write_text(yaml.dump(base), encoding="utf-8")
    with pytest.raises(ValueError, match="Unknown config keys"):
        load_game_config(f)


def _valid_base() -> dict[str, int]:
    return {
        "starting_stack": 100,
        "ante": 5,
        "min_raise": 5,
        "max_raise": 25,
        "max_rounds_per_match": 10,
        "card_min": 1,
        "card_max": 10,
    }


def test_ante_non_positive_raises(tmp_path: Path) -> None:
    for ante in (0, -1):
        f = tmp_path / f"ante_{ante}.yaml"
        data = {**_valid_base(), "ante": ante}
        f.write_text(yaml.dump(data), encoding="utf-8")
        with pytest.raises(ValueError, match="ante must be positive"):
            load_game_config(f)


def test_starting_stack_below_ante_raises(tmp_path: Path) -> None:
    f = tmp_path / "short.yaml"
    data = {**_valid_base(), "starting_stack": 4, "ante": 5}
    f.write_text(yaml.dump(data), encoding="utf-8")
    with pytest.raises(ValueError, match="starting_stack"):
        load_game_config(f)


def test_min_raise_gt_max_raises(tmp_path: Path) -> None:
    f = tmp_path / "raise.yaml"
    data = {**_valid_base(), "min_raise": 10, "max_raise": 5}
    f.write_text(yaml.dump(data), encoding="utf-8")
    with pytest.raises(ValueError, match="min_raise"):
        load_game_config(f)


def test_min_raise_below_one_raises(tmp_path: Path) -> None:
    f = tmp_path / "min0.yaml"
    data = {**_valid_base(), "min_raise": 0, "max_raise": 5}
    f.write_text(yaml.dump(data), encoding="utf-8")
    with pytest.raises(ValueError, match="min_raise must be at least"):
        load_game_config(f)


def test_max_rounds_below_one_raises(tmp_path: Path) -> None:
    f = tmp_path / "rounds.yaml"
    data = {**_valid_base(), "max_rounds_per_match": 0}
    f.write_text(yaml.dump(data), encoding="utf-8")
    with pytest.raises(ValueError, match="max_rounds_per_match"):
        load_game_config(f)


def test_card_range_invalid_raises(tmp_path: Path) -> None:
    f = tmp_path / "cards.yaml"
    data = {**_valid_base(), "card_min": 5, "card_max": 2}
    f.write_text(yaml.dump(data), encoding="utf-8")
    with pytest.raises(ValueError, match="card_min"):
        load_game_config(f)


def test_card_below_one_raises(tmp_path: Path) -> None:
    f = tmp_path / "card0.yaml"
    data = {**_valid_base(), "card_min": 0, "card_max": 5}
    f.write_text(yaml.dump(data), encoding="utf-8")
    with pytest.raises(ValueError, match="card_min and card_max"):
        load_game_config(f)


def test_non_integer_field_raises(tmp_path: Path) -> None:
    f = tmp_path / "float.yaml"
    doc = textwrap.dedent(
        """
        starting_stack: 100
        ante: 5
        min_raise: 5
        max_raise: 25
        max_rounds_per_match: 10
        card_min: 1
        card_max: 3.5
        """
    )
    f.write_text(doc, encoding="utf-8")
    with pytest.raises(ValueError, match="integer"):
        load_game_config(f)


def test_bool_field_rejected(tmp_path: Path) -> None:
    f = tmp_path / "bool.yaml"
    data = {**_valid_base(), "ante": True}
    f.write_text(yaml.dump(data), encoding="utf-8")
    with pytest.raises(ValueError, match="boolean"):
        load_game_config(f)
