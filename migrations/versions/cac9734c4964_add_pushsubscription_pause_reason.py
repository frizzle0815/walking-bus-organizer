"""Add PushSubscription Pause Reason

Revision ID: cac9734c4964
Revises: 189570fda189
Create Date: 2025-02-12 08:19:04.204513
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.engine.reflection import Inspector

# revision identifiers, used by Alembic.
revision = 'cac9734c4964'
down_revision = '189570fda189'
branch_labels = None
depends_on = None

def upgrade():
    # Check if apscheduler_jobs table exists before trying to drop it
    connection = op.get_bind()
    inspector = Inspector.from_engine(connection)
    tables = inspector.get_table_names()
    
    if 'apscheduler_jobs' in tables:
        op.drop_table('apscheduler_jobs')

    # Add new columns to push_subscription table
    with op.batch_alter_table('push_subscription', schema=None) as batch_op:
        batch_op.add_column(sa.Column('is_active', sa.Boolean(), nullable=True))
        batch_op.add_column(sa.Column('paused_at', sa.DateTime(), nullable=True))
        batch_op.add_column(sa.Column('pause_reason', sa.String(length=500), nullable=True))
        batch_op.add_column(sa.Column('last_error_code', sa.Integer(), nullable=True))

def downgrade():
    with op.batch_alter_table('push_subscription', schema=None) as batch_op:
        batch_op.drop_column('last_error_code')
        batch_op.drop_column('pause_reason')
        batch_op.drop_column('paused_at')
        batch_op.drop_column('is_active')