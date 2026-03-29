# Agent context: genetic-betting

## Purpose

Configurable **two-player** betting game (single card showdown) as boilerplate for later genetic-algorithm training. The core should stay **deterministic with a seeded RNG**, **fast enough for large batches**, and **rules-driven** from config.

Follow the **planned layout and task plan** the owner provides (roadmap, issues, or chat instructions). This file is the stable reference for **domain rules** and **repo conventions**; execution order comes from that plan.

## Game rules (authoritative v1)

Betting order each **round**: Player 1 acts first, then Player 2; after the round, **first actor alternates** (Player 2 starts the next round).

1. **If Player 1 raises**  
   The raise size is an **integer dollar** in **`[min_raise, max_raise]`** from config (inclusive), capped by stack (same bounds as Player 2’s raise after a check).  
   Player 2 may **fold** or **call** (match the raise, including **all-in for less** if the stack is insufficient).

2. **If Player 1 checks** (commits **$0** beyond the ante for this decision)  
   Player 2 may **check** (also **$0** beyond ante) or **raise**.  
   **This is the only situation in which Player 2 may raise.**

3. **If Player 2 raises** (after Player 1 checked)  
   The raise amount must be an **integer dollar** amount in **`[min_raise, max_raise]`** from config (inclusive).  
   Player 1 may **fold** or **call** (match, including all-in for less).

**Terminology**

- **Check**: only an action that adds **no** money beyond what is already committed for this decision (betting $0).
- **Call**: match the opponent’s current commitment for the round (not available when there is nothing extra to match).

There is **no re-raise chain**: at most **one** raise in a round (by Player 2, and only after Player 1 checked).

**Showdown**: If neither player folds, compare cards (values from config range, e.g. 1–10). Higher card wins the pot; **tie → split the pot**.

**Money**: All balances, antes, raises, and pot sizes are **`int` whole dollars** (no floats).

**Tie-break for odd pot (dollars)**: When splitting, if the pot is odd, assign the extra **$1** to **seat 0** (deterministic).

**All-in mismatch**: If one player **calls** for less than the full amount to match, **refund** unmatched dollars from the pot to the over-committed player **before showdown**. This does **not** apply when the opponent **folds**—the winner takes the full pot, including the unmatched portion of a raise.

**Seats vs Player 1 / 2**: The engine uses **seat 0** and **seat 1**. Each **hand**, the seat that opens the betting sequence is **Player 1** for the rules above (the match layer passes `first_to_act`); the other seat is **Player 2**. The odd-pot split tie-break assigns the extra **$1** to **seat 0** (not “who was Player 1”).

**First action**: Player 1 may **fold** on the first decision (forfeit the hand, including ante already posted).

**Match end**: Play until a player is broke or a **safety max-round** limit; then the player with **more money** wins.

## Planned layout

| Path | Role |
|------|------|
| `app/` | Application modules (YAML config load, actions, hand/round, match, strategies, CLI)—run with `uv run python -m app.cli`, not an installable distribution |
| `config/` | Example game **YAML** (dollar amounts, ante, `min_raise` / `max_raise`, card range, max rounds) |
| `tests/` | `pytest` (`pythonpath` includes repo root so `import app` works) |
| `scripts/` | Optional throughput benchmark |

## Config format

- Prefer **YAML** for game (and project) config files, not TOML.
- Parsing requires a YAML library added via **`uv add`** (see `.cursor/rules/dependencies-uv.mdc`).

## Commands

Use **`uv`** for environments and dependencies (see dependency rule). Typical workflow once the package is wired up:

```bash
uv sync
uv run pytest
```

Adjust to match the repo’s `uv`/`pytest` setup as it evolves.

## Definition of done

- Behavior matches the **Game rules** section; **conservation** of total dollars holds (including refunds).
- Monetary fields are **`int` dollars** in the engine API.
- Config keys documented in example **YAML** and loaded in code.
- Tests cover: P1 raise → P2 fold vs call; P1 check → P2 check vs raise (amount in config range) → P1 fold vs call; ties and odd pot; short all-in refund.
- Public API docstrings per `.cursor/rules/python-pep8-docstrings.mdc`.

## Performance

- No logging inside inner action-selection / betting loops for batch runs.
- Prefer small types (`int` dollars, compact state) on the hot path; optional batching stays outside the core rules loop.
