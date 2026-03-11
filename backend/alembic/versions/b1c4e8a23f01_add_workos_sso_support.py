"""add_workos_sso_support

Revision ID: b1c4e8a23f01
Revises: 80d3f99c55f2
Create Date: 2026-03-11 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'b1c4e8a23f01'
down_revision: Union[str, None] = '80d3f99c55f2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Make google_id nullable (SSO users won't have one initially)
    op.alter_column('users', 'google_id', existing_type=sa.Text(), nullable=True)

    # Add workos_user_id column
    op.add_column('users', sa.Column('workos_user_id', sa.Text(), nullable=True))
    op.create_unique_constraint('uq_users_workos_user_id', 'users', ['workos_user_id'])


def downgrade() -> None:
    op.drop_constraint('uq_users_workos_user_id', 'users', type_='unique')
    op.drop_column('users', 'workos_user_id')
    op.alter_column('users', 'google_id', existing_type=sa.Text(), nullable=False)
