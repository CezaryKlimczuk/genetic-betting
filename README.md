# genetic-betting

Configurable **two-player** betting game (single-card showdown) for local **hotseat** play and future batch simulation or genetic-algorithm experiments.

After antes, the opening player acts first and may fold, check, or raise (integer raise sizes from config); the other player may raise only after a check, and there is at most **one** raise per hand—no re-raises. If nobody folds, **showdown** compares hole cards: higher card wins the pot; ties split.

Authoritative rules, money handling, and match end conditions are in [`AGENTS.md`](AGENTS.md).

## Prerequisites

- [uv](https://docs.astral.sh/uv/) for environments and dependency installs
- **Python 3.13+** (see `requires-python` in [`pyproject.toml`](pyproject.toml))

## Setup

From the repository root:

```bash
uv sync
```

This installs runtime dependencies (e.g. PyYAML for game config) and dev dependencies (pytest). The project is **not** published as an installable package; run modules with `uv run python -m …` from the repo root.

## Play (hotseat)

Two people share one keyboard. Each prompt shows only the **current** seat’s hole card, stacks, pot, and a numbered menu of legal actions. **Both cards appear at showdown**; **if the hand ends in a fold, hole cards stay hidden.**

```bash
uv run python -m app.cli
```

| Option | Description |
|--------|-------------|
| `--config PATH` | Path to game YAML (default: `config/game.example.yaml`) |
| `--seed N` | Optional integer seed for `random.Random` when dealing; omit for nondeterministic deals |

Example:

```bash
uv run python -m app.cli --config config/game.example.yaml --seed 42
```

If the config path is missing or invalid, the program exits with an error after argparse validation.

## Configuration file

Example: [`config/game.example.yaml`](config/game.example.yaml).

| Key | Meaning |
|-----|---------|
| `starting_stack` | Each seat’s stack at match start |
| `ante` | Posted each hand before action |
| `min_raise`, `max_raise` | Inclusive bounds on raise sizes (capped by stack in play) |
| `max_rounds_per_match` | Maximum hands in a match (safety cap); if reached, the richer seat wins (see `MatchResult` in `app/match.py`) |
| `card_min`, `card_max` | Inclusive range of dealt card values |

Unknown keys or failed validation raise errors from `app.config.load_game_config`.

## Tests

```bash
uv run pytest
```

[`pyproject.toml`](pyproject.toml) sets `pythonpath = ["."]` so tests can `import app` without installing the tree as a package.

## Layout and development

- `app/` — config loader, hand engine, match loop, strategies, CLI
- `config/` — example YAML
- `tests/` — pytest suite

See [`AGENTS.md`](AGENTS.md) for betting rules, module responsibilities, and conventions for agents and contributors.
