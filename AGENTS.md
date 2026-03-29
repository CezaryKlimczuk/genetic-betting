# Agent context: genetic-betting

## Purpose

Configurable **two-player** betting game (single card showdown) as boilerplate for later genetic-algorithm training. The core should stay **deterministic with a seeded RNG**, **fast enough for large batches**, and **rules-driven** from config.

Follow the **planned layout and task plan** the owner provides (roadmap, issues, or chat instructions). This file is the stable reference for **domain rules** and **repo conventions**; execution order comes from that plan.

## Game rules (authoritative v1)

Betting order each **round**: Player 1 acts first, then Player 2; after the round, **first actor alternates** (Player 2 starts the next round).

1. **If Player 1 raises**  
   The raise size is an **integer** in **`[min_raise, max_raise]`** from config (inclusive), capped by stack (same bounds as Player 2’s raise after a check).  
   Player 2 may **fold** or **call** (match the raise, including **all-in for less** if the stack is insufficient).

2. **If Player 1 checks** (commits **$0** beyond the ante for this decision)  
   Player 2 may **check** (also **$0** beyond ante) or **raise**.  
   **This is the only situation in which Player 2 may raise.**

3. **If Player 2 raises** (after Player 1 checked)  
   The raise amount must be an **integer** in **`[min_raise, max_raise]`** from config (inclusive).  
   Player 1 may **fold** or **call** (match, including all-in for less).

**Terminology**

- **Check**: only an action that adds **no** money beyond what is already committed for this decision (betting $0).
- **Call**: match the opponent’s current commitment for the round (not available when there is nothing extra to match).

There is **no re-raise chain**: at most **one** raise in a round (by Player 2, and only after Player 1 checked).

**Showdown**: If neither player folds, compare cards (values from config range, e.g. 1–10). Higher card wins the pot; **tie → split the pot**.

**Money**: All balances, antes, raises, and pot sizes are integers (**`int`** in code; no fractional amounts).

**Tie-break for odd pot**: When splitting, if the pot is odd, assign the extra **$1** to **seat 0** (deterministic).

**All-in mismatch**: If one player **calls** for less than the full amount to match, **refund** the unmatched amount from the pot to the over-committed player **before showdown**. This does **not** apply when the opponent **folds**—the winner takes the full pot, including the unmatched portion of a raise.

**Seats vs Player 1 / 2**: The engine uses **seat 0** and **seat 1**. Each **hand**, the seat that opens the betting sequence is **Player 1** for the rules above (the match layer passes `first_to_act`); the other seat is **Player 2**. The odd-pot split tie-break assigns the extra **$1** to **seat 0** (not “who was Player 1”).

**First action**: Player 1 may **fold** on the first decision (forfeit the hand, including ante already posted).

**Match end**: Play until a player cannot cover the next **ante** (brokes out of the match) or a **safety max-round** (`max_rounds_per_match`) cap is reached. The richer seat wins; **equal final stacks → no single winner** (implementation uses `None` for the winner id). In code, `run_match` returns `MatchResult` with `reason` of **`bankruptcy`** (cannot post ante before the next hand) or **`max_hands`** (hand cap from `max_rounds_per_match` reached).

## Planned layout

| Path | Role |
|------|------|
| `app/` | Application modules—`config`, `actions` / `actor_view`, **`hand.py`** (one hand), **`match.py`** (`run_match`), **`strategies.py`** (`HotseatStrategy`, `ScriptedStrategy`, `RandomLegalStrategy`, `legal_actions_for_view`), **`cli.py`** (`hotseat_menu_actions`, `hotseat_action_completes_hand`, argparse hotseat driver)—run with `uv run python -m app.cli`, not an installable distribution |
| `config/` | Example game **YAML** (stacks, ante, `min_raise` / `max_raise`, card range, max rounds) |
| `tests/` | `pytest` (`pythonpath` includes repo root so `import app` works) |
| `scripts/` | Optional throughput benchmark |

A **strategy** is `Callable[[random.Random, ActorView], Action]` (see `Strategy` in `hand.py`). `ActorView.can_fold` is only true when fold is legal at that decision (e.g. false for Player 2 after Player 1 checked—**check** or **raise** only).

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

### Hotseat CLI (two humans, one terminal)

- Run: **`uv run python -m app.cli`**
- **`--config`**: path to game YAML (default: **`config/game.example.yaml`**).
- **`--seed`**: optional `int` seed for `random.Random` when dealing cards (omit for nondeterministic deals).
- Each prompt shows only the **current** seat’s hole card, balances, pot, and a **fixed-order** numbered menu: fold, check, call, then every raise amount in **`min_raise`..`max_raise`** from config. Illegal rows are still listed and marked **`(NOT AVAILABLE)`** so action indices stay stable (useful for neural-net outputs tied to one slot per action kind/size). **Opponent’s card is not shown** until **showdown**; on a **fold**, hole cards stay hidden.
- After a seat submits a **legal** choice, the CLI pauses (**Enter**): if another decision remains in the hand, it asks to pass the keyboard to the other seat; if the action ends the hand (fold, call, or check-down), it asks to continue to **hand results** instead. After each hand, it prints a spaced hand summary and pauses (**Enter**) before the next hand when the match continues, including **which seat opens** as Player 1.
- **`run_match`** accepts optional **`before_each_hand`** and **`after_each_hand`** callbacks (used by the CLI to print hand banners and outcomes without putting I/O in the engine core).

## Definition of done

- Behavior matches the **Game rules** section; **conservation** of total money in play holds (including refunds).
- Config keys documented in example **YAML** and loaded in code.
- Tests cover: P1 raise → P2 fold vs call; P1 check → P2 check vs raise (amount in config range) → P1 fold vs call; ties and odd pot; short all-in refund.
- Public API docstrings per `.cursor/rules/python-pep8-docstrings.mdc`.

## Performance

- No logging inside inner action-selection / betting loops for batch runs.
- Prefer compact state and small numeric types on the hot path; optional batching stays outside the core rules loop.
