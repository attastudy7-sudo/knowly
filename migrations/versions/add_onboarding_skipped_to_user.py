"""add onboarding_skipped to user

Revision ID: a1b2c3d4e5f6
Revises: d539b2d789cd
Create Date: 2025-01-01 00:00:00.000000
"""
from alembic import op
import sqlalchemy as sa

revision = 'a1b2c3d4e5f6'
down_revision = 'add_programme_and_bookmark_tables'
branch_labels = None
depends_on = None


def upgrade():
    conn = op.get_bind()
    cols = [row[1] for row in conn.execute(sa.text("PRAGMA table_info(profiles)"))]
    if 'onboarding_skipped' not in cols:
        op.add_column('profiles',
            sa.Column('onboarding_skipped', sa.Boolean(), nullable=False,
                      server_default=sa.false())
        )

def downgrade():
    op.drop_column('profiles', 'onboarding_skipped')