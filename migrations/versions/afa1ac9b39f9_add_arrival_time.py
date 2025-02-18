"""Add arrival time

Revision ID: afa1ac9b39f9
Revises: de31609f2965
Create Date: 2025-01-17 05:57:33.728131

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'afa1ac9b39f9'
down_revision = 'de31609f2965'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table('station', schema=None) as batch_op:
        batch_op.add_column(sa.Column('arrival_time', sa.Time(), nullable=True))

    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table('station', schema=None) as batch_op:
        batch_op.drop_column('arrival_time')

    # ### end Alembic commands ###
