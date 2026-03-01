"""Merge migration heads

Revision ID: 68b2c9a84344
Revises: add_subscription_fields, 45c27f8e60c0
Create Date: 2026-02-27 04:31:08.822522

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '68b2c9a84344'
down_revision = ('add_subscription_fields', '45c27f8e60c0')
branch_labels = None
depends_on = None


def upgrade():
    pass


def downgrade():
    pass
