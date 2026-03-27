"""shared_document_pool

Revision ID: f6a8b0c34e56
Revises: e5f7a9b23d45
Create Date: 2026-03-27 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'f6a8b0c34e56'
down_revision: str = 'e5f7a9b23d45'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # --- Step 1: Deduplicate documents that share the same google_file_id ---
    # For each google_file_id with multiple rows, keep the one with the most chunks
    # (tie-break by earliest created_at). Re-point orphan chunks to the winner, then
    # delete loser rows.
    conn = op.get_bind()

    # Find duplicate google_file_ids (only where google_file_id IS NOT NULL)
    dupes = conn.execute(sa.text("""
        SELECT google_file_id
        FROM documents
        WHERE google_file_id IS NOT NULL
        GROUP BY google_file_id
        HAVING COUNT(*) > 1
    """)).fetchall()

    for (gfid,) in dupes:
        # Pick the winner: highest chunk_count, then earliest created_at
        rows = conn.execute(sa.text("""
            SELECT id FROM documents
            WHERE google_file_id = :gfid
            ORDER BY chunk_count DESC, created_at ASC
        """), {"gfid": gfid}).fetchall()

        winner_id = rows[0][0]
        loser_ids = [r[0] for r in rows[1:]]

        for loser_id in loser_ids:
            # Re-point chunks from loser to winner
            conn.execute(sa.text("""
                UPDATE document_chunks
                SET document_id = :winner
                WHERE document_id = :loser
            """), {"winner": winner_id, "loser": loser_id})

            # Delete the loser document
            conn.execute(sa.text("""
                DELETE FROM documents WHERE id = :loser
            """), {"loser": loser_id})

    # --- Step 2: Delete documents with NULL google_file_id (shouldn't exist, but safety) ---
    conn.execute(sa.text("""
        DELETE FROM documents WHERE google_file_id IS NULL
    """))

    # --- Step 3: Drop old unique constraint and rename column ---
    op.drop_constraint("uq_user_google_file", "documents", type_="unique")

    op.alter_column("documents", "user_id", new_column_name="synced_by_user_id")

    # --- Step 4: Make synced_by_user_id nullable and change FK ondelete ---
    op.alter_column("documents", "synced_by_user_id", nullable=True)

    # Drop the old FK and recreate with SET NULL
    op.drop_constraint("documents_user_id_fkey", "documents", type_="foreignkey")
    op.create_foreign_key(
        "documents_synced_by_user_id_fkey",
        "documents",
        "users",
        ["synced_by_user_id"],
        ["id"],
        ondelete="SET NULL",
    )

    # --- Step 5: Make google_file_id NOT NULL and add unique constraint ---
    op.alter_column("documents", "google_file_id", nullable=False)
    op.create_unique_constraint("uq_google_file", "documents", ["google_file_id"])


def downgrade() -> None:
    # Reverse: drop new constraint, restore old schema
    op.drop_constraint("uq_google_file", "documents", type_="unique")
    op.alter_column("documents", "google_file_id", nullable=True)

    op.drop_constraint("documents_synced_by_user_id_fkey", "documents", type_="foreignkey")
    op.create_foreign_key(
        "documents_user_id_fkey",
        "documents",
        "users",
        ["synced_by_user_id"],
        ["id"],
        ondelete="CASCADE",
    )

    op.alter_column("documents", "synced_by_user_id", nullable=False)
    op.alter_column("documents", "synced_by_user_id", new_column_name="user_id")

    op.create_unique_constraint("uq_user_google_file", "documents", ["user_id", "google_file_id"])
