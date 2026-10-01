"""Database schema. All timestamps are naive UTC (converted at the API edge)."""
import enum
from datetime import datetime, timezone

from sqlalchemy import (Boolean, Column, DateTime, Float, ForeignKey, Integer,
                        String, Table, Text)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .database import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


class JourneyStatus(str, enum.Enum):
    ACTIVE = "ACTIVE"
    COMPLETED = "COMPLETED"
    EMERGENCY = "EMERGENCY"
    CANCELLED = "CANCELLED"


class Consent(str, enum.Enum):
    PENDING = "PENDING"
    CONFIRMED = "CONFIRMED"
    DECLINED = "DECLINED"


# many-to-many: which contacts were chosen for which journey
journey_contacts = Table(
    "journey_contacts",
    Base.metadata,
    Column("journey_id", ForeignKey("journeys.id", ondelete="CASCADE"), primary_key=True),
    Column("contact_id", ForeignKey("contacts.id", ondelete="CASCADE"), primary_key=True),
)


class User(Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(80))
    email: Mapped[str] = mapped_column(String(254), unique=True, index=True)
    phone: Mapped[str | None] = mapped_column(String(20), nullable=True)
    password_hash: Mapped[str] = mapped_column(String(200))
    safe_pin_hash: Mapped[str | None] = mapped_column(String(200), nullable=True)
    duress_pin_hash: Mapped[str | None] = mapped_column(String(200), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)

    contacts = relationship("Contact", back_populates="owner", cascade="all, delete-orphan")
    journeys = relationship("Journey", back_populates="owner", cascade="all, delete-orphan")


class Contact(Base):
    """A trusted person. They do NOT need an account: they get an SMS with a private link."""
    __tablename__ = "contacts"
    id: Mapped[int] = mapped_column(primary_key=True)
    owner_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(80))
    phone: Mapped[str] = mapped_column(String(20))
    relationship_label: Mapped[str | None] = mapped_column(String(40), nullable=True)
    priority: Mapped[int] = mapped_column(Integer, default=1)  # 1 = alerted first, 2 = escalation
    consent: Mapped[str] = mapped_column(String(12), default=Consent.PENDING.value)
    view_token: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    telegram_chat_id: Mapped[str | None] = mapped_column(String(32), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)

    @property
    def telegram_connected(self) -> bool:      # exposed to the app; the chat id itself never is
        return bool(self.telegram_chat_id)

    owner = relationship("User", back_populates="contacts")
    journeys = relationship("Journey", secondary=journey_contacts, back_populates="contacts")


class Journey(Base):
    __tablename__ = "journeys"
    id: Mapped[int] = mapped_column(primary_key=True)
    owner_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    destination: Mapped[str] = mapped_column(String(200))
    expected_arrival_at: Mapped[datetime] = mapped_column(DateTime)
    status: Mapped[str] = mapped_column(String(12), default=JourneyStatus.ACTIVE.value, index=True)
    escalation_stage: Mapped[int] = mapped_column(Integer, default=0)
    share_location: Mapped[bool] = mapped_column(Boolean, default=False)
    duress_triggered: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    owner = relationship("User", back_populates="journeys")
    contacts = relationship("Contact", secondary=journey_contacts, back_populates="journeys")
    points = relationship("LocationPoint", back_populates="journey", cascade="all, delete-orphan")


class LocationPoint(Base):
    __tablename__ = "location_points"
    id: Mapped[int] = mapped_column(primary_key=True)
    journey_id: Mapped[int] = mapped_column(ForeignKey("journeys.id", ondelete="CASCADE"), index=True)
    lat: Mapped[float] = mapped_column(Float)
    lng: Mapped[float] = mapped_column(Float)
    accuracy: Mapped[float | None] = mapped_column(Float, nullable=True)
    recorded_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, index=True)

    journey = relationship("Journey", back_populates="points")


class Event(Base):
    """Append-only audit trail: what was sent, to whom, when."""
    __tablename__ = "events"
    id: Mapped[int] = mapped_column(primary_key=True)
    owner_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    journey_id: Mapped[int | None] = mapped_column(ForeignKey("journeys.id", ondelete="SET NULL"), nullable=True)
    contact_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    type: Mapped[str] = mapped_column(String(30), index=True)
    detail: Mapped[str] = mapped_column(Text, default="")
    lat: Mapped[float | None] = mapped_column(Float, nullable=True)
    lng: Mapped[float | None] = mapped_column(Float, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, index=True)
