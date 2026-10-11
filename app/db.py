"""Database models (SQLite via SQLAlchemy).

A teaching *session* (one meeting of a class) holds one or more *phases*:
the opening check-in, any mid-class checks, and an optional check-out.
Students record one *check-in* per phase.
"""

from datetime import datetime, timezone

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    create_engine,
    event,
    select,
)
from sqlalchemy.types import TypeDecorator
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, relationship, sessionmaker


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class AwareDateTime(TypeDecorator):
    """SQLite drops tzinfo; store naive UTC and hand back aware UTC."""

    impl = DateTime
    cache_ok = True

    def process_bind_param(self, value, dialect):
        if value is not None and value.tzinfo is not None:
            value = value.astimezone(timezone.utc).replace(tzinfo=None)
        return value

    def process_result_value(self, value, dialect):
        if value is not None:
            value = value.replace(tzinfo=timezone.utc)
        return value


class Base(DeclarativeBase):
    pass


class Setting(Base):
    __tablename__ = "settings"
    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    value: Mapped[str] = mapped_column(Text, default="")


class User(Base):
    __tablename__ = "users"
    email: Mapped[str] = mapped_column(String(320), primary_key=True)
    name: Mapped[str] = mapped_column(String(200), default="")
    created_at: Mapped[datetime] = mapped_column(AwareDateTime, default=utcnow)
    last_login_at: Mapped[datetime | None] = mapped_column(AwareDateTime, nullable=True)


class LoginCode(Base):
    __tablename__ = "login_codes"
    email: Mapped[str] = mapped_column(String(320), primary_key=True)
    code_hash: Mapped[str] = mapped_column(String(128))
    expires_at: Mapped[datetime] = mapped_column(AwareDateTime)
    sent_at: Mapped[datetime] = mapped_column(AwareDateTime, default=utcnow)
    attempts: Mapped[int] = mapped_column(Integer, default=0)


class ClassSession(Base):
    __tablename__ = "sessions"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    teacher_email: Mapped[str] = mapped_column(String(320), index=True)
    class_name: Mapped[str] = mapped_column(String(200), default="")
    email_report: Mapped[bool] = mapped_column(Boolean, default=True)
    email_students: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(AwareDateTime, default=utcnow)
    closed_at: Mapped[datetime | None] = mapped_column(AwareDateTime, nullable=True)

    phases: Mapped[list["Phase"]] = relationship(
        back_populates="session", order_by="Phase.position", cascade="all, delete-orphan"
    )

    @property
    def is_closed(self) -> bool:
        return self.closed_at is not None

    @property
    def active_phase(self) -> "Phase | None":
        for p in self.phases:
            if p.state in ("open", "paused"):
                return p
        return None


PHASE_KINDS = ("checkin", "mid", "checkout")
PHASE_STATES = ("pending", "open", "paused", "closed")


class Phase(Base):
    __tablename__ = "phases"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    session_id: Mapped[int] = mapped_column(ForeignKey("sessions.id", ondelete="CASCADE"), index=True)
    kind: Mapped[str] = mapped_column(String(16))
    label: Mapped[str] = mapped_column(String(100))
    position: Mapped[int] = mapped_column(Integer, default=0)
    state: Mapped[str] = mapped_column(String(16), default="pending")
    opened_at: Mapped[datetime | None] = mapped_column(AwareDateTime, nullable=True)
    closed_at: Mapped[datetime | None] = mapped_column(AwareDateTime, nullable=True)

    session: Mapped[ClassSession] = relationship(back_populates="phases")
    checkins: Mapped[list["CheckIn"]] = relationship(
        back_populates="phase", order_by="CheckIn.created_at", cascade="all, delete-orphan"
    )


class CheckIn(Base):
    __tablename__ = "checkins"
    __table_args__ = (UniqueConstraint("phase_id", "email"),)
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    phase_id: Mapped[int] = mapped_column(ForeignKey("phases.id", ondelete="CASCADE"), index=True)
    email: Mapped[str] = mapped_column(String(320), index=True)
    name: Mapped[str] = mapped_column(String(200), default="")
    created_at: Mapped[datetime] = mapped_column(AwareDateTime, default=utcnow)

    phase: Mapped[Phase] = relationship(back_populates="checkins")


class Database:
    def __init__(self, path):
        path.parent.mkdir(parents=True, exist_ok=True)
        self.engine = create_engine(
            f"sqlite:///{path}", connect_args={"check_same_thread": False, "timeout": 30}
        )

        @event.listens_for(self.engine, "connect")
        def _pragmas(conn, _record):
            cur = conn.cursor()
            cur.execute("PRAGMA journal_mode=WAL")
            cur.execute("PRAGMA foreign_keys=ON")
            cur.close()

        Base.metadata.create_all(self.engine)
        self.Session = sessionmaker(self.engine, expire_on_commit=False)

    def session(self) -> Session:
        return self.Session()


__all__ = [
    "Base",
    "Setting",
    "User",
    "LoginCode",
    "ClassSession",
    "Phase",
    "CheckIn",
    "Database",
    "PHASE_KINDS",
    "PHASE_STATES",
    "utcnow",
    "select",
]
