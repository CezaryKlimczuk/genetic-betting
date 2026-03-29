"""Per-seat view passed to strategies (no hidden opponent card before showdown)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

from app.config import GameConfig, strict_int

_DECISION_PHASES = frozenset(
    ("p1_open", "p2_facing_raise", "p2_after_check", "p1_facing_raise")
)
DecisionPhase = Literal["p1_open", "p2_facing_raise", "p2_after_check", "p1_facing_raise"]
"""Betting FSM node for the current decision (set by :func:`app.hand.play_hand`)."""


@dataclass(frozen=True, slots=True)
class ActorView:
    """Information visible to one seat when choosing an action.

    Opponent hole card is omitted until showdown (``opponent_card`` is ``None``
    during hidden play). Amounts are int dollars.

    ``card_min`` and ``card_max`` must match the active ``GameConfig`` (inclusive
    legal card values). Prefer :meth:`from_config` so bounds stay aligned with
    the loaded rules.

    When ``can_raise`` is true, ``raise_amount_min`` and ``raise_amount_max`` are
    the inclusive legal **raise sizes** (extra dollars beyond the check line) for
    this decision, already intersected with stack limits. When false, both are
    ``None``.

    ``decision_phase`` records which betting node built this view (see
    :mod:`app.hand`); UI code can use it without re-deriving FSM state.
    """

    seat: int
    own_card: int
    opponent_card: int | None
    card_min: int
    card_max: int
    wallet_self: int
    wallet_opponent: int
    pot: int
    amount_to_call: int
    can_check: bool
    can_fold: bool
    can_call: bool
    can_raise: bool
    raise_amount_min: int | None
    raise_amount_max: int | None
    decision_phase: DecisionPhase

    @classmethod
    def from_config(cls, config: GameConfig, /, **kwargs: Any) -> ActorView:
        """Build a view; ``card_min`` / ``card_max`` are taken from ``config``."""
        return cls(card_min=config.card_min, card_max=config.card_max, **kwargs)

    def __post_init__(self) -> None:
        seat = strict_int("seat", self.seat)
        if seat not in (0, 1):
            raise ValueError("seat must be 0 or 1.")

        cmin = strict_int("card_min", self.card_min)
        cmax = strict_int("card_max", self.card_max)
        if cmin < 1 or cmax < 1:
            raise ValueError("card_min and card_max must be at least 1.")
        if cmin > cmax:
            raise ValueError("card_min must be less than or equal to card_max.")

        own = strict_int("own_card", self.own_card)
        if own < cmin or own > cmax:
            raise ValueError(
                f"own_card must be in [{cmin}, {cmax}], got {own}."
            )

        if self.opponent_card is not None:
            opp = strict_int("opponent_card", self.opponent_card)
            if opp < cmin or opp > cmax:
                raise ValueError(
                    f"opponent_card must be in [{cmin}, {cmax}] when set, got {opp}."
                )

        for name, value in (
            ("wallet_self", self.wallet_self),
            ("wallet_opponent", self.wallet_opponent),
            ("pot", self.pot),
            ("amount_to_call", self.amount_to_call),
        ):
            strict_int(name, value)
            if value < 0:
                raise ValueError(f"{name} must be non-negative.")
        if self.can_raise:
            if self.raise_amount_min is None or self.raise_amount_max is None:
                raise ValueError("raise bounds required when can_raise is true.")
            rmin = strict_int("raise_amount_min", self.raise_amount_min)
            rmax = strict_int("raise_amount_max", self.raise_amount_max)
            if rmin < 1:
                raise ValueError("raise_amount_min must be at least 1.")
            if rmin > rmax:
                raise ValueError("raise_amount_min must be <= raise_amount_max.")
        else:
            if self.raise_amount_min is not None or self.raise_amount_max is not None:
                raise ValueError("raise bounds must be None when can_raise is false.")

        if self.decision_phase not in _DECISION_PHASES:
            raise ValueError(
                f"decision_phase must be one of {sorted(_DECISION_PHASES)!r}, "
                f"got {self.decision_phase!r}."
            )
