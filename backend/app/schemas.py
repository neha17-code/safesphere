"""Request/response models (validation happens here, before any logic runs)."""
from datetime import datetime, timezone
from typing import Annotated

from pydantic import AfterValidator, BaseModel, ConfigDict, EmailStr, Field, PlainSerializer, field_validator

from .security import PHONE_RE, PIN_RE

# naive-UTC datetimes are serialised with a trailing Z so clients parse them as UTC
UtcDt = Annotated[datetime, PlainSerializer(lambda d: d.isoformat() + "Z", return_type=str)]


def to_naive_utc(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        return dt
    return dt.astimezone(timezone.utc).replace(tzinfo=None)


def _normalise_phone(v: str) -> str:
    v = v.replace(" ", "").replace("-", "")
    if not PHONE_RE.match(v):
        raise ValueError("Phone must be in international format, e.g. +919876543210")
    return v


def _optional_phone(v: str | None) -> str | None:
    return _normalise_phone(v) if v else None


Phone = Annotated[str, AfterValidator(_normalise_phone)]
OptionalPhone = Annotated[str | None, AfterValidator(_optional_phone)]


# ---------- auth ----------
class RegisterIn(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    phone: OptionalPhone = None


class LoginIn(BaseModel):
    email: EmailStr
    password: str = Field(max_length=128)


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str
    email: str
    phone: str | None
    has_pins: bool = False


class PinsIn(BaseModel):
    safe_pin: str
    duress_pin: str

    @field_validator("safe_pin", "duress_pin")
    @classmethod
    def _digits(cls, v):
        if not PIN_RE.match(v):
            raise ValueError("PIN must be 4-6 digits")
        return v


# ---------- contacts ----------
class ContactIn(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    phone: Phone
    relationship_label: str | None = Field(default=None, max_length=40)
    priority: int = Field(default=1, ge=1, le=2)
    email: EmailStr | None = None


class ContactOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str
    phone: str
    relationship_label: str | None
    priority: int
    consent: str
    email: str | None = None
    invite_status: str = "NOT_SENT"            # NOT_SENT | SENT | ACCEPTED | DECLINED
    invite_channel: str | None = None
    invite_sent_at: UtcDt | None = None


class OutcomeOut(BaseModel):
    name: str
    ok: bool
    channel: str
    reason: str = ""


class ContactEmailIn(BaseModel):
    email: EmailStr


class InviteOut(BaseModel):
    message: str
    link: str
    whatsapp_url: str


# ---------- journeys ----------
class JourneyIn(BaseModel):
    destination: str = Field(min_length=1, max_length=200)
    expected_arrival_at: datetime
    contact_ids: list[int] = Field(min_length=1, max_length=10)
    share_location: bool = False


class ArriveIn(BaseModel):
    pin: str | None = Field(default=None, max_length=6)


class ExtendIn(BaseModel):
    minutes: int = Field(ge=5, le=720)  # up to 12 h per extension


class LocationIn(BaseModel):
    lat: float = Field(ge=-90, le=90)
    lng: float = Field(ge=-180, le=180)
    accuracy: float | None = Field(default=None, ge=0)


class JourneyOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    destination: str
    expected_arrival_at: UtcDt
    status: str
    escalation_stage: int
    share_location: bool
    contacts: list[ContactOut]


class JourneyStartOut(JourneyOut):
    notified: list[OutcomeOut] = []     # who was told the journey started, and how


class ArriveOut(BaseModel):
    status: str
    completed_at: UtcDt


class AlertIn(BaseModel):
    contact_ids: list[int] | None = None   # None = every confirmed contact
    message: str | None = Field(default=None, max_length=200)
    lat: float | None = Field(default=None, ge=-90, le=90)
    lng: float | None = Field(default=None, ge=-180, le=180)


class AlertOut(BaseModel):
    delivered_to: int
    skipped_unconfirmed: int
    results: list[OutcomeOut] = []


class EventOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    type: str
    detail: str
    created_at: UtcDt
