"""Per-seat view passed to strategies (no hidden opponent card before showdown)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

import math

from app.config import GameConfig, strict_int

_DECISION_PHASES = frozenset(
    ("p1_open", "p2_facing_raise", "p2_after_check", "p1_facing_raise")
)
DecisionPhase = Literal["p1_open", "p2_facing_raise", "p2_after_check", "p1_facing_raise"]
"""Betting FSM node for the current decision (set by :func:`app.hand.play_hand`)."""

# Stable alphabetical order for :func:`as_observation` phase one-hot (do not reorder).
OBSERVATION_PHASE_ORDER: tuple[DecisionPhase, ...] = (
    "p1_facing_raise",
    "p1_open",
    "p2_after_check",
    "p2_facing_raise",
)

OBSERVATION_VECTOR_LEN = 17
"""Length of :attr:`Observation.values` from :func:`as_observation`."""


@dataclass(frozen=True, slots=True)
class Observation:
    """Float feature vector derived from an :class:`ActorView` for batch encoders.

    Not used by the engine; layout is best-effort and may evolve—pin versions for
    serious training runs. See module constants for field ordering.
    """

    values: tuple[float, ...]

    def __post_init__(self) -> None:
        if len(self.values) != OBSERVATION_VECTOR_LEN:
            raise ValueError(
                f"Observation.values must have length {OBSERVATION_VECTOR_LEN}, "
                f"got {len(self.values)}."
            )


def as_observation(view: ActorView) -> Observation:
    """Map a view to a fixed-length float tuple for GA / neural encoders.

    Values are mostly in ``[0, 1]``; legal flags use ``0.0``/``1.0``.
    Money fields use ``denom = max(wallet_self + wallet_opponent + pot, 1)``.
    Hidden opponent cards use ``0.0`` for the normalized rank and ``0.0`` for the
    known flag; revealed cards use normalized rank and ``1.0``. Seat is omitted;
    ``decision_phase`` and ego-centric wallets encode role.

    Layout (indices ``0 .. OBSERVATION_VECTOR_LEN - 1``):

    - ``0`` — own card normalized by ``[card_min, card_max]``
    - ``1`` — opponent card normalized, or ``0`` if unknown
    - ``2`` — ``1`` if opponent card is known, else ``0``
    - ``3:7`` — ``wallet_self``, ``wallet_opponent``, ``pot``, ``amount_to_call`` / denom
    - ``7:11`` — ``can_check``, ``can_fold``, ``can_call``, ``can_raise`` as floats
    - ``11:13`` — ``raise_amount_min/max`` / denom if ``can_raise``, else ``0``, ``0``
    - ``13:17`` — ``decision_phase`` one-hot in :data:`OBSERVATION_PHASE_ORDER`

    Args:
        view: Actor-visible state (typically from :func:`app.hand.play_hand`).

    Returns:
        Frozen :class:`Observation` wrapping the feature tuple.
    """
    cmin, cmax = view.card_min, view.card_max
    span_cards = max(cmax - cmin, 1)
    own_n = (view.own_card - cmin) / span_cards

    if view.opponent_card is None:
        opp_n = 0.0
        opp_known = 0.0
    else:
        opp_n = (view.opponent_card - cmin) / span_cards
        opp_known = 1.0

    total_chips = view.wallet_self + view.wallet_opponent + view.pot
    denom = max(total_chips, 1)
    w_s = view.wallet_self / denom
    w_o = view.wallet_opponent / denom
    pot_n = view.pot / denom
    call_n = view.amount_to_call / denom

    if view.can_raise:
        rmin = view.raise_amount_min
        rmax = view.raise_amount_max
        if rmin is None or rmax is None:
            raise ValueError("can_raise requires raise_amount_min and raise_amount_max.")
        rmin_n = rmin / denom
        rmax_n = rmax / denom
    else:
        rmin_n = 0.0
        rmax_n = 0.0

    phase_bits = tuple(
        1.0 if view.decision_phase is ph else 0.0 for ph in OBSERVATION_PHASE_ORDER
    )

    vec = (
        own_n,
        opp_n,
        opp_known,
        w_s,
        w_o,
        pot_n,
        call_n,
        float(view.can_check),
        float(view.can_fold),
        float(view.can_call),
        float(view.can_raise),
        rmin_n,
        rmax_n,
    ) + phase_bits

    expected = OBSERVATION_VECTOR_LEN
    if len(vec) != expected:
        msg = f"internal observation layout error: len {len(vec)} != {expected}"
        raise RuntimeError(msg)

    # Guard against NaNs so encoders fail loudly on bad fixtures.
    for x in vec:
        if isinstance(x, float) and not math.isfinite(x):
            raise ValueError(f"non-finite observation component: {x!r}")

    return Observation(values=vec)


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
