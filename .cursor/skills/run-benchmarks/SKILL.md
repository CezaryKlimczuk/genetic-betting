---
name: run-benchmarks
description: >-
  Measures throughput for the genetic-betting simulator and interprets results.
  Use when the user asks about performance, hands per second, or profiling the
  game loop.
---

# Run benchmarks

## Status

A benchmark script is **not** part of the repo until you add it (see [`AGENTS.md`](../../AGENTS.md)). When it exists, use the workflow below.

## Command (once `scripts/` exists)

From repo root, after syncing the environment (e.g. `uv sync`):

```bash
uv run python scripts/benchmark_hands.py --hands 10000
```

Adjust the script name/path to match what you add.

## Interpreting results

- Compare **before/after** on the same machine with the same `--hands`.
- Stdlib timing is not a profiler; use `python -m cProfile` on the benchmark entrypoint if you need hotspots.

## Adding a benchmark

1. Keep timers **outside** the inner betting loop (`scripts/` or CLI driver), not inside per-action hot paths in `app/`.
2. Document usage in [`AGENTS.md`](../../AGENTS.md).

## Pitfalls

- Warmup and OS noise: repeat runs; do not extrapolate linearly from tiny `--hands` without checking variance.
- Random strategies add noise; for micro-benchmarks prefer a **cheap deterministic** strategy.
