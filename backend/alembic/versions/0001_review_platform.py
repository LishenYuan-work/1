"""create review platform tables

Revision ID: 0001_review_platform
"""
from alembic import op
from sqlalchemy import text

revision = "0001_review_platform"
down_revision = None
branch_labels = None
depends_on = None

def upgrade():
    # The canonical schema is generated from SQLAlchemy metadata in development.
    # Production uses this migration after setting DATABASE_URL to PostgreSQL.
    from app.db.models import Base
    bind = op.get_bind()
    Base.metadata.create_all(bind=bind)

def downgrade():
    from app.db.models import Base
    Base.metadata.drop_all(bind=op.get_bind())
