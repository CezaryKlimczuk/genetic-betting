"""Command-line entrypoint for the genetic-betting app."""

from __future__ import annotations

import argparse
import random
import sys
from pathlib import Path

from app.actions import Action, ActionKind
from app.actor_view import ActorView
from app.config import load_game_config
from app.hand import HandResult
from app.match import run_match
from app.strategies import HotseatStrategy, legal_actions_for_view


def build_parser() -> argparse.ArgumentParser:
    """Return the CLI argument parser."""
    parser = argparse.ArgumentParser(
        prog="python -m app.cli",
        description=(
            "Two-player betting game: hotseat mode (one terminal, two humans). "
            "Opponent hole cards stay hidden until showdown unless the hand ends in a fold."
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


def prompt_action_from_view(
    _rng: random.Random, view: ActorView, file=sys.stdout
) -> Action:
    """Print the actor view (own card only) and read a menu choice from stdin."""
    legal = legal_actions_for_view(view)
    if not legal:
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
    print("Legal moves:", file=file)
    for i, a in enumerate(legal, start=1):
        print(f"  {i}) {_format_action_line(a)}", file=file)

    while True:
        raw = input("Enter choice number: ").strip()
        if not raw.isdigit():
            print("Please enter a positive integer.", file=file)
            continue
        n = int(raw)
        if 1 <= n <= len(legal):
            return legal[n - 1]
        print(f"Choose 1–{len(legal)}.", file=file)


def _before_hand(hand_no: int, stacks: tuple[int, int], first_to_act: int) -> None:
    print()
    print("=" * 54)
    print(f"Hand {hand_no} — stacks: seat 0 = ${stacks[0]}, seat 1 = ${stacks[1]}")
    print(f"Player 1 (acts first this hand): seat {first_to_act}")
    print("=" * 54)


def _after_hand(result: HandResult) -> None:
    c0, c1 = result.cards
    if result.reason == "fold":
        w = result.winner
        assert w is not None
        loser = 1 - w
        print()
        print(
            f"Hand over: seat {loser} folded. Seat {w} wins the pot. "
            "Hole cards stay hidden."
        )
    elif result.reason == "showdown_tie":
        print()
        print(f"Showdown — cards: seat 0 = {c0}, seat 1 = {c1}. Tie; pot split.")
        print("(Odd chip from an odd pot goes to seat 0.)")
    else:
        w = result.winner
        print()
        print(f"Showdown — cards: seat 0 = {c0}, seat 1 = {c1}. Seat {w} wins the pot.")

    fs = result.final_stacks
    print(f"Stacks after hand: seat 0 = ${fs[0]}, seat 1 = ${fs[1]}")


def main(argv: list[str] | None = None) -> None:
    """Run hotseat play: load config, loop a full match with stdin prompts."""
    parser = build_parser()
    args = parser.parse_args(argv)
    cfg_path: Path = args.config
    if not cfg_path.is_file():
        parser.error(f"Config file not found: {cfg_path}")

    config = load_game_config(cfg_path)
    rng = random.Random(args.seed)

    print(f"Loaded config from {cfg_path.resolve()}")
    if args.seed is not None:
        print(f"Deal seed: {args.seed}")
    print(
        "Hotseat: pass the keyboard between seats. Menus show only the current "
        "player's hole card until showdown."
    )

    human0 = HotseatStrategy(prompt_action_from_view)
    human1 = HotseatStrategy(prompt_action_from_view)

    result = run_match(
        config,
        rng,
        human0,
        human1,
        before_each_hand=_before_hand,
        after_each_hand=_after_hand,
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
