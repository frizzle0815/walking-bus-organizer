"""Add multi bus support

Revision ID: b5689f23488b
Revises: 398d1f1b8abd
Create Date: 2025-01-07 04:24:03.666419

"""
from datetime import time
import sqlalchemy as sa
from alembic import op
from sqlalchemy import text


# revision identifiers, used by Alembic.
revision = 'b5689f23488b'
down_revision = '398d1f1b8abd'
branch_labels = None
depends_on = None


def upgrade():
    # Create walking_bus table first
    op.create_table('walking_bus',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(length=100), nullable=False),
        sa.Column('password', sa.String(length=100), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )
    
    # Create default walking bus
    op.execute("INSERT INTO walking_bus (id, name, password) VALUES (1, 'Default Bus', 'default_password')")
    
    # Set default times
    default_start = time(7, 20).strftime('%H:%M')
    default_end = time(8, 0).strftime('%H:%M')
    
    # Update existing time records
    for day in ['monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday', 'sunday']:
        op.execute(f"UPDATE walking_bus_schedule SET {day}_start = '{default_start}' WHERE {day}_start IS NULL")
        op.execute(f"UPDATE walking_bus_schedule SET {day}_end = '{default_end}' WHERE {day}_end IS NULL")
    
    # Add walking_bus_id to all tables with proper handling
    tables = ['calendar_status', 'daily_note', 'participant', 'station', 
              'walking_bus_schedule', 'walking_bus_override']
              
    for table in tables:
        # Add column as nullable first
        op.add_column(table, sa.Column('walking_bus_id', sa.Integer(), nullable=True))
        # Set default value for existing records
        op.execute(f"UPDATE {table} SET walking_bus_id = 1")
        # Make column non-nullable
        op.alter_column(table, 'walking_bus_id', nullable=False)
        # Add foreign key constraint
        op.create_foreign_key(
            f'{table}_walking_bus_id_fkey',
            table,
            'walking_bus',
            ['walking_bus_id'],
            ['id']
        )
    
    # Make time columns non-nullable with defaults
    with op.batch_alter_table('walking_bus_schedule', schema=None) as batch_op:
        for day in ['monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday', 'sunday']:
            batch_op.alter_column(f'{day}_start',
                                existing_type=sa.Time(),
                                nullable=False,
                                server_default=text(f"'{default_start}'"))
            batch_op.alter_column(f'{day}_end',
                                existing_type=sa.Time(),
                                nullable=False,
                                server_default=text(f"'{default_end}'"))

def downgrade():
    # Drop foreign keys first
    tables = ['calendar_status', 'daily_note', 'participant', 'station', 
              'walking_bus_schedule', 'walking_bus_override']
    
    for table in tables:
        op.drop_constraint(f'{table}_walking_bus_id_fkey', table, type_='foreignkey')
        op.drop_column(table, 'walking_bus_id')
    
    # Make time columns nullable again
    with op.batch_alter_table('walking_bus_schedule', schema=None) as batch_op:
        for day in ['monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday', 'sunday']:
            batch_op.alter_column(f'{day}_start',
                                existing_type=sa.Time(),
                                nullable=True,
                                server_default=None)
            batch_op.alter_column(f'{day}_end',
                                existing_type=sa.Time(),
                                nullable=True,
                                server_default=None)
    
    # Finally drop the walking_bus table
    op.drop_table('walking_bus')


