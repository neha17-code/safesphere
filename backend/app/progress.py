"""Regular 'still on the way' updates for contacts. Pure functions (no I/O) so they are easy to test."""
from datetime import datetime, timedelta


def progress_due(last: datetime, now: datetime, interval: timedelta) -> bool:
    """True when a new update should go out. A zero/negative interval switches updates off."""
    return interval > timedelta(0) and now - last >= interval


def progress_text(name: str, destination: str, minutes_left: int) -> str:
    if minutes_left > 1:
        return f"{name} is on the way to {destination}. About {minutes_left} min to go."
    if minutes_left >= -1:
        return f"{name} should be arriving at {destination} about now."
    return f"{name} is {-minutes_left} min past the expected arrival at {destination}. Still waiting for their check-in."
