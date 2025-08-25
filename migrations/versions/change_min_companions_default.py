"""Change min_companions default to 0

Revision ID: change_min_companions_default
Revises: 8c45d646d917
Create Date: 2025-08-25 11:08:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'change_min_companions_default'
down_revision = '8c45d646d917'
branch_labels = None
depends_on = None


def upgrade():
    # Change the default value for new entries
    op.alter_column('walking_bus', 'min_companions',
               existing_type=sa.INTEGER(),
               server_default='0')
    
    # Update existing entries that have the old default value of 2 to 0
    op.execute("UPDATE walking_bus SET min_companions = 0 WHERE min_companions = 2")


def downgrade():
    # Revert to old default
    op.alter_column('walking_bus', 'min_companions',
               existing_type=sa.INTEGER(),
               server_default='2')
    
    # Update existing entries back to 2
    op.execute("UPDATE walking_bus SET min_companions = 2 WHERE min_companions = 0")
