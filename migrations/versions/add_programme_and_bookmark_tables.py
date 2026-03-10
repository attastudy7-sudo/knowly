"""Add programme table, bookmark table, content_type to post, and programme_id to subject.

Revision ID: a8f3c1b09d2e
Revises: 68b2c9a84344_merge_migration_heads
Create Date: 2025-01-15 10:30:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'a8f3c1b09d2e'
down_revision = '68b2c9a84344'
branch_labels = None
depends_on = None


def upgrade():
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    existing_tables = inspector.get_table_names()

    # === Create programme table ===
    if 'programme' not in existing_tables:
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
            sa.UniqueConstraint('name'),
            sa.UniqueConstraint('slug')
        )
        indexes = [i['name'] for i in inspector.get_indexes('programme')] if 'programme' in existing_tables else []
        if 'ix_programme_name' not in indexes:
            op.create_index(op.f('ix_programme_name'), 'programme', ['name'], unique=True)
        if 'ix_programme_slug' not in indexes:
            op.create_index(op.f('ix_programme_slug'), 'programme', ['slug'], unique=True)

    # === Add programme_id to subject table ===
    subject_cols = [col['name'] for col in inspector.get_columns('subject')]
    subject_fks = [fk['name'] for fk in inspector.get_foreign_keys('subject')]
    with op.batch_alter_table('subject', schema=None) as batch_op:
        if 'programme_id' not in subject_cols:
            batch_op.add_column(sa.Column('programme_id', sa.Integer(), nullable=True))
        if 'fk_subject_programme' not in subject_fks:
            batch_op.create_foreign_key(
                'fk_subject_programme', 'programme',
                ['programme_id'], ['id'], ondelete='SET NULL'
            )

    # === Add content_type to post table ===
    post_cols = [col['name'] for col in inspector.get_columns('post')]
    with op.batch_alter_table('post', schema=None) as batch_op:
        if 'content_type' not in post_cols:
            batch_op.add_column(sa.Column('content_type', sa.String(length=20), nullable=False, server_default='notes'))

    # === Create bookmark table ===
    if 'bookmark' not in existing_tables:
        op.create_table(
            'bookmark',
            sa.Column('id', sa.Integer(), nullable=False),
            sa.Column('user_id', sa.Integer(), nullable=False),
            sa.Column('post_id', sa.Integer(), nullable=False),
            sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
            sa.ForeignKeyConstraint(['user_id'], ['profiles.id'], name='fk_bookmark_user', ondelete='CASCADE'),
            sa.ForeignKeyConstraint(['post_id'], ['post.id'], name='fk_bookmark_post', ondelete='CASCADE'),
            sa.PrimaryKeyConstraint('id'),
            sa.UniqueConstraint('user_id', 'post_id', name='unique_bookmark')
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