"""Index call start time for the dashboard's local-day count."""
from alembic import op

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade():
    op.create_index("ix_calls_started_at", "calls", ["started_at"])


def downgrade():
    op.drop_index("ix_calls_started_at", table_name="calls")
