"""subject_programme many-to-many

Revision ID: fa10ee43eea2
Revises: 7a29b26a39e2
Create Date: 2026-03-11 09:20:48.715995

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'fa10ee43eea2'
down_revision = '7a29b26a39e2'
branch_labels = None
depends_on = None


def upgrade():
    # Drop programme_id column from subject if it still exists
    op.execute("""
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_name='subject' AND column_name='programme_id'
            ) THEN
                ALTER TABLE subject DROP COLUMN programme_id;
            END IF;
        END$$;
    """)

    # Re-create FKs on subject_programme with named constraints
    op.drop_constraint('subject_programme_programme_id_fkey', 'subject_programme', type_='foreignkey')
    op.drop_constraint('subject_programme_subject_id_fkey',   'subject_programme', type_='foreignkey')
    op.create_foreign_key('fk_sp_subject_id',   'subject_programme', 'subject',   ['subject_id'],   ['id'], ondelete='CASCADE')
    op.create_foreign_key('fk_sp_programme_id', 'subject_programme', 'programme', ['programme_id'], ['id'], ondelete='CASCADE')


def downgrade():
    op.drop_constraint('fk_sp_subject_id',   'subject_programme', type_='foreignkey')
    op.drop_constraint('fk_sp_programme_id', 'subject_programme', type_='foreignkey')
    op.create_foreign_key('subject_programme_subject_id_fkey',   'subject_programme', 'subject',   ['subject_id'],   ['id'], ondelete='CASCADE')
    op.create_foreign_key('subject_programme_programme_id_fkey', 'subject_programme', 'programme', ['programme_id'], ['id'], ondelete='CASCADE')
    op.add_column('subject', sa.Column('programme_id', sa.INTEGER(), autoincrement=False, nullable=True))