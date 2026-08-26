"""add atomic sequence counters and token revocation version"""

from alembic import op
import sqlalchemy as sa

revision = "0002_review_sequences_tokens"
down_revision = "0001_review_platform"
branch_labels = None
depends_on = None


def upgrade():
    inspector = sa.inspect(op.get_bind())
    if "token_version" not in {column["name"] for column in inspector.get_columns("profiles")}:
        op.add_column("profiles", sa.Column("token_version", sa.Integer(), nullable=False, server_default="0"))
    session_columns = {column["name"] for column in inspector.get_columns("review_sessions")}
    if "next_event_sequence" not in session_columns:
        op.add_column("review_sessions", sa.Column("next_event_sequence", sa.Integer(), nullable=False, server_default="0"))
    if "next_output_sequence" not in session_columns:
        op.add_column("review_sessions", sa.Column("next_output_sequence", sa.Integer(), nullable=False, server_default="0"))
    op.execute(sa.text("UPDATE review_sessions SET next_event_sequence = COALESCE((SELECT MAX(sequence) FROM review_events WHERE review_events.session_id = review_sessions.id), 0)"))
    op.execute(sa.text("UPDATE review_sessions SET next_output_sequence = COALESCE((SELECT MAX(sequence) FROM review_outputs WHERE review_outputs.session_id = review_sessions.id), 0)"))


def downgrade():
    # These columns are part of the canonical 0001 model as well; removing
    # them would leave the application model incompatible after downgrade.
    pass
