"""Single-hand betting, refunds, and showdown (no match loop).

Betting order follows ``AGENTS.md``: the seat named ``first_to_act`` is
**Player 1** for this hand (acts first); the other seat is **Player 2**.

**Raise cap (callable amount)**: If a raise would require the facing player to
put in **more than their remaining stack**, the raise is **truncated** first:
the excess is refunded **immediately** from the pot to the raiser, so the amount
to call is at most the responder's stack. If that caps the raise to **$0**
extra, betting is over and the hand goes to **showdown** without another
decision.

**All-in refund invariant**: After a **call** that puts in less than the full
amount to match (all-in for less), the pot still holds the over-committed
player's unmatched chips. That excess is returned from the pot to that player
**before showdown**, so matched extras are equal and
``sum(stacks) + pot`` is unchanged. Refunds do **not** apply when the facing
player **folds**—the aggressor keeps the full pot including their raise.
**(Truncation avoids this path** when the raise exceeds what the responder can
add—they never face an uncapped amount to call.)
"""

from __future__ import annotations

import random
from collections.abc import Callable
from dataclasses import dataclass
from typing import Literal

from app.actions import Action, ActionKind
from app.actor_view import ActorView, DecisionPhase
from app.config import GameConfig, strict_int
from app.legal_actions import legal_actions_for_view

Strategy = Callable[[random.Random, ActorView], Action]


@dataclass(frozen=True, slots=True)
class HandResult:
    """Outcome of one hand after antes, betting, refunds, and pot award."""

    winner: int | None
    """Winning seat, or ``None`` if the pot was split (showdown tie)."""

    reason: Literal["fold", "showdown", "showdown_tie"]
    final_stacks: tuple[int, int]
    cards: tuple[int, int]
    first_to_act: int


@dataclass(frozen=True, slots=True)
class RaiseTruncationNotice:
    """Emitted when a raise amount is capped because the opponent cannot match more."""

    raiser_seat: int
    responder_seat: int
    requested_extra: int
    """Extra dollars the raiser tried to put in on this action (before cap)."""

    effective_extra: int
    """Extra dollars after capping (opponent's callable amount)."""


def _other(seat: int) -> int:
    return 1 - seat


def _raise_amounts(config: GameConfig, max_extra: int) -> list[int]:
    """Inclusive legal raise sizes (extra dollars) capped by ``max_extra``."""
    if max_extra < config.min_raise:
        return []
    hi = min(config.max_raise, max_extra)
    if hi < config.min_raise:
        return []
    return list(range(config.min_raise, hi + 1))


def _build_view(
    config: GameConfig,
    seat: int,
    stacks: tuple[int, int],
    *,
    pot: int,
    round_extra: tuple[int, int],
    cards: tuple[int, int],
    amount_to_call: int,
    can_raise: bool,
    raise_amount_min: int | None,
    raise_amount_max: int | None,
    decision_phase: DecisionPhase,
    can_fold: bool = True,
) -> ActorView:
    opp = _other(seat)
    return ActorView.from_config(
        config,
        seat=seat,
        own_card=cards[seat],
        opponent_card=None,
        wallet_self=stacks[seat],
        wallet_opponent=stacks[opp],
        pot=pot,
        amount_to_call=amount_to_call,
        can_check=amount_to_call == 0,
        can_fold=can_fold,
        can_call=amount_to_call > 0 and stacks[seat] > 0,
        can_raise=can_raise,
        raise_amount_min=raise_amount_min,
        raise_amount_max=raise_amount_max,
        decision_phase=decision_phase,
    )


def _truncate_raise_to_opponent_stack(
    pot: int,
    stacks: list[int],
    round_extra: list[int],
    raiser: int,
    responder: int,
) -> tuple[int, list[int]]:
    """Cap the raiser's round extra so the responder can match with their stack.

    If ``round_extra[raiser] - round_extra[responder] > stacks[responder]``,
    refund the surplus from the pot to the raiser and lower ``round_extra``.
    """
    r_extra = round_extra[raiser] - round_extra[responder]
    cap = stacks[responder]
    if r_extra <= cap:
        return pot, stacks
    excess = r_extra - cap
    round_extra[raiser] -= excess
    stacks[raiser] += excess
    return pot - excess, stacks


def _notify_raise_truncated_if_applicable(
    on_raise_truncated: Callable[[RaiseTruncationNotice], None] | None,
    *,
    raiser_seat: int,
    responder_seat: int,
    requested_extra: int,
    round_extra: list[int],
) -> None:
    if on_raise_truncated is None:
        return
    effective_extra = round_extra[raiser_seat] - round_extra[responder_seat]
    if requested_extra <= effective_extra:
        return
    on_raise_truncated(
        RaiseTruncationNotice(
            raiser_seat=raiser_seat,
            responder_seat=responder_seat,
            requested_extra=requested_extra,
            effective_extra=effective_extra,
        )
    )


def _apply_refund_if_mismatch(
    pot: int,
    stacks: list[int],
    round_extra: list[int],
) -> tuple[int, list[int]]:
    """Refund unmatched extra from pot to the over-committed seat."""
    e0, e1 = round_extra[0], round_extra[1]
    if e0 == e1:
        return pot, stacks
    if e0 > e1:
        refund = e0 - e1
        round_extra[0] = e1
        stacks[0] += refund
        return pot - refund, stacks
    refund = e1 - e0
    round_extra[1] = e0
    stacks[1] += refund
    return pot - refund, stacks


def _award_pot_winner(pot: int, stacks: list[int], winner: int) -> None:
    stacks[winner] += pot


def _award_split_pot(pot: int, stacks: list[int]) -> None:
    """Split ``pot``; odd dollar goes to seat 0 (AGENTS.md)."""
    if pot <= 0:
        return
    half = pot // 2
    rem = pot - 2 * half
    stacks[0] += half + rem
    stacks[1] += half


def _finish_hand_fold(
    winner: int,
    pot: int,
    stacks: list[int],
    cards: tuple[int, int],
    first_to_act: int,
) -> HandResult:
    """Award full ``pot`` to ``winner`` after an opponent fold."""
    _award_pot_winner(pot, stacks, winner)
    return HandResult(
        winner=winner,
        reason="fold",
        final_stacks=(stacks[0], stacks[1]),
        cards=cards,
        first_to_act=first_to_act,
    )


def _resolve_showdown(
    pot: int,
    stacks: list[int],
    cards: tuple[int, int],
    first_to_act: int,
) -> HandResult:
    """Compare hole cards, split on tie or award full ``pot`` to high card."""
    c0, c1 = cards[0], cards[1]
    if c0 > c1:
        w = 0
    elif c1 > c0:
        w = 1
    else:
        _award_split_pot(pot, stacks)
        return HandResult(
            winner=None,
            reason="showdown_tie",
            final_stacks=(stacks[0], stacks[1]),
            cards=cards,
            first_to_act=first_to_act,
        )
    _award_pot_winner(pot, stacks, w)
    return HandResult(
        winner=w,
        reason="showdown",
        final_stacks=(stacks[0], stacks[1]),
        cards=cards,
        first_to_act=first_to_act,
    )


def play_hand(
    config: GameConfig,
    rng: random.Random,
    stacks: tuple[int, int],
    first_to_act: int,
    strategy0: Strategy,
    strategy1: Strategy,
    *,
    on_raise_truncated: Callable[[RaiseTruncationNotice], None] | None = None,
) -> HandResult:
    """Play one hand: antes, deal, betting FSM, refunds, showdown if needed.

    Args:
        config: Validated game parameters.
        rng: Injected RNG (used to deal ``card_min``..``card_max`` inclusive).
        stacks: Wallets **before** antes (each must be >= ``config.ante``).
        first_to_act: Seat (0 or 1) that acts as **Player 1** this hand.
        strategy0: Chooses an action for seat 0.
        strategy1: Chooses an action for seat 1.
        on_raise_truncated: If set, called immediately after a raise is capped
            to the opponent's remaining stack (see module docstring).

    Returns:
        ``HandResult`` with final stacks (after pot resolution).

    Raises:
        ValueError: If ``stacks`` cannot cover ante or ``first_to_act`` invalid.
    """
    if first_to_act not in (0, 1):
        raise ValueError("first_to_act must be 0 or 1.")
    s0, s1 = strict_int("stacks[0]", stacks[0]), strict_int("stacks[1]", stacks[1])
    if s0 < config.ante or s1 < config.ante:
        raise ValueError("Each stack must be at least ante.")

    st = [s0, s1]
    pot = 0
    st[0] -= config.ante
    st[1] -= config.ante
    pot += 2 * config.ante
    round_extra = [0, 0]

    span = config.card_max - config.card_min + 1
    c0 = config.card_min + rng.randrange(span)
    c1 = config.card_min + rng.randrange(span)
    cards = (c0, c1)

    strategies: tuple[Strategy, Strategy] = (strategy0, strategy1)
    p1 = first_to_act
    p2 = _other(p1)

    def choose(seat: int, view: ActorView) -> Action:
        return strategies[seat](rng, view)

    # --- Player 1 (first actor) ---
    raise_opts1 = _raise_amounts(config, st[p1])
    can_r1 = len(raise_opts1) > 0
    v1 = _build_view(
        config,
        p1,
        (st[0], st[1]),
        pot=pot,
        round_extra=(round_extra[0], round_extra[1]),
        cards=cards,
        amount_to_call=0,
        can_raise=can_r1,
        raise_amount_min=min(raise_opts1) if can_r1 else None,
        raise_amount_max=max(raise_opts1) if can_r1 else None,
        decision_phase="p1_open",
    )
    legal1 = legal_actions_for_view(v1)
    a1 = choose(p1, v1)
    if a1 not in legal1:
        raise ValueError(f"Illegal action from seat {p1}: {a1!r}")

    if a1.kind is ActionKind.FOLD:
        return _finish_hand_fold(p2, pot, st, cards, first_to_act)

    if a1.kind is ActionKind.CALL:
        raise ValueError("Illegal call with nothing to match (use check).")

    if a1.kind is ActionKind.RAISE:
        if a1.amount_dollars is None:
            raise ValueError("raise without amount.")
        r = a1.amount_dollars
        st[p1] -= r
        pot += r
        round_extra[p1] += r
        pot, st = _truncate_raise_to_opponent_stack(pot, st, round_extra, p1, p2)
        _notify_raise_truncated_if_applicable(
            on_raise_truncated,
            raiser_seat=p1,
            responder_seat=p2,
            requested_extra=r,
            round_extra=round_extra,
        )

        to_call = round_extra[p1] - round_extra[p2]
        if to_call == 0:
            return _resolve_showdown(pot, st, cards, first_to_act)

        # --- Player 2: fold or call ---
        v2 = _build_view(
            config,
            p2,
            (st[0], st[1]),
            pot=pot,
            round_extra=(round_extra[0], round_extra[1]),
            cards=cards,
            amount_to_call=to_call,
            can_raise=False,
            raise_amount_min=None,
            raise_amount_max=None,
            decision_phase="p2_facing_raise",
        )
        legal2 = legal_actions_for_view(v2)
        a2 = choose(p2, v2)
        if a2 not in legal2:
            raise ValueError(f"Illegal action from seat {p2}: {a2!r}")

        if a2.kind is ActionKind.FOLD:
            return _finish_hand_fold(p1, pot, st, cards, first_to_act)

        # call (including all-in for less)
        pay = min(to_call, st[p2])
        st[p2] -= pay
        pot += pay
        round_extra[p2] += pay
        pot, st = _apply_refund_if_mismatch(pot, st, round_extra)

        return _resolve_showdown(pot, st, cards, first_to_act)

    if a1.kind is not ActionKind.CHECK:
        raise ValueError(f"Unexpected action from first actor: {a1!r}")

    raise_opts2 = _raise_amounts(config, st[p2])
    can_r2 = len(raise_opts2) > 0

    v2b = _build_view(
        config,
        p2,
        (st[0], st[1]),
        pot=pot,
        round_extra=(round_extra[0], round_extra[1]),
        cards=cards,
        amount_to_call=0,
        can_raise=can_r2,
        raise_amount_min=min(raise_opts2) if can_r2 else None,
        raise_amount_max=max(raise_opts2) if can_r2 else None,
        decision_phase="p2_after_check",
        can_fold=False,
    )
    legal2b = legal_actions_for_view(v2b)
    a2b = choose(p2, v2b)
    if a2b not in legal2b:
        raise ValueError(f"Illegal action from seat {p2}: {a2b!r}")

    if a2b.kind is ActionKind.CHECK:
        return _resolve_showdown(pot, st, cards, first_to_act)

    if a2b.kind is not ActionKind.RAISE or a2b.amount_dollars is None:
        raise ValueError("Expected raise after check from Player 2.")
    r2 = a2b.amount_dollars
    st[p2] -= r2
    pot += r2
    round_extra[p2] += r2
    pot, st = _truncate_raise_to_opponent_stack(pot, st, round_extra, p2, p1)
    _notify_raise_truncated_if_applicable(
        on_raise_truncated,
        raiser_seat=p2,
        responder_seat=p1,
        requested_extra=r2,
        round_extra=round_extra,
    )

    to_call1 = round_extra[p2] - round_extra[p1]
    if to_call1 == 0:
        return _resolve_showdown(pot, st, cards, first_to_act)

    v1b = _build_view(
        config,
        p1,
        (st[0], st[1]),
        pot=pot,
        round_extra=(round_extra[0], round_extra[1]),
        cards=cards,
        amount_to_call=to_call1,
        can_raise=False,
        raise_amount_min=None,
        raise_amount_max=None,
        decision_phase="p1_facing_raise",
    )
    legal1b = legal_actions_for_view(v1b)
    a1b = choose(p1, v1b)
    if a1b not in legal1b:
        raise ValueError(f"Illegal action from seat {p1}: {a1b!r}")

    if a1b.kind is ActionKind.FOLD:
        return _finish_hand_fold(p2, pot, st, cards, first_to_act)

    pay1 = min(to_call1, st[p1])
    st[p1] -= pay1
    pot += pay1
    round_extra[p1] += pay1
    pot, st = _apply_refund_if_mismatch(pot, st, round_extra)

    return _resolve_showdown(pot, st, cards, first_to_act)
