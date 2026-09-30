"""
Escalation ladder -- the core idea of SafeSphere.

Pure functions only (no database, no clock, no network) so the safety-critical
timing rules can be unit-tested exhaustively.

Timeline for a journey with expected arrival T:

    T                        -> Stage.NUDGED             ask the user "are you safe?"
    T + grace                -> Stage.CONTACTS_ALERTED   priority-1 contacts are told
    T + grace + second_level -> Stage.ESCALATED          everyone is told, urgent wording
"""
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import IntEnum


class Stage(IntEnum):
    NONE = 0
    NUDGED = 1
    CONTACTS_ALERTED = 2
    ESCALATED = 3


@dataclass(frozen=True)
class Policy:
    grace: timedelta = timedelta(minutes=10)
    second_level: timedelta = timedelta(minutes=15)


def target_stage(expected_arrival: datetime, now: datetime, policy: Policy) -> Stage:
    """Which stage SHOULD the journey be in at time `now`?"""
    if now < expected_arrival:
        return Stage.NONE
    if now < expected_arrival + policy.grace:
        return Stage.NUDGED
    if now < expected_arrival + policy.grace + policy.second_level:
        return Stage.CONTACTS_ALERTED
    return Stage.ESCALATED


def pending_transitions(current: Stage, target: Stage) -> list[Stage]:
    """
    Every stage that still has to be executed, in order.
    If the server was down and we jumped from NONE to ESCALATED, the intermediate
    stages are still returned so no alert level is silently skipped.
    """
    if target <= current:
        return []
    return [Stage(s) for s in range(current + 1, target + 1)]
