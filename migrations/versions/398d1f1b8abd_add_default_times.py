"""Add default times

Revision ID: 398d1f1b8abd
Revises: fc8d01e0048b
Create Date: 2025-01-05 21:35:20.043731
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from datetime import time

# revision identifiers, used by Alembic.
revision = '398d1f1b8abd'
down_revision = 'fc8d01e0048b'
branch_labels = None
depends_on = None

def upgrade():
    # First set default values for all NULL fields
    default_start = time(7, 20).strftime('%H:%M')
    default_end = time(8, 0).strftime('%H:%M')
    
    # Update all NULL values with defaults
    for day in ['monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday', 'sunday']:
        op.execute(f"UPDATE walking_bus_schedule SET {day}_start = '{default_start}' WHERE {day}_start IS NULL")
        op.execute(f"UPDATE walking_bus_schedule SET {day}_end = '{default_end}' WHERE {day}_end IS NULL")
    
    # Now we can safely set columns to NOT NULL
    with op.batch_alter_table('walking_bus_schedule', schema=None) as batch_op:
        for day in ['monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday', 'sunday']:
            batch_op.alter_column(f'{day}_start',
                                existing_type=postgresql.TIME(),
                                nullable=False)
            batch_op.alter_column(f'{day}_end',
                                existing_type=postgresql.TIME(),
                                nullable=False)

def downgrade():
    # Original downgrade logic remains unchanged
    with op.batch_alter_table('walking_bus_schedule', schema=None) as batch_op:
        for day in ['monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday', 'sunday']:
            batch_op.alter_column(f'{day}_end',
                                existing_type=postgresql.TIME(),
                                nullable=True)
            batch_op.alter_column(f'{day}_start',
                                existing_type=postgresql.TIME(),
                                nullable=True)
