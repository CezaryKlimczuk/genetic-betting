"""Derive legal actions from an :class:`~app.actor_view.ActorView`.

Single source of truth for what actions are consistent with ``ActorView`` flags.
The hand engine in ``app.hand`` builds views with the same flags it uses here for
validation.
"""

from __future__ import annotations

from app.actions import Action
from app.actor_view import ActorView


def legal_actions_for_view(view: ActorView) -> list[Action]:
    """List legal actions for this view, in stable menu order.

    Order: fold (if allowed), check (if allowed), call (if allowed), then raises
    from ``raise_amount_min`` through ``raise_amount_max`` inclusive (if
    ``can_raise``).

    Matches the engine when ``can_fold`` reflects the active node (notably
    Player 2 after Player 1 checked may not fold).
    """
    actions: list[Action] = []
    if view.can_fold:
        actions.append(Action.fold())
    if view.can_check:
        actions.append(Action.check())
    if view.can_call:
        actions.append(Action.call())
    if view.can_raise:
        if view.raise_amount_min is None or view.raise_amount_max is None:
            raise ValueError("can_raise requires raise_amount_min/max.")
        actions.extend(
            Action.raise_(a)
            for a in range(view.raise_amount_min, view.raise_amount_max + 1)
        )
    return actions
