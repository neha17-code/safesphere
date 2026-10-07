"""Which alert channels are actually set up on this server (so the app can show real progress)."""
from fastapi import APIRouter, Depends

from .. import alerts as alerts_mod
from ..deps import current_user
from ..models import User
from ..notifier import ConsoleNotifier

router = APIRouter(prefix="/status", tags=["status"])


@router.get("/channels")
def channels(_: User = Depends(current_user)):
    return {"email": alerts_mod.emailer is not None,
            "sms": not isinstance(alerts_mod.notifier, ConsoleNotifier),
            "push": alerts_mod.pusher is not None}
