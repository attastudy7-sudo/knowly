"""add streak fields to user

Revision ID: add_streak_fields
Revises: d539b2d789cd
Create Date: 2026-02-22 00:20:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'add_streak_fields'
down_revision = 'd539b2d789cd'
branch_labels = None
depends_on = None


def upgrade():
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    columns = [col['name'] for col in inspector.get_columns('profiles')]
    if 'last_activity_date' not in columns:
        op.add_column('profiles', sa.Column('last_activity_date', sa.Date(), nullable=True))
    if 'current_streak' not in columns:
        op.add_column('profiles', sa.Column('current_streak', sa.Integer(), nullable=False, server_default='0'))
    if 'longest_streak' not in columns:
        op.add_column('profiles', sa.Column('longest_streak', sa.Integer(), nullable=False, server_default='0'))


def downgrade():
    # Remove streak tracking columns from profiles table
    op.drop_column('profiles', 'longest_streak')
    op.drop_column('profiles', 'current_streak')
    op.drop_column('profiles', 'last_activity_date')
