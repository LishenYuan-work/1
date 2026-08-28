"""allow Supabase Auth-managed profiles without a local password hash"""

from alembic import op
import sqlalchemy as sa

revision = "0004_supabase_auth"
down_revision = "0003_rate_limit_bucket"
branch_labels = None
depends_on = None


def upgrade():
    inspector = sa.inspect(op.get_bind())
    columns = {column["name"]: column for column in inspector.get_columns("profiles")}
    password = columns.get("password_hash")
    if password and not password.get("nullable", False):
        op.alter_column("profiles", "password_hash", existing_type=sa.String(length=255), nullable=True)


def downgrade():
    # Existing Supabase-managed rows may have NULL password_hash values.
    pass
