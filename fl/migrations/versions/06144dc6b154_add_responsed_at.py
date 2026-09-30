"""add_responsed_at

Revision ID: 06144dc6b154
Revises: 4f89cad1ab2e
Create Date: 2026-09-30 19:03:26.599530

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '06144dc6b154'
down_revision: Union[str, Sequence[str], None] = '4f89cad1ab2e'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None



def upgrade() -> None:
    op.add_column(
        "job_data",
        sa.Column(
            "responded_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
    )


def downgrade() -> None:
    op.drop_column(
        "job_data",
        "responded_at",
    )