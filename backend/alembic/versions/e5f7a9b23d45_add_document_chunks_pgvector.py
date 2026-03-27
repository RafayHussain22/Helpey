"""add_document_chunks_pgvector

Revision ID: e5f7a9b23d45
Revises: d4e6f8b01c23
Create Date: 2026-03-25 14:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from pgvector.sqlalchemy import Vector

# revision identifiers, used by Alembic.
revision: str = 'e5f7a9b23d45'
down_revision: Union[str, None] = 'd4e6f8b01c23'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Enable pgvector extension
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    # Create document_chunks table
    op.create_table(
        'document_chunks',
        sa.Column('id', sa.Text(), primary_key=True),
        sa.Column('document_id', sa.Text(), sa.ForeignKey('documents.id', ondelete='CASCADE'), nullable=False),
        sa.Column('chunk_index', sa.Integer(), nullable=False),
        sa.Column('content', sa.Text(), nullable=False),
        sa.Column('embedding', Vector(1536), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # Index on document_id for fast lookups and cascade deletes
    op.create_index('ix_document_chunks_document_id', 'document_chunks', ['document_id'])

    # HNSW index for cosine similarity vector search
    op.execute("""
        CREATE INDEX ix_document_chunks_embedding
        ON document_chunks
        USING hnsw (embedding vector_cosine_ops)
    """)


def downgrade() -> None:
    op.drop_table('document_chunks')
    op.execute("DROP EXTENSION IF EXISTS vector")
