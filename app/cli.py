"""Command-line entrypoint for the genetic-betting app."""

from __future__ import annotations

import argparse
import random
import sys
from pathlib import Path

from app.actions import Action, ActionKind
from app.actor_view import ActorView
from app.config import GameConfig, load_game_config
from app.hand import HandResult, RaiseTruncationNotice
from app.match import run_match
from app.strategies import HotseatStrategy

# Spaces between the longest action label and "(NOT AVAILABLE)" for readability.
_MENU_GAP_BEFORE_UNAVAILABLE = 4


def build_parser() -> argparse.ArgumentParser:
    """Return the CLI argument parser."""
    parser = argparse.ArgumentParser(
        prog="python -m app.cli",
        description=(
            "Two-player betting game: hotseat mode (one terminal, two humans). "
            "Each seat sees only their own card until showdown; fold endings do not reveal hole cards."
        ),
    )
    parser.add_argument(
        "--config",
        type=Path,
        default=Path("config/game.example.yaml"),
        help="Path to game YAML (default: config/game.example.yaml)",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=None,
        help="Seed for random.Random when dealing cards (default: nondeterministic).",
    )
    return parser


def _format_action_line(action: Action) -> str:
    if action.kind is ActionKind.FOLD:
        return "fold"
    if action.kind is ActionKind.CHECK:
        return "check"
    if action.kind is ActionKind.CALL:
        return "call (match; may be all-in for less)"
    if action.kind is ActionKind.RAISE:
        assert action.amount_dollars is not None
        return f"raise +${action.amount_dollars}"
    raise AssertionError(f"Unknown action: {action!r}")


def hotseat_menu_actions(config: GameConfig, view: ActorView) -> list[tuple[Action, bool]]:
    """Return fixed-slot menu rows: ``(action, is_legal)`` for this view.

    Order is stable for training: fold, check, call, then every raise size in
    ``[config.min_raise, config.max_raise]`` inclusive.
    """
    rows: list[tuple[Action, bool]] = [
        (Action.fold(), view.can_fold),
        (Action.check(), view.can_check),
        (Action.call(), view.can_call),
    ]
    for amt in range(config.min_raise, config.max_raise + 1):
        legal = (
            view.can_raise
            and view.raise_amount_min is not None
            and view.raise_amount_max is not None
            and view.raise_amount_min <= amt <= view.raise_amount_max
        )
        rows.append((Action.raise_(amt), legal))
    return rows


def hotseat_action_completes_hand(view: ActorView, action: Action) -> bool:
    """Return True if this choice finishes the current hand (no further decisions).

    Relies on :attr:`~app.actor_view.ActorView.decision_phase` set in
    ``app.hand`` when the view is built. Fold and call always end the hand if
    submitted (matching prior CLI behavior); raise never does; check ends only
    in the ``p2_after_check`` phase (check-back after Player 1 checked).
    """
    if action.kind is ActionKind.FOLD:
        return True
    if action.kind is ActionKind.CALL:
        return True
    if action.kind is ActionKind.RAISE:
        return False
    if action.kind is ActionKind.CHECK:
        return view.decision_phase == "p2_after_check"
    raise AssertionError(f"Unknown action: {action!r}")


def prompt_action_from_view(
    _rng: random.Random,
    view: ActorView,
    config: GameConfig,
    *,
    file=sys.stdout,
    submit_pause: bool = True,
) -> Action:
    """Print the actor view (own card only) and read a menu choice from stdin.

    The menu always lists the same action slots (fold, check, call, then every
    configured raise size). Illegal rows are shown with ``(NOT AVAILABLE)``.
    After a legal choice, optionally pauses: either a handoff to the next actor
    or a prompt to continue to hand results when this action ends the hand.
    """
    menu = hotseat_menu_actions(config, view)
    legal_actions = [a for a, ok in menu if ok]
    if not legal_actions:
        msg = "No legal actions for this view."
        raise RuntimeError(msg)

    print(file=file)
    print(f"--- Seat {view.seat} to act ---", file=file)
    print(f"Your card: {view.own_card}  (deck {view.card_min}–{view.card_max})", file=file)
    print(
        f"Your stack: ${view.wallet_self}  Opponent stack: ${view.wallet_opponent}  "
        f"Pot: ${view.pot}",
        file=file,
    )
    if view.amount_to_call:
        print(f"Amount to call (extra beyond ante): ${view.amount_to_call}", file=file)
    else:
        print("Nothing to call yet (check or raise / fold as offered).", file=file)
    print("Actions:", file=file)
    labels = [_format_action_line(a) for a, _ in menu]
    label_width = max(len(s) for s in labels) if labels else 0
    for i, (ok, label) in enumerate(zip((ok for _, ok in menu), labels, strict=True), start=1):
        if ok:
            print(f"  {i})  {label}", file=file)
        else:
            spacer = label_width - len(label) + _MENU_GAP_BEFORE_UNAVAILABLE
            print(f"  {i})  {label}{' ' * spacer}(NOT AVAILABLE)", file=file)

    chosen: Action | None = None
    while chosen is None:
        raw = input("Enter choice number: ").strip()
        if not raw.isdigit():
            print("Please enter a positive integer.", file=file)
            continue
        n = int(raw)
        if not (1 <= n <= len(menu)):
            print(f"Choose 1–{len(menu)}.", file=file)
            continue
        act, ok = menu[n - 1]
        if not ok:
            print("That action is not available. Pick a numbered row without (NOT AVAILABLE).", file=file)
            continue
        chosen = act

    if submit_pause:
        print(file=file)
        print(f"Seat {view.seat} submitted: {_format_action_line(chosen)}.", file=file)
        if hotseat_action_completes_hand(view, chosen):
            print(
                "This action ends the hand. Press Enter to see the hand results.",
                file=file,
            )
        else:
            other = 1 - view.seat
            print(
                f"Pass the keyboard to seat {other}. Press Enter when seat {other} "
                "is ready to act.",
                file=file,
            )
        input()

    return chosen


def _before_hand(hand_no: int, stacks: tuple[int, int], first_to_act: int) -> None:
    print()
    print("=" * 54)
    print(f"Hand {hand_no} — stacks: seat 0 = ${stacks[0]}, seat 1 = ${stacks[1]}")
    print(f"Player 1 (acts first this hand): seat {first_to_act}")
    print("=" * 54)


def _format_hand_outcome(result: HandResult) -> list[str]:
    """Human-readable outcome lines for one hand."""
    lines: list[str] = []
    c0, c1 = result.cards
    if result.reason == "fold":
        w = result.winner
        assert w is not None
        loser = 1 - w
        lines.append(
            f"Hand over: seat {loser} folded. Seat {w} wins the pot. "
            "Hole cards stay hidden."
        )
    elif result.reason == "showdown_tie":
        lines.append(
            f"Showdown — cards: seat 0 = {c0}, seat 1 = {c1}. Tie; pot split."
        )
        lines.append("(Odd chip from an odd pot goes to seat 0.)")
    else:
        w = result.winner
        lines.append(
            f"Showdown — cards: seat 0 = {c0}, seat 1 = {c1}. Seat {w} wins the pot."
        )
    fs = result.final_stacks
    lines.append(f"Stacks after hand: seat 0 = ${fs[0]}, seat 1 = ${fs[1]}")
    return lines


def _match_can_continue(
    config: GameConfig, stacks: tuple[int, int], hands_completed: int
) -> bool:
    """Whether ``run_match`` would deal another hand after ``hands_completed`` hands."""
    if hands_completed >= config.max_rounds_per_match:
        return False
    return stacks[0] >= config.ante and stacks[1] >= config.ante


def main(argv: list[str] | None = None) -> None:
    """Run hotseat play: load config, loop a full match with stdin prompts."""
    parser = build_parser()
    args = parser.parse_args(argv)
    cfg_path: Path = args.config
    if not cfg_path.is_file():
        parser.error(f"Config file not found: {cfg_path}")

    config = load_game_config(cfg_path)
    rng = random.Random(args.seed)
    hands_completed = 0

    print(f"Loaded config from {cfg_path.resolve()}")
    if args.seed is not None:
        print(f"Deal seed: {args.seed}")
    print(
        "Hotseat: pass the keyboard between seats. Menus list every action in a "
        "fixed order; illegal rows are marked (NOT AVAILABLE). Only your hole card "
        "is shown until showdown."
    )

    def choose(_r: random.Random, view: ActorView) -> Action:
        return prompt_action_from_view(_r, view, config)

    def on_raise_truncated(note: RaiseTruncationNotice) -> None:
        refund = note.requested_extra - note.effective_extra
        print()
        print("--- Raise truncated (opponent cannot match the full amount) ---")
        print(
            f"Seat {note.raiser_seat} raised +${note.requested_extra}, but seat "
            f"{note.responder_seat} can only put in +${note.effective_extra} more "
            "in this betting round given their stack."
        )
        print(
            f"The raise counts as +${note.effective_extra}; ${refund} is refunded "
            f"from the pot to seat {note.raiser_seat}."
        )
        if note.effective_extra == 0:
            print("No further betting this hand; the hand goes to showdown.")
        print()
        input("Press Enter to continue.")

    human0 = HotseatStrategy(choose)
    human1 = HotseatStrategy(choose)

    def after_each_hand(result: HandResult) -> None:
        nonlocal hands_completed
        hands_completed += 1
        print()
        print()
        for line in _format_hand_outcome(result):
            print(line)
        print()
        if _match_can_continue(config, result.final_stacks, hands_completed):
            next_first = hands_completed % 2
            print(
                f"Next hand: Player 1 (opens the betting) will be seat {next_first}."
            )
            print()
            input("Press Enter to start the next hand.")

    result = run_match(
        config,
        rng,
        human0,
        human1,
        before_each_hand=_before_hand,
        after_each_hand=after_each_hand,
        on_raise_truncated=on_raise_truncated,
    )

    print()
    print("— Match finished —")
    print(f"Reason: {result.reason}")
    print(f"Hands played: {result.hands_played}")
    print(
        f"Final stacks: seat 0 = ${result.final_stacks[0]}, "
        f"seat 1 = ${result.final_stacks[1]}"
    )
    if result.winner is None:
        print("Match winner: none (tied stacks).")
    else:
        print(f"Match winner: seat {result.winner} (richest).")


if __name__ == "__main__":
    main()
