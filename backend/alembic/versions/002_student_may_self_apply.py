"""학생 자율 재신청 허용 플래그 (관리자 배정 삭제 시에만 True)

Revision ID: 002_may_self_apply
Revises: 001_initial
Create Date: 2026-03-24

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "002_may_self_apply"
down_revision: Union[str, None] = "001_initial"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "students",
        sa.Column(
            "may_self_apply",
            sa.Boolean(),
            server_default=sa.text("true"),
            nullable=False,
        ),
    )
    op.execute(
        """
        UPDATE students
        SET may_self_apply = false
        WHERE id IN (
            SELECT student_id FROM applications
            WHERE status IN ('completed', 'forced_assign')
        )
        """
    )


def downgrade() -> None:
    op.drop_column("students", "may_self_apply")
