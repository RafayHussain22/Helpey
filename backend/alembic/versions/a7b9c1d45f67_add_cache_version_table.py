"""add_cache_version_table

Revision ID: a7b9c1d45f67
Revises: f6a8b0c34e56
Create Date: 2026-03-28 20:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'a7b9c1d45f67'
down_revision: Union[str, None] = 'f6a8b0c34e56'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'cache_version',
        sa.Column('id', sa.Integer, primary_key=True),
        sa.Column('version', sa.Integer, nullable=False, server_default='0'),
    )
    op.execute("INSERT INTO cache_version (id, version) VALUES (1, 0)")


def downgrade() -> None:
    op.drop_table('cache_version')
