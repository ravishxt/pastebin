from __future__ import annotations

from typing import Iterable

from .models import PasteStatus


class InvalidPasteStateTransition(Exception):
    """Raised when an invalid state transition is requested for a Paste."""


# Explicitly enumerated allowed transitions between distinct states.
_ALLOWED_TRANSITIONS: set[tuple[PasteStatus, PasteStatus]] = {
    (PasteStatus.ACTIVE, PasteStatus.VIEWED),
    (PasteStatus.ACTIVE, PasteStatus.EXPIRED),
    (PasteStatus.VIEWED, PasteStatus.EXPIRED),
    (PasteStatus.ACTIVE, PasteStatus.DELETED),
    (PasteStatus.VIEWED, PasteStatus.DELETED),
}


def _coerce_state(value: PasteStatus | str) -> PasteStatus:
    """Normalize incoming state values to ``PasteStatus``."""
    if isinstance(value, PasteStatus):
        return value
    try:
        return PasteStatus(value)
    except ValueError as exc:
        valid: Iterable[str] = (s.value for s in PasteStatus)
        raise InvalidPasteStateTransition(
            f"Unknown paste state {value!r}. Valid states: {', '.join(valid)}"
        ) from exc


def validate_transition(
    current_state: PasteStatus | str,
    next_state: PasteStatus | str,
) -> None:
    """
    Validate a transition between two Paste states.

    - Allowed transitions:
      ACTIVE → VIEWED, ACTIVE → EXPIRED, VIEWED → EXPIRED,
      ACTIVE → DELETED, VIEWED → DELETED.
    - Forbidden transitions raise ``InvalidPasteStateTransition``.
    - A \"no-op\" transition (``current_state == next_state``) is always allowed.
    """

    current = _coerce_state(current_state)
    target = _coerce_state(next_state)

    # No-op: staying in the same state is permitted.
    if current is target:
        return

    if (current, target) not in _ALLOWED_TRANSITIONS:
        raise InvalidPasteStateTransition(
            f"Cannot transition Paste from {current.value} to {target.value}."
        )

