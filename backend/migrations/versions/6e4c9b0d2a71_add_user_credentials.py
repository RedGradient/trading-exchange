"""Add credentials while preserving existing users."""

from alembic import op
import sqlalchemy as sa

revision = "6e4c9b0d2a71"
down_revision = "19fd7ee6e5a2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("users", sa.Column("username", sa.String(64), nullable=True))
    op.add_column("users", sa.Column("password_hash", sa.String(256), nullable=True))
    op.create_unique_constraint("uq_users_username", "users", ["username"])
    # Demo users may have been inserted with explicit IDs, bypassing the sequence.
    op.execute(
        "SELECT setval(pg_get_serial_sequence('users', 'id'), "
        "GREATEST(COALESCE((SELECT MAX(id) FROM users), 0), "
        "nextval(pg_get_serial_sequence('users', 'id'))))"
    )


def downgrade() -> None:
    op.drop_constraint("uq_users_username", "users", type_="unique")
    op.drop_column("users", "password_hash")
    op.drop_column("users", "username")
