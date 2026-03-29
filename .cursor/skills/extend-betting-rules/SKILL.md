---
name: extend-betting-rules
description: >-
  Adds or changes betting game rules in genetic-betting: config schema, engine
  legal actions, and tests. Use when the user asks to change antes, raises,
  player order, showdown rules, or similar game logic.
---

# Extend betting rules

## Prerequisites

If there is no `app/` tree yet, follow [`AGENTS.md`](../../AGENTS.md) and the owner’s plan to add code first; then use this checklist.

## Checklist

1. **Config**: Update the game config dataclass and **YAML** loader (fields in **whole dollars**). Add any new third-party deps with **`uv add`**, not hand-edited `pyproject.toml` lists (see `.cursor/rules/dependencies-uv.mdc`).
2. **Example config**: Update or add an example under `config/` (**`.yaml`**) with comments for new keys.
3. **Engine**: Adjust legal actions and transitions to match [`AGENTS.md`](../../AGENTS.md) (check vs call, P2 raise only after P1 check, raise amounts in config range).
4. **Match loop**: Change end-of-match / alternating first player if rules require it.
5. **Tests**: Add or adjust `tests/` cases; run **`uv run pytest`** (or the project’s test command).
6. **Agents doc**: Sync the **Game rules** section in [`AGENTS.md`](../../AGENTS.md) if behavior changes.

## Constraints

- Money stays **`int` dollars** (no floats).
- Preserve **injected RNG** for determinism.
- Prefer **config-driven** values over magic numbers.

## PR / commit note

One short paragraph: rule change, config keys, tests added.
