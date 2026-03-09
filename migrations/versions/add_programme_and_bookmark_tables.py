"""Add programme table, bookmark table, content_type to post, and programme_id to subject.

Revision ID: add_programme_and_bookmark_tables
Revises: 68b2c9a84344_merge_migration_heads
Create Date: 2025-01-15 10:30:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'add_programme_and_bookmark_tables'
down_revision = '68b2c9a84344'
branch_labels = None
depends_on = None


def upgrade():
    # === Create programme table ===
    op.create_table(
        'programme',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(length=200), nullable=False),
        sa.Column('slug', sa.String(length=100), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('icon', sa.String(length=50), nullable=True, server_default='graduation-cap'),
        sa.Column('color', sa.String(length=7), nullable=True, server_default='#8b5cf6'),
        sa.Column('order', sa.Integer(), nullable=True, server_default='0'),
        sa.Column('is_active', sa.Boolean(), nullable=True, server_default='true'),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint('id'),
        sa.unique_constraint('name'),
        sa.unique_constraint('slug')
    )
    op.create_index(op.f('ix_programme_name'), 'programme', ['name'], unique=True)
    op.create_index(op.f('ix_programme_slug'), 'programme', ['slug'], unique=True)
    
    # === Add programme_id to subject table ===
    with op.batch_alter_table('subject', schema=None) as batch_op:
        batch_op.add_column(sa.Column('programme_id', sa.Integer(), nullable=True))
        batch_op.create_foreign_key(
            'fk_subject_programme',
            'programme',
            ['programme_id'],
            ['id'],
            ondelete='SET NULL'
        )
    
    # === Add content_type to post table ===
    with op.batch_alter_table('post', schema=None) as batch_op:
        batch_op.add_column(sa.Column('content_type', sa.String(length=20), nullable=False, server_default='notes'))
    
    # === Create bookmark table ===
    op.create_table(
        'bookmark',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('post_id', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(['user_id'], ['profiles.id'], name='fk_bookmark_user', ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['post_id'], ['post.id'], name='fk_bookmark_post', ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.unique_constraint('unique_bookmark')
    )
    op.create_index(op.f('ix_bookmark_user_id'), 'bookmark', ['user_id'], unique=False)
    op.create_index(op.f('ix_bookmark_post_id'), 'bookmark', ['post_id'], unique=False)


def downgrade():
    # === Drop bookmark table ===
    op.drop_index(op.f('ix_bookmark_post_id'), table_name='bookmark')
    op.drop_index(op.f('ix_bookmark_user_id'), table_name='bookmark')
    op.drop_table('bookmark')
    
    # === Drop content_type from post ===
    with op.batch_alter_table('post', schema=None) as batch_op:
        batch_op.drop_column('content_type')
    
    # === Drop programme_id from subject ===
    with op.batch_alter_table('subject', schema=None) as batch_op:
        batch_op.drop_constraint('fk_subject_programme', type_='foreignkey')
        batch_op.drop_column('programme_id')
    
    # === Drop programme table ===
    op.drop_index(op.f('ix_programme_slug'), table_name='programme')
    op.drop_index(op.f('ix_programme_name'), table_name='programme')
    op.drop_table('programme')

