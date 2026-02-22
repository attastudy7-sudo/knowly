"""add xp fields to user

Revision ID: add_xp_fields
Revises: add_streak_fields
Create Date: 2026-02-22 07:23:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'add_xp_fields'
down_revision = 'add_streak_fields'
branch_labels = None
depends_on = None


def upgrade():
    # Add XP tracking columns to profiles table
    op.add_column('profiles', sa.Column('xp_points', sa.Integer(), nullable=False, server_default='0'))
    op.add_column('profiles', sa.Column('xp_level', sa.Integer(), nullable=False, server_default='1'))
    op.add_column('profiles', sa.Column('xp_title', sa.String(50), nullable=True))


def downgrade():
    # Remove XP tracking columns from profiles table
    op.drop_column('profiles', 'xp_title')
    op.drop_column('profiles', 'xp_level')
    op.drop_column('profiles', 'xp_points')
