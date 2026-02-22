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
    # Add streak tracking columns to profiles table
    op.add_column('profiles', sa.Column('last_activity_date', sa.Date(), nullable=True))
    op.add_column('profiles', sa.Column('current_streak', sa.Integer(), nullable=False, server_default='0'))
    op.add_column('profiles', sa.Column('longest_streak', sa.Integer(), nullable=False, server_default='0'))


def downgrade():
    # Remove streak tracking columns from profiles table
    op.drop_column('profiles', 'longest_streak')
    op.drop_column('profiles', 'current_streak')
    op.drop_column('profiles', 'last_activity_date')
