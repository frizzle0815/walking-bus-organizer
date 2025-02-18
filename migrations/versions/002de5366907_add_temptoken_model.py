"""Add TempToken model

Revision ID: 002de5366907
Revises: b5689f23488b
Create Date: 2025-01-15 11:08:09.972650

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '002de5366907'
down_revision = 'b5689f23488b'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.create_table('temp_tokens',
    sa.Column('id', sa.String(length=10), nullable=False),
    sa.Column('expiry', sa.DateTime(), nullable=False),
    sa.Column('walking_bus_id', sa.Integer(), nullable=False),
    sa.Column('walking_bus_name', sa.String(length=100), nullable=False),
    sa.Column('bus_password_hash', sa.String(length=256), nullable=False),
    sa.Column('created_by', sa.Integer(), nullable=False),
    sa.Column('created_at', sa.DateTime(), nullable=True),
    sa.ForeignKeyConstraint(['walking_bus_id'], ['walking_bus.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_table('temp_tokens')
    # ### end Alembic commands ###
