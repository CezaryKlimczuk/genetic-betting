"""Multi-hand match: alternating first actor, bankruptcy and hand-cap endings."""

from __future__ import annotations

import random
from collections.abc import Callable
from dataclasses import dataclass
from typing import Literal

from app.config import GameConfig
from app.hand import HandResult, Strategy, play_hand

MatchEndReason = Literal["max_hands", "bankruptcy"]


@dataclass(frozen=True, slots=True)
class MatchResult:
    """Outcome after ``run_match`` (terminal balances and match winner)."""

    winner: int | None
    """Richer seat at end, or ``None`` if stacks are tied."""

    final_stacks: tuple[int, int]
    reason: MatchEndReason
    hands_played: int


def _richer_seat(stacks: tuple[int, int]) -> int | None:
    a, b = stacks[0], stacks[1]
    if a > b:
        return 0
    if b > a:
        return 1
    return None


def run_match(
    config: GameConfig,
    rng: random.Random,
    strategy0: Strategy,
    strategy1: Strategy,
    *,
    before_each_hand: Callable[[int, tuple[int, int], int], None] | None = None,
    after_each_hand: Callable[[HandResult], None] | None = None,
) -> MatchResult:
    """Run hands until bankruptcy, max hands, or cap (see ``AGENTS.md``).

    Starting stacks are ``config.starting_stack`` each. Seat ``hand_index % 2``
    is Player 1 (opens the action) on that hand. If either stack is below
    ``config.ante`` before dealing a hand, the match ends immediately with
    ``reason=bankruptcy`` and no further hands. Otherwise at most
    ``config.max_rounds_per_match`` hands are played; if the cap is reached,
    ``reason=max_hands``. The match ``winner`` is the seat with more money
    (``None`` if tied).

    Args:
        config: Validated parameters including stack, ante, and hand cap.
        rng: Injected RNG (passed through to each ``play_hand``).
        strategy0: Chooses actions for seat 0.
        strategy1: Chooses actions for seat 1.
        before_each_hand: If set, called before each hand with
            ``(hand_number, stacks_before_antes, first_to_act)`` where
            ``hand_number`` is 1-based within this match.
        after_each_hand: If set, called after each completed hand with
            that hand's :class:`~app.hand.HandResult`.

    Returns:
        ``MatchResult`` with final stacks, end reason, and richer seat if any.
    """
    stacks = (config.starting_stack, config.starting_stack)
    hands_played = 0

    for hand_index in range(config.max_rounds_per_match):
        if stacks[0] < config.ante or stacks[1] < config.ante:
            return MatchResult(
                winner=_richer_seat(stacks),
                final_stacks=stacks,
                reason="bankruptcy",
                hands_played=hands_played,
            )

        first_to_act = hand_index % 2
        if before_each_hand is not None:
            before_each_hand(hands_played + 1, stacks, first_to_act)
        hand_result: HandResult = play_hand(
            config,
            rng,
            stacks,
            first_to_act,
            strategy0,
            strategy1,
        )
        if after_each_hand is not None:
            after_each_hand(hand_result)
        stacks = hand_result.final_stacks
        hands_played += 1

    return MatchResult(
        winner=_richer_seat(stacks),
        final_stacks=stacks,
        reason="max_hands",
        hands_played=hands_played,
    )
