"""switch users to google oauth: add google_id and avatar_url, drop password_hash

Revision ID: 1435fa7506d1
Revises: cc304e3d4c19
Create Date: 2026-09-10 13:10:39.663277

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '1435fa7506d1'
down_revision = 'cc304e3d4c19'
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if "users" not in inspector.get_table_names():
        # Fresh database — db.create_all() already built "users" from the
        # current (Google-OAuth) model, google_id/avatar_url included and
        # password_hash never existed. Nothing to migrate.
        return

    columns = [c["name"] for c in inspector.get_columns("users")]

    with op.batch_alter_table("users", schema=None) as batch_op:
        if "google_id" not in columns:
            batch_op.add_column(sa.Column("google_id", sa.String(length=255), nullable=True))
            batch_op.create_index(batch_op.f("ix_users_google_id"), ["google_id"], unique=True)
        if "avatar_url" not in columns:
            batch_op.add_column(sa.Column("avatar_url", sa.String(length=512), nullable=True))
        if "password_hash" in columns:
            # No accounts sign in with a password anymore — dropping this
            # does not touch id/name/email/created_at or any user's
            # prediction_history rows, so no data is lost, only the
            # now-unused password column.
            batch_op.drop_column("password_hash")


def downgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if "users" not in inspector.get_table_names():
        return

    columns = [c["name"] for c in inspector.get_columns("users")]

    with op.batch_alter_table("users", schema=None) as batch_op:
        if "password_hash" not in columns:
            # Restored nullable since existing Google-only accounts have no
            # password to backfill.
            batch_op.add_column(sa.Column("password_hash", sa.String(length=255), nullable=True))
        if "avatar_url" in columns:
            batch_op.drop_column("avatar_url")
        if "google_id" in columns:
            batch_op.drop_index(batch_op.f("ix_users_google_id"))
            batch_op.drop_column("google_id")
