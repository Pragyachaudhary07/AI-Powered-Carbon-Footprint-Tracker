"""add users table and prediction_history.user_id

Revision ID: cc304e3d4c19
Revises: 
Create Date: 2026-09-10 12:26:40.682328

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'cc304e3d4c19'
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing_tables = inspector.get_table_names()

    # A brand-new database has no tables at all yet — app.py's db.create_all()
    # already builds both tables from the current models on first run, so
    # there is nothing for this migration to do there. This migration exists
    # for the other case: a database created by the Phase 1 app, which has
    # prediction_history but no concept of users yet.
    if "users" not in existing_tables:
        op.create_table(
            "users",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("name", sa.String(length=120), nullable=False),
            sa.Column("email", sa.String(length=255), nullable=False),
            sa.Column("password_hash", sa.String(length=255), nullable=False),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("email"),
        )
        with op.batch_alter_table("users", schema=None) as batch_op:
            batch_op.create_index(batch_op.f("ix_users_email"), ["email"], unique=True)

    if "prediction_history" in existing_tables:
        columns = [c["name"] for c in inspector.get_columns("prediction_history")]
        if "user_id" not in columns:
            # Existing rows predate authentication and have no owner. They're
            # kept (not dropped) but become unreachable through the app's
            # user-scoped queries, so the column must be nullable here even
            # though the ORM model declares it NOT NULL for new rows.
            with op.batch_alter_table("prediction_history", schema=None) as batch_op:
                batch_op.add_column(sa.Column("user_id", sa.Integer(), nullable=True))
                batch_op.create_index(
                    batch_op.f("ix_prediction_history_user_id"), ["user_id"], unique=False
                )
                batch_op.create_foreign_key(
                    "fk_prediction_history_user_id_users", "users", ["user_id"], ["id"]
                )
    # If prediction_history doesn't exist yet either, this is a fresh
    # database and db.create_all() already created it with user_id included.


def downgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing_tables = inspector.get_table_names()

    if "prediction_history" in existing_tables:
        columns = [c["name"] for c in inspector.get_columns("prediction_history")]
        if "user_id" in columns:
            with op.batch_alter_table("prediction_history", schema=None) as batch_op:
                batch_op.drop_constraint("fk_prediction_history_user_id_users", type_="foreignkey")
                batch_op.drop_index(batch_op.f("ix_prediction_history_user_id"))
                batch_op.drop_column("user_id")

    if "users" in existing_tables:
        with op.batch_alter_table("users", schema=None) as batch_op:
            batch_op.drop_index(batch_op.f("ix_users_email"))
        op.drop_table("users")
