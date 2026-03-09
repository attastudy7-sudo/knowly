"""add school and programme to user

Revision ID: 45c27f8e60c0
Revises: d539b2d789cd
Create Date: 2026-02-21 19:35:23.676805

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '45c27f8e60c0'
down_revision = 'd539b2d789cd'
branch_labels = None
depends_on = None


def upgrade():
    conn = op.get_bind()
    inspector = sa.inspect(conn)

    # ── comment ──────────────────────────────────────────────────────────────
    indexes = [i['name'] for i in inspector.get_indexes('comment')]
    fks = [fk['name'] for fk in inspector.get_foreign_keys('comment')]
    with op.batch_alter_table('comment', schema=None) as batch_op:
        batch_op.alter_column('content', existing_type=sa.TEXT(), nullable=False)
        batch_op.alter_column('created_at', existing_type=sa.TIMESTAMP(), nullable=False)
        batch_op.alter_column('user_id', existing_type=sa.INTEGER(), nullable=False)
        batch_op.alter_column('post_id', existing_type=sa.INTEGER(), nullable=False)
        if 'ix_comment_created_at' not in indexes:
            batch_op.create_index(batch_op.f('ix_comment_created_at'), ['created_at'], unique=False)
        if 'fk_comment_user' not in fks:
            batch_op.create_foreign_key('fk_comment_user', 'profiles', ['user_id'], ['id'])
        if 'fk_comment_post' not in fks:
            batch_op.create_foreign_key('fk_comment_post', 'post', ['post_id'], ['id'])

    # ── notification ──────────────────────────────────────────────────────────
    indexes = [i['name'] for i in inspector.get_indexes('notification')]
    with op.batch_alter_table('notification', schema=None) as batch_op:
        batch_op.alter_column('user_id', existing_type=sa.INTEGER(), nullable=False)
        batch_op.alter_column('message', existing_type=sa.TEXT(), type_=sa.String(length=300), nullable=False)
        batch_op.alter_column('notification_type', existing_type=sa.TEXT(), type_=sa.String(length=50), existing_nullable=True)
        batch_op.alter_column('link', existing_type=sa.TEXT(), type_=sa.String(length=300), existing_nullable=True)
        batch_op.alter_column('created_at', existing_type=sa.TIMESTAMP(), nullable=False)
        if 'ix_notification_created_at' not in indexes:
            batch_op.create_index(batch_op.f('ix_notification_created_at'), ['created_at'], unique=False)
        batch_op.create_foreign_key(None, 'profiles', ['user_id'], ['id'])

    # ── post ──────────────────────────────────────────────────────────────────
    indexes = [i['name'] for i in inspector.get_indexes('post')]
    fks = [fk['name'] for fk in inspector.get_foreign_keys('post')]
    with op.batch_alter_table('post', schema=None) as batch_op:
        batch_op.alter_column('title', existing_type=sa.TEXT(), type_=sa.String(length=200), nullable=False)
        batch_op.alter_column('created_at', existing_type=sa.TIMESTAMP(), nullable=False)
        batch_op.alter_column('user_id', existing_type=sa.INTEGER(), nullable=False)
        if 'ix_post_created_at' not in indexes:
            batch_op.create_index(batch_op.f('ix_post_created_at'), ['created_at'], unique=False)
        if 'fk_post_subject' not in fks:
            batch_op.create_foreign_key('fk_post_subject', 'subject', ['subject_id'], ['id'])
        if 'fk_post_document' not in fks:
            batch_op.create_foreign_key('fk_post_document', 'document', ['document_id'], ['id'])
        if 'fk_post_user' not in fks:
            batch_op.create_foreign_key('fk_post_user', 'profiles', ['user_id'], ['id'])

    # ── profiles ──────────────────────────────────────────────────────────────
    profile_cols = [col['name'] for col in inspector.get_columns('profiles')]
    indexes = [i['name'] for i in inspector.get_indexes('profiles')]
    with op.batch_alter_table('profiles', schema=None) as batch_op:
        if 'school' not in profile_cols:
            batch_op.add_column(sa.Column('school', sa.String(length=200), nullable=True))
        if 'programme' not in profile_cols:
            batch_op.add_column(sa.Column('programme', sa.String(length=200), nullable=True))
        batch_op.alter_column('username', existing_type=sa.TEXT(), type_=sa.String(length=80), nullable=False)
        batch_op.alter_column('email', existing_type=sa.TEXT(), type_=sa.String(length=120), nullable=False)
        batch_op.alter_column('password_hash', existing_type=sa.TEXT(), type_=sa.String(length=255), nullable=False)
        batch_op.alter_column('full_name', existing_type=sa.TEXT(), type_=sa.String(length=120), existing_nullable=True)
        batch_op.alter_column('profile_picture', existing_type=sa.TEXT(), type_=sa.String(length=200), existing_nullable=True)
        batch_op.alter_column('created_at', existing_type=sa.TIMESTAMP(), nullable=False)
        if 'ix_profiles_email' not in indexes:
            batch_op.create_index(batch_op.f('ix_profiles_email'), ['email'], unique=True)
        if 'ix_profiles_username' not in indexes:
            batch_op.create_index(batch_op.f('ix_profiles_username'), ['username'], unique=True)

    # ── subject ───────────────────────────────────────────────────────────────
    indexes = [i['name'] for i in inspector.get_indexes('subject')]
    with op.batch_alter_table('subject', schema=None) as batch_op:
        batch_op.alter_column('name', existing_type=sa.TEXT(), type_=sa.String(length=100), nullable=False)
        batch_op.alter_column('slug', existing_type=sa.TEXT(), type_=sa.String(length=100), nullable=False)
        batch_op.alter_column('icon', existing_type=sa.TEXT(), type_=sa.String(length=50), existing_nullable=True)
        batch_op.alter_column('color', existing_type=sa.TEXT(), type_=sa.String(length=7), existing_nullable=True)
        batch_op.alter_column('created_at', existing_type=sa.TIMESTAMP(), nullable=False)
        if 'ix_subject_name' not in indexes:
            batch_op.create_index(batch_op.f('ix_subject_name'), ['name'], unique=True)
        if 'ix_subject_slug' not in indexes:
            batch_op.create_index(batch_op.f('ix_subject_slug'), ['slug'], unique=True)

    # ── like ──────────────────────────────────────────────────────────────────
    fks = [fk['name'] for fk in inspector.get_foreign_keys('like')]
    uqs = [c['name'] for c in inspector.get_unique_constraints('like')]
    with op.batch_alter_table('like', schema=None) as batch_op:
        batch_op.alter_column('created_at', existing_type=sa.TIMESTAMP(), nullable=False)
        batch_op.alter_column('user_id', existing_type=sa.INTEGER(), nullable=False)
        batch_op.alter_column('post_id', existing_type=sa.INTEGER(), nullable=False)
        if 'unique_like' not in uqs:
            batch_op.create_unique_constraint('unique_like', ['user_id', 'post_id'])
        if 'fk_like_post' not in fks:
            batch_op.create_foreign_key('fk_like_post', 'post', ['post_id'], ['id'])
        if 'fk_like_user' not in fks:
            batch_op.create_foreign_key('fk_like_user', 'profiles', ['user_id'], ['id'])

    # ── followers ─────────────────────────────────────────────────────────────
    fks = [fk['name'] for fk in inspector.get_foreign_keys('followers')]
    with op.batch_alter_table('followers', schema=None) as batch_op:
        if 'fk_followers_follower' not in fks:
            batch_op.create_foreign_key('fk_followers_follower', 'profiles', ['follower_id'], ['id'])
        if 'fk_followers_followed' not in fks:
            batch_op.create_foreign_key('fk_followers_followed', 'profiles', ['followed_id'], ['id'])

    # ── purchase ──────────────────────────────────────────────────────────────
    fks = [fk['name'] for fk in inspector.get_foreign_keys('purchase')]
    uqs = [c['name'] for c in inspector.get_unique_constraints('purchase')]
    with op.batch_alter_table('purchase', schema=None) as batch_op:
        batch_op.alter_column('user_id', existing_type=sa.INTEGER(), nullable=False)
        batch_op.alter_column('document_id', existing_type=sa.INTEGER(), nullable=False)
        batch_op.alter_column('amount_paid', existing_type=sa.FLOAT(), nullable=False)
        batch_op.alter_column('payment_method', existing_type=sa.TEXT(), type_=sa.String(length=50), existing_nullable=True)
        batch_op.alter_column('transaction_id', existing_type=sa.TEXT(), type_=sa.String(length=200), existing_nullable=True)
        batch_op.alter_column('status', existing_type=sa.TEXT(), type_=sa.String(length=50), existing_nullable=True)
        batch_op.alter_column('purchased_at', existing_type=sa.TIMESTAMP(), nullable=False)
        if 'uq_purchase_transaction' not in uqs:
            batch_op.create_unique_constraint('uq_purchase_transaction', ['transaction_id'])
        if 'fk_purchase_document' not in fks:
            batch_op.create_foreign_key('fk_purchase_document', 'document', ['document_id'], ['id'])
        if 'fk_purchase_user' not in fks:
            batch_op.create_foreign_key('fk_purchase_user', 'profiles', ['user_id'], ['id'])

    # ── document ──────────────────────────────────────────────────────────────
    with op.batch_alter_table('document', schema=None) as batch_op:
        batch_op.alter_column('filename', existing_type=sa.TEXT(), type_=sa.String(length=300), nullable=False)
        batch_op.alter_column('original_filename', existing_type=sa.TEXT(), type_=sa.String(length=300), nullable=False)
        batch_op.alter_column('file_path', existing_type=sa.TEXT(), type_=sa.String(length=500), nullable=False)
        batch_op.alter_column('file_type', existing_type=sa.TEXT(), type_=sa.String(length=50), existing_nullable=True)
        batch_op.alter_column('uploaded_at', existing_type=sa.TIMESTAMP(), nullable=False)
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table('subject', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_subject_slug'))
        batch_op.drop_index(batch_op.f('ix_subject_name'))
        batch_op.alter_column('created_at',
               existing_type=postgresql.TIMESTAMP(),
               nullable=True)
        batch_op.alter_column('color',
               existing_type=sa.String(length=7),
               type_=sa.TEXT(),
               existing_nullable=True)
        batch_op.alter_column('icon',
               existing_type=sa.String(length=50),
               type_=sa.TEXT(),
               existing_nullable=True)
        batch_op.alter_column('slug',
               existing_type=sa.String(length=100),
               type_=sa.TEXT(),
               nullable=True)
        batch_op.alter_column('name',
               existing_type=sa.String(length=100),
               type_=sa.TEXT(),
               nullable=True)

    with op.batch_alter_table('purchase', schema=None) as batch_op:
        batch_op.drop_constraint(None, type_='foreignkey')
        batch_op.drop_constraint(None, type_='foreignkey')
        batch_op.drop_constraint(None, type_='unique')
        batch_op.alter_column('purchased_at',
               existing_type=postgresql.TIMESTAMP(),
               nullable=True)
        batch_op.alter_column('status',
               existing_type=sa.String(length=50),
               type_=sa.TEXT(),
               existing_nullable=True)
        batch_op.alter_column('transaction_id',
               existing_type=sa.String(length=200),
               type_=sa.TEXT(),
               existing_nullable=True)
        batch_op.alter_column('payment_method',
               existing_type=sa.String(length=50),
               type_=sa.TEXT(),
               existing_nullable=True)
        batch_op.alter_column('amount_paid',
               existing_type=sa.DOUBLE_PRECISION(precision=53),
               nullable=True)
        batch_op.alter_column('document_id',
               existing_type=sa.INTEGER(),
               nullable=True)
        batch_op.alter_column('user_id',
               existing_type=sa.INTEGER(),
               nullable=True)

    with op.batch_alter_table('profiles', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_profiles_username'))
        batch_op.drop_index(batch_op.f('ix_profiles_email'))
        batch_op.alter_column('created_at',
               existing_type=postgresql.TIMESTAMP(),
               nullable=True)
        batch_op.alter_column('profile_picture',
               existing_type=sa.String(length=200),
               type_=sa.TEXT(),
               existing_nullable=True)
        batch_op.alter_column('full_name',
               existing_type=sa.String(length=120),
               type_=sa.TEXT(),
               existing_nullable=True)
        batch_op.alter_column('password_hash',
               existing_type=sa.String(length=255),
               type_=sa.TEXT(),
               nullable=True)
        batch_op.alter_column('email',
               existing_type=sa.String(length=120),
               type_=sa.TEXT(),
               nullable=True)
        batch_op.alter_column('username',
               existing_type=sa.String(length=80),
               type_=sa.TEXT(),
               nullable=True)
        batch_op.drop_column('programme')
        batch_op.drop_column('school')

    with op.batch_alter_table('post', schema=None) as batch_op:
        batch_op.drop_constraint(None, type_='foreignkey')
        batch_op.drop_constraint(None, type_='foreignkey')
        batch_op.drop_constraint(None, type_='foreignkey')
        batch_op.drop_index(batch_op.f('ix_post_created_at'))
        batch_op.alter_column('user_id',
               existing_type=sa.INTEGER(),
               nullable=True)
        batch_op.alter_column('created_at',
               existing_type=postgresql.TIMESTAMP(),
               nullable=True)
        batch_op.alter_column('title',
               existing_type=sa.String(length=200),
               type_=sa.TEXT(),
               nullable=True)

    with op.batch_alter_table('notification', schema=None) as batch_op:
        batch_op.drop_constraint(None, type_='foreignkey')
        batch_op.drop_index(batch_op.f('ix_notification_created_at'))
        batch_op.alter_column('created_at',
               existing_type=postgresql.TIMESTAMP(),
               nullable=True)
        batch_op.alter_column('link',
               existing_type=sa.String(length=300),
               type_=sa.TEXT(),
               existing_nullable=True)
        batch_op.alter_column('notification_type',
               existing_type=sa.String(length=50),
               type_=sa.TEXT(),
               existing_nullable=True)
        batch_op.alter_column('message',
               existing_type=sa.String(length=300),
               type_=sa.TEXT(),
               nullable=True)
        batch_op.alter_column('user_id',
               existing_type=sa.INTEGER(),
               nullable=True)

    with op.batch_alter_table('like', schema=None) as batch_op:
        batch_op.drop_constraint(None, type_='foreignkey')
        batch_op.drop_constraint(None, type_='foreignkey')
        batch_op.drop_constraint('unique_like', type_='unique')
        batch_op.alter_column('post_id',
               existing_type=sa.INTEGER(),
               nullable=True)
        batch_op.alter_column('user_id',
               existing_type=sa.INTEGER(),
               nullable=True)
        batch_op.alter_column('created_at',
               existing_type=postgresql.TIMESTAMP(),
               nullable=True)

    with op.batch_alter_table('followers', schema=None) as batch_op:
        batch_op.drop_constraint(None, type_='foreignkey')
        batch_op.drop_constraint(None, type_='foreignkey')

    with op.batch_alter_table('document', schema=None) as batch_op:
        batch_op.alter_column('uploaded_at',
               existing_type=postgresql.TIMESTAMP(),
               nullable=True)
        batch_op.alter_column('file_type',
               existing_type=sa.String(length=50),
               type_=sa.TEXT(),
               existing_nullable=True)
        batch_op.alter_column('file_path',
               existing_type=sa.String(length=500),
               type_=sa.TEXT(),
               nullable=True)
        batch_op.alter_column('original_filename',
               existing_type=sa.String(length=300),
               type_=sa.TEXT(),
               nullable=True)
        batch_op.alter_column('filename',
               existing_type=sa.String(length=300),
               type_=sa.TEXT(),
               nullable=True)

    with op.batch_alter_table('comment', schema=None) as batch_op:
        batch_op.drop_constraint(None, type_='foreignkey')
        batch_op.drop_constraint(None, type_='foreignkey')
        batch_op.drop_index(batch_op.f('ix_comment_created_at'))
        batch_op.alter_column('post_id',
               existing_type=sa.INTEGER(),
               nullable=True)
        batch_op.alter_column('user_id',
               existing_type=sa.INTEGER(),
               nullable=True)
        batch_op.alter_column('created_at',
               existing_type=postgresql.TIMESTAMP(),
               nullable=True)
        batch_op.alter_column('content',
               existing_type=sa.TEXT(),
               nullable=True)

    # ### end Alembic commands ###
