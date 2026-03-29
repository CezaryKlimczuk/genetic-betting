"""Betting actions (immutable, engine-agnostic)."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from app.config import strict_int


class ActionKind(StrEnum):
    """Discriminator for ``Action``."""

    CHECK = "check"
    FOLD = "fold"
    CALL = "call"
    RAISE = "raise"


@dataclass(frozen=True, slots=True)
class Action:
    """A single betting choice (amounts are int dollars).

    ``amount_dollars`` is set only for ``RAISE``; it is the **additional** chips
    committed by the raise beyond what was already required to stay in the hand
    for this street (raise size in dollars).
    """

    kind: ActionKind
    amount_dollars: int | None = None

    def __post_init__(self) -> None:
        if self.kind is ActionKind.RAISE:
            if self.amount_dollars is None:
                raise ValueError("raise requires amount_dollars.")
            amount = strict_int("amount_dollars", self.amount_dollars)
            if amount < 1:
                raise ValueError("raise amount_dollars must be at least 1.")
        elif self.amount_dollars is not None:
            raise ValueError("amount_dollars is only valid for raise.")

    @classmethod
    def check(cls) -> Action:
        """Commit no additional money when allowed."""
        return cls(kind=ActionKind.CHECK)

    @classmethod
    def fold(cls) -> Action:
        """Forfeit the hand."""
        return cls(kind=ActionKind.FOLD)

    @classmethod
    def call(cls) -> Action:
        """Match the opponent's current commitment (including all-in for less)."""
        return cls(kind=ActionKind.CALL)

    @classmethod
    def raise_(cls, amount_dollars: int) -> Action:
        """Raise by ``amount_dollars`` (true ``int`` dollars, at least 1)."""
        return cls(kind=ActionKind.RAISE, amount_dollars=amount_dollars)
