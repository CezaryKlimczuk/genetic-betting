"""Command-line entrypoint for the genetic-betting app."""

from __future__ import annotations

import argparse


def build_parser() -> argparse.ArgumentParser:
    """Return the CLI argument parser."""
    parser = argparse.ArgumentParser(
        prog="python -m app.cli",
        description="Two-player betting game (hotseat CLI and simulation).",
    )
    return parser


def main(argv: list[str] | None = None) -> None:
    """Parse CLI arguments and dispatch (full play loop in T7)."""
    parser = build_parser()
    parser.parse_args(argv)


if __name__ == "__main__":
    main()
