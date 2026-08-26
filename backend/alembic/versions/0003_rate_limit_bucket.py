"""add shared database rate limit bucket"""

from alembic import op
import sqlalchemy as sa

revision = "0003_rate_limit_bucket"
down_revision = "0002_review_sequences_tokens"
branch_labels = None
depends_on = None


def upgrade():
    if "rate_limit_buckets" not in sa.inspect(op.get_bind()).get_table_names():
        op.create_table(
            "rate_limit_buckets",
            sa.Column("key", sa.String(length=180), primary_key=True),
            sa.Column("window_started_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("request_count", sa.Integer(), nullable=False, server_default="0"),
        )


def downgrade():
    op.drop_table("rate_limit_buckets")
