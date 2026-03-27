"""add_drive_sync_tracking

Revision ID: c3d5f7a89b12
Revises: b1c4e8a23f01
Create Date: 2026-03-24 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'c3d5f7a89b12'
down_revision: Union[str, None] = 'b1c4e8a23f01'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Users: track sync state
    op.add_column('users', sa.Column('initial_sync_done', sa.Boolean(), nullable=False, server_default='false'))
    op.add_column('users', sa.Column('last_sync_at', sa.DateTime(timezone=True), nullable=True))

    # Documents: track Drive modified time for delta sync
    op.add_column('documents', sa.Column('google_modified_time', sa.DateTime(timezone=True), nullable=True))

    # Unique constraint to prevent duplicate Drive files per user
    op.create_unique_constraint('uq_user_google_file', 'documents', ['user_id', 'google_file_id'])


def downgrade() -> None:
    op.drop_constraint('uq_user_google_file', 'documents', type_='unique')
    op.drop_column('documents', 'google_modified_time')
    op.drop_column('users', 'last_sync_at')
    op.drop_column('users', 'initial_sync_done')
