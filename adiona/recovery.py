"""External-outcome protocol model ONLY; no connector or dispatch code exists."""
from enum import Enum
from .canonical import Rejected


class ExternalState(str, Enum):
    PREPARED = "PREPARED"
    DISPATCHED = "DISPATCHED"
    UNKNOWN_EXTERNAL_STATE = "UNKNOWN_EXTERNAL_STATE"
    OBSERVED_COMMITTED = "OBSERVED_COMMITTED"
    FAILED_BEFORE_DISPATCH = "FAILED_BEFORE_DISPATCH"
    OBSERVED_NOT_COMMITTED = "OBSERVED_NOT_COMMITTED"


def advance(state: ExternalState, event: str) -> ExternalState:
    """Trusted-harness events; observation authentication is a future adapter duty.

A timeout never releases an old capability. Even observed non-commit requires
a NEW action, fresh warrant, and fresh authorization before another dispatch.
"""
    transitions = {
        (ExternalState.PREPARED, "dispatch"): ExternalState.DISPATCHED,
        (ExternalState.PREPARED, "reject_before_dispatch"): ExternalState.FAILED_BEFORE_DISPATCH,
        (ExternalState.DISPATCHED, "timeout"): ExternalState.UNKNOWN_EXTERNAL_STATE,
        (ExternalState.DISPATCHED, "confirmed_commit"): ExternalState.OBSERVED_COMMITTED,
        (ExternalState.UNKNOWN_EXTERNAL_STATE, "confirmed_commit"): ExternalState.OBSERVED_COMMITTED,
        (ExternalState.UNKNOWN_EXTERNAL_STATE, "confirmed_noncommit"): ExternalState.OBSERVED_NOT_COMMITTED,
    }
    try:
        return transitions[(state, event)]
    except (KeyError, TypeError) as exc:
        raise Rejected("invalid external-state transition; no blind retry or implied rollback") from exc
