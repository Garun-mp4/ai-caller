"""Add indexes used by lead filtering and call scheduling."""
from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade():
    op.create_index("ix_leads_status_next_call_at", "leads", ["status", "next_call_at"])
    op.create_index("ix_calls_status_started_at", "calls", ["status", "started_at"])
    op.create_index("ix_calls_lead_status", "calls", ["lead_id", "status"])
    op.create_index("ix_callbacks_status_scheduled_at", "callbacks", ["status", "scheduled_at"])


def downgrade():
    op.drop_index("ix_callbacks_status_scheduled_at", table_name="callbacks")
    op.drop_index("ix_calls_lead_status", table_name="calls")
    op.drop_index("ix_calls_status_started_at", table_name="calls")
    op.drop_index("ix_leads_status_next_call_at", table_name="leads")
