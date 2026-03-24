"""initial schema

Revision ID: 001_initial
Revises:
Create Date: 2026-03-24

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "001_initial"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# CREATE TYPE 전용 (테이블 정의에서는 create_type=False 로 같은 name만 참조)
_application_status_create = postgresql.ENUM(
    "completed",
    "cancelled",
    "forced_assign",
    name="application_status",
)
_sync_run_status_create = postgresql.ENUM("success", "failure", name="sync_run_status")
_admin_log_action_create = postgresql.ENUM(
    "sync_sheets",
    "force_assign",
    "cancel_application",
    "settings_update",
    "club_update",
    name="admin_log_action",
)

# 테이블 컬럼용: 타입은 위에서 이미 생성됨
application_status = postgresql.ENUM(
    "completed",
    "cancelled",
    "forced_assign",
    name="application_status",
    create_type=False,
)
sync_run_status = postgresql.ENUM("success", "failure", name="sync_run_status", create_type=False)
admin_log_action = postgresql.ENUM(
    "sync_sheets",
    "force_assign",
    "cancel_application",
    "settings_update",
    "club_update",
    name="admin_log_action",
    create_type=False,
)


def upgrade() -> None:
    bind = op.get_bind()
    _application_status_create.create(bind, checkfirst=True)
    _sync_run_status_create.create(bind, checkfirst=True)
    _admin_log_action_create.create(bind, checkfirst=True)

    op.create_table(
        "admin_users",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("username", sa.String(length=64), nullable=False),
        sa.Column("password_hash", sa.String(length=256), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("username"),
    )
    op.create_table(
        "clubs",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("club_code", sa.String(length=32), nullable=False),
        sa.Column("club_name", sa.String(length=128), nullable=False),
        sa.Column("teacher_name", sa.String(length=64), nullable=True),
        sa.Column("capacity", sa.Integer(), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("is_open", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_clubs_club_code"), "clubs", ["club_code"], unique=True)
    op.create_table(
        "students",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("student_number", sa.String(length=32), nullable=False),
        sa.Column("name", sa.String(length=64), nullable=False),
        sa.Column("grade", sa.Integer(), nullable=True),
        sa.Column("class_no", sa.Integer(), nullable=True),
        sa.Column("attendance_no", sa.Integer(), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_students_student_number"), "students", ["student_number"], unique=True)
    op.create_table(
        "application_settings",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("singleton_key", sa.String(length=16), nullable=False),
        sa.Column("application_starts_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("application_ends_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("is_globally_closed", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("singleton_key"),
    )
    op.create_table(
        "sync_runs",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("status", sync_run_status, nullable=False),
        sa.Column("message", sa.Text(), nullable=True),
        sa.Column("students_upserted", sa.Integer(), nullable=False),
        sa.Column("clubs_upserted", sa.Integer(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "applications",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("student_id", sa.Integer(), nullable=False),
        sa.Column("club_id", sa.Integer(), nullable=False),
        sa.Column("applied_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("status", application_status, nullable=False),
        sa.Column("assigned_by_admin_id", sa.Integer(), nullable=True),
        sa.Column("assign_reason", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(["assigned_by_admin_id"], ["admin_users.id"]),
        sa.ForeignKeyConstraint(["club_id"], ["clubs.id"]),
        sa.ForeignKeyConstraint(["student_id"], ["students.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "admin_logs",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("admin_id", sa.Integer(), nullable=True),
        sa.Column("action_type", admin_log_action, nullable=False),
        sa.Column("target_student_id", sa.Integer(), nullable=True),
        sa.Column("target_club_id", sa.Integer(), nullable=True),
        sa.Column("action_time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("note", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(["admin_id"], ["admin_users.id"]),
        sa.ForeignKeyConstraint(["target_club_id"], ["clubs.id"]),
        sa.ForeignKeyConstraint(["target_student_id"], ["students.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "application_attempts",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("student_id", sa.Integer(), nullable=False),
        sa.Column("club_id", sa.Integer(), nullable=True),
        sa.Column("attempted_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("failure_reason", sa.String(length=128), nullable=False),
        sa.ForeignKeyConstraint(["club_id"], ["clubs.id"]),
        sa.ForeignKeyConstraint(["student_id"], ["students.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.execute(
        """
        CREATE UNIQUE INDEX uq_applications_one_active_student
        ON applications (student_id)
        WHERE status IN ('completed', 'forced_assign')
        """
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS uq_applications_one_active_student")
    op.drop_table("application_attempts")
    op.drop_table("admin_logs")
    op.drop_table("applications")
    op.drop_table("sync_runs")
    op.drop_table("application_settings")
    op.drop_index(op.f("ix_students_student_number"), table_name="students")
    op.drop_table("students")
    op.drop_index(op.f("ix_clubs_club_code"), table_name="clubs")
    op.drop_table("clubs")
    op.drop_table("admin_users")
    bind = op.get_bind()
    _admin_log_action_create.drop(bind, checkfirst=True)
    _sync_run_status_create.drop(bind, checkfirst=True)
    _application_status_create.drop(bind, checkfirst=True)
