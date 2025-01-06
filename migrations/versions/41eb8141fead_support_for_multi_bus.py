"""Support for multi bus

Revision ID: 41eb8141fead
Revises: 398d1f1b8abd
Create Date: 2025-01-06 18:01:10.943533

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '41eb8141fead'
down_revision = '398d1f1b8abd'
branch_labels = None
depends_on = None


def upgrade():
    # Create walking_bus table
    op.create_table('walking_bus',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(100), nullable=False),
        sa.Column('password', sa.String(100), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )
    
    # Add walking_bus_id to existing tables
    op.add_column('station', sa.Column('walking_bus_id', sa.Integer(), nullable=True))
    op.add_column('participant', sa.Column('walking_bus_id', sa.Integer(), nullable=True))
    # Add to other tables...
    
    # Create foreign key constraints
    op.create_foreign_key(None, 'station', 'walking_bus', ['walking_bus_id'], ['id'])
    op.create_foreign_key(None, 'participant', 'walking_bus', ['walking_bus_id'], ['id'])
    
    # Create default walking bus and update existing records
    default_bus = op.inline_literal(1)  # ID for default bus
    op.execute("INSERT INTO walking_bus (id, name, password) VALUES (1, 'Default Bus', 'default_password')")
    op.execute(f"UPDATE station SET walking_bus_id = {default_bus}")
    op.execute(f"UPDATE participant SET walking_bus_id = {default_bus}")
    
    # Make columns non-nullable after data migration
    op.alter_column('station', 'walking_bus_id', nullable=False)
    op.alter_column('participant', 'walking_bus_id', nullable=False)

def downgrade():
    # Remove foreign key constraints
    op.drop_constraint(None, 'station', type_='foreignkey')
    op.drop_constraint(None, 'participant', type_='foreignkey')
    
    # Remove walking_bus_id columns
    op.drop_column('station', 'walking_bus_id')
    op.drop_column('participant', 'walking_bus_id')
    
    # Drop walking_bus table
    op.drop_table('walking_bus')
