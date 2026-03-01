"""Add can_access_all_content to profiles table

Revision ID: add_can_access_all_content
Revises: add_xp_fields
Create Date: 2026-02-22 10:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

revision = 'add_can_access_all_content'
down_revision = 'add_xp_fields'
branch_labels = None
depends_on = None

def upgrade():
    op.add_column('profiles', sa.Column('can_access_all_content', sa.Boolean(), nullable=False, server_default='0'))

def downgrade():
    op.drop_column('profiles', 'can_access_all_content')
