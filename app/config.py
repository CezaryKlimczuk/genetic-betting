"""Load and validate game configuration from YAML."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

_CONFIG_KEYS = frozenset(
    {
        "starting_stack",
        "ante",
        "min_raise",
        "max_raise",
        "max_rounds_per_match",
        "card_min",
        "card_max",
    }
)


@dataclass(frozen=True, slots=True)
class GameConfig:
    """Immutable game parameters loaded from YAML (amounts are int dollars)."""

    starting_stack: int
    ante: int
    min_raise: int
    max_raise: int
    max_rounds_per_match: int
    card_min: int
    card_max: int


def _strict_int(name: str, value: Any) -> int:
    if type(value) is bool:
        raise ValueError(f"{name} must be an integer, not a boolean.")
    if type(value) is not int:
        raise ValueError(f"{name} must be an integer, got {type(value).__name__}.")
    return value


def _validate_config_fields(data: dict[str, Any]) -> GameConfig:
    unknown = set(data) - _CONFIG_KEYS
    if unknown:
        raise ValueError(f"Unknown config keys: {sorted(unknown)}")

    missing = _CONFIG_KEYS - set(data)
    if missing:
        raise ValueError(f"Missing config keys: {sorted(missing)}")

    starting_stack = _strict_int("starting_stack", data["starting_stack"])
    ante = _strict_int("ante", data["ante"])
    min_raise = _strict_int("min_raise", data["min_raise"])
    max_raise = _strict_int("max_raise", data["max_raise"])
    max_rounds = _strict_int("max_rounds_per_match", data["max_rounds_per_match"])
    card_min = _strict_int("card_min", data["card_min"])
    card_max = _strict_int("card_max", data["card_max"])

    if ante <= 0:
        raise ValueError("ante must be positive.")
    if starting_stack < ante:
        raise ValueError("starting_stack must be at least ante (each player posts ante).")
    if min_raise < 1:
        raise ValueError("min_raise must be at least 1 dollar.")
    if min_raise > max_raise:
        raise ValueError("min_raise must be less than or equal to max_raise.")
    if max_rounds < 1:
        raise ValueError("max_rounds_per_match must be at least 1.")
    if card_min < 1 or card_max < 1:
        raise ValueError("card_min and card_max must be at least 1.")
    if card_min > card_max:
        raise ValueError("card_min must be less than or equal to card_max.")

    return GameConfig(
        starting_stack=starting_stack,
        ante=ante,
        min_raise=min_raise,
        max_raise=max_raise,
        max_rounds_per_match=max_rounds,
        card_min=card_min,
        card_max=card_max,
    )


def load_game_config(path: str | Path) -> GameConfig:
    """Load ``GameConfig`` from a YAML file and validate constraints.

    Args:
        path: Path to a YAML file containing exactly the documented keys.

    Returns:
        Validated ``GameConfig``.

    Raises:
        ValueError: If the file is missing keys, has unknown keys, invalid types,
            or fails validation rules.
        OSError: If the file cannot be read.
    """
    p = Path(path)
    text = p.read_text(encoding="utf-8")
    try:
        raw = yaml.safe_load(text)
    except yaml.YAMLError as exc:
        raise ValueError(f"Invalid YAML in {p}: {exc}") from exc

    if raw is None:
        raise ValueError(f"Config file {p} is empty or contains only null.")

    if not isinstance(raw, dict):
        raise ValueError(f"Config root must be a mapping, got {type(raw).__name__}.")

    # Normalize keys to str for validation (YAML may use str keys only).
    data = {str(k): v for k, v in raw.items()}
    return _validate_config_fields(data)
