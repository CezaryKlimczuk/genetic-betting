"""Measure single-hand simulation throughput (stdlib timer only; no hot-path overhead)."""

from __future__ import annotations

import argparse
import random
import sys
import time
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from app.config import load_game_config
from app.hand import play_hand
from app.strategies import RandomLegalStrategy


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Run N independent hands with RandomLegalStrategy on both seats and "
            "report hands per second (wall time via time.perf_counter)."
        ),
    )
    parser.add_argument(
        "--hands",
        type=int,
        default=10_000,
        help="Number of timed hands (default: 10000).",
    )
    parser.add_argument(
        "--config",
        type=Path,
        default=Path("config/game.example.yaml"),
        help="Game YAML path (default: config/game.example.yaml).",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=None,
        help="Optional RNG seed for reproducibility.",
    )
    parser.add_argument(
        "--warmup",
        type=int,
        default=0,
        help="Hands to run before the timed loop (default: 0).",
    )
    args = parser.parse_args()
    if args.hands < 1:
        parser.error("--hands must be at least 1.")
    if args.warmup < 0:
        parser.error("--warmup must be non-negative.")
    return args


def main() -> None:
    args = _parse_args()
    config = load_game_config(args.config)
    rng = random.Random(args.seed)
    strategy0 = RandomLegalStrategy()
    strategy1 = RandomLegalStrategy()

    for i in range(args.warmup):
        stacks = (config.starting_stack, config.starting_stack)
        play_hand(config, rng, stacks, i % 2, strategy0, strategy1)

    t0 = time.perf_counter()
    for i in range(args.hands):
        stacks = (config.starting_stack, config.starting_stack)
        play_hand(config, rng, stacks, (i + args.warmup) % 2, strategy0, strategy1)
    elapsed = time.perf_counter() - t0

    rate = args.hands / elapsed if elapsed > 0 else float("inf")
    print(
        f"hands={args.hands} elapsed_s={elapsed:.6f} hands_per_s={rate:.1f}",
    )


if __name__ == "__main__":
    main()
