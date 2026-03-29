---
name: Hand engine refactors
overview: "Sequenced, behavior-preserving refactors: deduplicate showdown logic and pot awards in `play_hand`, unify strategy typing, then single-source legal actions between engine and strategies; optional follow-ups for CLI FSM coupling and a GA-friendly observation helper."
todos:
  - id: phase1-showdown
    content: Extract showdown/pot award helpers in app/hand.py; keep behavior identical; run pytest
    status: completed
  - id: phase2-strategy-type
    content: Unify Strategy / StrategyFn (single canonical type + re-exports); update match/strategies imports
    status: completed
  - id: phase3-legal-unify
    content: Move legal_actions_for_view to neutral module if needed; drive play_hand validation from it; remove _legal_actions_*; add table/characterization tests
    status: completed
  - id: phase4-decision-tag
    content: (Optional) Add ActorView decision phase; simplify hotseat_action_completes_hand; fix test fixtures
    status: completed
  - id: phase5-observation
    content: (Optional) Add as_observation(view) for GA/batch encoders without touching engine math
    status: completed
isProject: false
---

# Refactoring plan: hand engine and policy seams

## Scope and guardrails

- **Contract:** Existing tests plus `[AGENTS.md](/home/cez/coding/genetic-betting/AGENTS.md)` semantics (refunds, truncate-and-refund, showdown tie = even pot / even split, seeded `random.Random`, no logging on hot path).
- **Verification:** `uv run pytest` after each phase; run `[scripts/benchmark_hands.py](/home/cez/coding/genetic-betting/scripts/benchmark_hands.py)` after Phase 1–2 if you want throughput regression signal (optional).
- **Out of scope for initial phases:** New game rules, batch NN training pipelines, or large renames unrelated to these seams.

## Current pain (mental model)

```mermaid
flowchart LR
  subgraph hand [app/hand.py]
    play_hand[play_hand FSM]
    legal_inline[_p1_first / _facing_extra]
    build[_build_view]
    play_hand --> legal_inline
    play_hand --> build
  end
  subgraph strategies [app/strategies.py]
    legal_view[legal_actions_for_view]
  end
  legal_inline -. duplicate rule knowledge .- legal_view
  cli [app/cli.py hotseat_action_completes_hand]
  build -. mirrored by booleans .- cli
```



---

## Phase 1: Deduplicate showdown / pot resolution in `[app/hand.py](/home/cez/coding/genetic-betting/app/hand.py)`

**Goal:** Shrink `play_hand` (~L212+) by removing repeated tie/win/split/fold-winner blocks.

**Approach:**

- Identify every path that ends in **showdown** or **pot award** (winner or split) and the **fold** winner paths.
- Extract one or two private helpers, e.g. `_resolve_showdown(...)` and/or `_finish_hand_fold(winner, ...)` that call existing `[_award_pot_winner](/home/cez/coding/genetic-betting/app/hand.py)`, `[_award_split_pot](/home/cez/coding/genetic-betting/app/hand.py)`, and build a single `[HandResult](/home/cez/coding/genetic-betting/app/hand.py)` constructor pattern.
- Keep **all** money movement and refund ordering inside helpers already used today (`_apply_refund_if_mismatch`, truncate helpers); only **restructure control flow**, do not change math.

**Risk:** Low if diffs are mechanical and tests already cover branches.

---

## Phase 2: Unify `Strategy` typing (`[app/hand.py](/home/cez/coding/genetic-betting/app/hand.py)` L34 vs `[app/strategies.py](/home/cez/coding/genetic-betting/app/strategies.py)` L12)

**Goal:** One public name for `Callable[[random.Random, ActorView], Action]`; remove import confusion.

**Approach (pick one, stay consistent with repo style):**

- Define `Strategy` once (e.g. keep in `hand.py` as canonical engine type, or move to a tiny `app/types.py` if you want zero `hand` ↔ `strategies` import cycles—today there is likely no cycle).
- Re-export or alias: `StrategyFn = Strategy` in `strategies.py` for backward compatibility, or replace `StrategyFn` with `Strategy` and update `[HotseatStrategy.__init__](/home/cez/coding/genetic-betting/app/strategies.py)` annotation.
- Update `[app/match.py](/home/cez/coding/genetic-betting/app/match.py)` imports if the canonical symbol moves.

**Risk:** Very low (typing/import-only).

---

## Phase 3: Single source for legal actions (highest payoff vs duplication)

**Goal:** After each `[_build_view](/home/cez/coding/genetic-betting/app/hand.py)` (L100+), derive `**legal = legal_actions_for_view(view)`** and validate `action in legal` instead of maintaining `[_legal_actions_p1_first](/home/cez/coding/genetic-betting/app/hand.py)`, `[_legal_actions_facing_extra](/home/cez/coding/genetic-betting/app/hand.py)`, and the inline `legal2b`-style list in `play_hand`.

**Dependency / import direction:**

- Prefer moving `[legal_actions_for_view](/home/cez/coding/genetic-betting/app/strategies.py)` to a neutral module e.g. `**app/legal_actions.py`** (or `app/policy_support.py`) that imports only `ActorView` + `Action`, then:
  - `hand.py` imports from there for validation.
  - `strategies.py` re-exports for public API stability.

**Tests:**

- Extend `[tests/test_strategies.py](/home/cez/coding/genetic-betting/tests/test_strategies.py)` and/or `[tests/test_hand.py](/home/cez/coding/genetic-betting/tests/test_hand.py)` with a **table-driven** check: for each documented betting node, build an `ActorView` (via existing test patterns or minimal fixtures) and assert the legal set matches what the engine previously enforced—especially **P2 after P1 check** (fold excluded when `can_fold` is false) per existing `[test_legal_actions_after_check_line_excludes_fold_when_can_fold_false](/home/cez/coding/genetic-betting/tests/test_strategies.py)`.
- Optionally assert **ordering** matches engine expectations if any code assumes list order (e.g. `RandomLegalStrategy` only needs non-empty set; confirm).

**Risk:** Medium—must preserve edge cases (raise bounds, all-in-facing amounts). Mitigate with full pytest green and one new characterization test if any branch is ambiguous.

---

## Phase 4 (optional): CLI “completes hand” without re-deriving FSM

**Goal:** Replace boolean logic in `[hotseat_action_completes_hand](/home/cez/coding/genetic-betting/app/cli.py)` (L80–99) with a field set only in `[_build_view](/home/cez/coding/genetic-betting/app/hand.py)`, e.g. `decision_phase: Literal["p1_open", "p2_facing_raise", "p2_after_check", "p1_facing_raise"]` on `[ActorView](/home/cez/coding/genetic-betting/app/actor_view.py)`.

**Steps:**

- Add field to `ActorView` + `from_config` / factory paths; update all construction sites (tests that build views manually: `[tests/test_cli.py](/home/cez/coding/genetic-betting/tests/test_cli.py)`, `[tests/test_actions_and_actor_view.py](/home/cez/coding/genetic-betting/tests/test_actions_and_actor_view.py)` if applicable).
- Implement completion as a small table `(phase, action_kind) -> bool` or explicit match, then keep `[test_hotseat_action_completes_hand_matches_fsm](/home/cez/coding/genetic-betting/tests/test_cli.py)` green.

**Risk:** Low–medium (API surface change on `ActorView`).

---

## Phase 5 (optional, GA prep): Observation adapter

**Goal:** Stable numeric feature vector or compact frozen dataclass for batch encoders, **without** moving betting logic out of `play_hand`.

**Approach:** Add `as_observation(view: ActorView) -> ...` next to strategies or in `actor_view.py`, documented as best-effort for training; engine remains authoritative for money and legality.

**Risk:** Low if pure function and unused in core loop initially.

---

## Recommended sequence and checkpoints


| Step | Deliverable                                  | Checkpoint                                  |
| ---- | -------------------------------------------- | ------------------------------------------- |
| 1    | Showdown/award helpers in `hand.py`          | `pytest` green; `play_hand` visibly shorter |
| 2    | Single `Strategy` type                       | `pytest` green                              |
| 3    | `legal_actions_for_view` + delete `_legal_`* | `pytest` green; optional new table test     |
| 4    | `ActorView.decision_phase` + CLI             | `pytest` especially `test_cli.py`           |
| 5    | `as_observation`                             | `pytest` green; no benchmark regression     |


Defer Phase 5 until you start encoding batches; Phases 1–3 are the core “less patchy, more scalable” win.