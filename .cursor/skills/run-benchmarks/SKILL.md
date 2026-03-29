---
name: run-benchmarks
description: >-
  Measures throughput for the genetic-betting simulator and interprets results.
  Use when the user asks about performance, hands per second, or profiling the
  game loop.
---

# Run benchmarks

## Status

The repo ships [`scripts/benchmark_hands.py`](../../../scripts/benchmark_hands.py). It prepends the repo root to `sys.path` so **`uv run python scripts/benchmark_hands.py`** works from the repository root without an editable install.

## Command

From repo root, after syncing the environment (e.g. `uv sync`):

```bash
uv run python scripts/benchmark_hands.py --hands 10000
```

Optional flags: `--config PATH` (default `config/game.example.yaml`), `--seed N`, `--warmup K` (untimed hands before the timed loop).

## Interpreting results

- Compare **before/after** on the same machine with the same `--hands`.
- Stdlib timing is not a profiler; use `python -m cProfile` on the benchmark entrypoint if you need hotspots.

## Adding a benchmark

1. Keep timers **outside** the inner betting loop (`scripts/` or CLI driver), not inside per-action hot paths in `app/`.
2. Document usage in [`AGENTS.md`](../../../AGENTS.md).

## Pitfalls

- Warmup and OS noise: repeat runs; do not extrapolate linearly from tiny `--hands` without checking variance.
- Random strategies add noise; for micro-benchmarks prefer **`ScriptedStrategy`** or **`random.Random` with a fixed seed** over `RandomLegalStrategy`.
