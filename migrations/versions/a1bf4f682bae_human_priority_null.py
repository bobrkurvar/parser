"""human_priority_null

Revision ID: a1bf4f682bae
Revises: e736e157c9ba
Create Date: 2026-08-30 15:39:09.908692

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a1bf4f682bae'
down_revision: Union[str, Sequence[str], None] = 'e736e157c9ba'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade():
    op.alter_column(
        "job_data",
        "priority",
        existing_type=sa.Integer(),
        nullable=True,
    )
    op.execute("UPDATE job_data SET priority = NULL")

def downgrade() -> None:
    """Downgrade schema."""
    pass
