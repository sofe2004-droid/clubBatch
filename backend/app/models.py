from __future__ import annotations

import enum
from datetime import datetime
from typing import TYPE_CHECKING, List, Optional

from sqlalchemy import (
    Boolean,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import expression

from app.database import Base

if TYPE_CHECKING:
    pass


class ApplicationStatus(str, enum.Enum):
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    FORCED_ASSIGN = "forced_assign"


class SyncRunStatus(str, enum.Enum):
    SUCCESS = "success"
    FAILURE = "failure"


class AdminLogAction(str, enum.Enum):
    SYNC_SHEETS = "sync_sheets"
    FORCE_ASSIGN = "force_assign"
    CANCEL_APPLICATION = "cancel_application"
    SETTINGS_UPDATE = "settings_update"
    CLUB_UPDATE = "club_update"


def _enum_values(obj: type[enum.Enum]) -> list[str]:
    """PostgreSQL ENUM 라벨은 migration 소문자 값과 일치해야 함(SQLAlchemy 기본은 멤버 *이름*을 보냄)."""
    return [m.value for m in obj]


class Student(Base):
    __tablename__ = "students"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    student_number: Mapped[str] = mapped_column(String(32), unique=True, index=True, nullable=False)
    name: Mapped[str] = mapped_column(String(64), nullable=False)
    grade: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    class_no: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    attendance_no: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    status: Mapped[str] = mapped_column(String(32), default="재학", nullable=False)
    may_self_apply: Mapped[bool] = mapped_column(
        Boolean, server_default=expression.true(), nullable=False
    )

    applications: Mapped[List[Application]] = relationship(back_populates="student")


class Club(Base):
    __tablename__ = "clubs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    club_code: Mapped[str] = mapped_column(String(32), unique=True, index=True, nullable=False)
    club_name: Mapped[str] = mapped_column(String(128), nullable=False)
    teacher_name: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    capacity: Mapped[int] = mapped_column(Integer, nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    is_open: Mapped[bool] = mapped_column(Boolean, server_default=expression.true(), nullable=False)

    applications: Mapped[List[Application]] = relationship(back_populates="club")


class Application(Base):
    __tablename__ = "applications"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    student_id: Mapped[int] = mapped_column(ForeignKey("students.id"), nullable=False)
    club_id: Mapped[int] = mapped_column(ForeignKey("clubs.id"), nullable=False)
    applied_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    status: Mapped[ApplicationStatus] = mapped_column(
        Enum(
            ApplicationStatus,
            name="application_status",
            values_callable=_enum_values,
        ),
        nullable=False,
    )
    assigned_by_admin_id: Mapped[Optional[int]] = mapped_column(ForeignKey("admin_users.id"), nullable=True)
    assign_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    student: Mapped[Student] = relationship(back_populates="applications")
    club: Mapped[Club] = relationship(back_populates="applications")


class AdminUser(Base):
    __tablename__ = "admin_users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    username: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(256), nullable=False)


class AdminLog(Base):
    __tablename__ = "admin_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    admin_id: Mapped[Optional[int]] = mapped_column(ForeignKey("admin_users.id"), nullable=True)
    action_type: Mapped[AdminLogAction] = mapped_column(
        Enum(AdminLogAction, name="admin_log_action", values_callable=_enum_values),
        nullable=False,
    )
    target_student_id: Mapped[Optional[int]] = mapped_column(ForeignKey("students.id"), nullable=True)
    target_club_id: Mapped[Optional[int]] = mapped_column(ForeignKey("clubs.id"), nullable=True)
    action_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    note: Mapped[Optional[str]] = mapped_column(Text, nullable=True)


class SyncRun(Base):
    __tablename__ = "sync_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    finished_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    status: Mapped[SyncRunStatus] = mapped_column(
        Enum(SyncRunStatus, name="sync_run_status", values_callable=_enum_values),
        nullable=False,
    )
    message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    students_upserted: Mapped[int] = mapped_column(Integer, default=0)
    clubs_upserted: Mapped[int] = mapped_column(Integer, default=0)


class ApplicationSettings(Base):
    __tablename__ = "application_settings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    singleton_key: Mapped[str] = mapped_column(String(16), unique=True, nullable=False, default="global")
    application_starts_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    application_ends_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    is_globally_closed: Mapped[bool] = mapped_column(
        Boolean, server_default=expression.false(), nullable=False
    )


class ApplicationAttempt(Base):
    __tablename__ = "application_attempts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    student_id: Mapped[int] = mapped_column(ForeignKey("students.id"), nullable=False)
    club_id: Mapped[Optional[int]] = mapped_column(ForeignKey("clubs.id"), nullable=True)
    attempted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    failure_reason: Mapped[str] = mapped_column(String(128), nullable=False)
