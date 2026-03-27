"""add_document_permissions

Revision ID: d4e6f8b01c23
Revises: c3d5f7a89b12
Create Date: 2026-03-25 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

# revision identifiers, used by Alembic.
revision: str = 'd4e6f8b01c23'
down_revision: Union[str, None] = 'c3d5f7a89b12'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('documents', sa.Column('permissions', JSONB, nullable=True))


def downgrade() -> None:
    op.drop_column('documents', 'permissions')
