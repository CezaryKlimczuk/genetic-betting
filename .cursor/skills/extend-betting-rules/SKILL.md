---
name: extend-betting-rules
description: >-
  Adds or changes betting game rules in genetic-betting: config schema, engine
  legal actions, and tests. Use when the user asks to change antes, raises,
  player order, showdown rules, or similar game logic.
---

# Extend betting rules

## Prerequisites

If there is no `app/` tree yet, follow [`AGENTS.md`](../../../AGENTS.md) and the owner’s plan to add code first; then use this checklist.

## Checklist

1. **Config**: Update the game config dataclass and **YAML** loader. Add any new third-party deps with **`uv add`**, not hand-edited `pyproject.toml` lists (see `.cursor/rules/dependencies-uv.mdc`).
2. **Example config**: Update or add an example under `config/` (**`.yaml`**) with comments for new keys.
3. **Engine**: Update **`app/hand.py`** for per-hand rules; update **`app/match.py`** if match-level behavior changes. Legal actions and transitions must match [`AGENTS.md`](../../../AGENTS.md) (check vs call, P2 raise only after P1 check, raises in `min_raise`..`max_raise`, refunds on short call only). If decision nodes or `ActorView` flags change, update **`app/legal_actions.py`** (`legal_actions_for_view`) and the view construction in **`hand.py`** (including **`ActorView.decision_phase`** in **`_build_view`**) so legality and phase tags stay consistent with the FSM; **`app/strategies.py`** re-exports the function for backward compatibility.
4. **Match loop**: In **`app/match.py`**, adjust end-of-match reason (`bankruptcy` vs `max_hands`), the YAML cap key (`max_rounds_per_match`), alternating first actor, or tie handling if rules require it.
5. **Tests**: Add or adjust `tests/` cases; run **`uv run pytest`** (or the project’s test command).
6. **Agents doc**: Sync the **Game rules** section in [`AGENTS.md`](../../../AGENTS.md) if behavior changes.
7. **Hotseat CLI** (if relevant): Menu order and **`hotseat_menu_actions`** in **`app/cli.py`** use config **`min_raise`..`max_raise`** for raise slots; if you add action kinds or change raise semantics, keep that helper aligned with **`legal_actions_for_view`** in **`app/legal_actions.py`** (re-exported from **`app/strategies.py`**) so illegal flags match the engine. If the hand FSM gains new nodes or endings, extend **`DecisionPhase`** / **`decision_phase`** in **`app/actor_view.py`** and **`_build_view`** as needed, then update **`hotseat_action_completes_hand`** so the post-move pause text (handoff vs hand results) stays correct.
8. **Throughput** (optional): If you materially change the hand or strategy hot path, re-check **`scripts/benchmark_hands.py`** with fixed **`--hands`** / **`--seed`** before vs after (see the **run-benchmarks** skill).

## Constraints

- Preserve **injected RNG** for determinism.
- Prefer **config-driven** values over magic numbers.

## PR / commit note

One short paragraph: rule change, config keys, tests added.
