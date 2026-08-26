"""add file_id to findings

Revision ID: 8ec99e7c2072
Revises: df4dec01519b
Create Date: 2026-08-26 03:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import datasentinel_backend.core.types


# revision identifiers, used by Alembic.
revision: str = '8ec99e7c2072'
down_revision: Union[str, Sequence[str], None] = 'df4dec01519b'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # batch_alter_table so this applies cleanly on SQLite (which can't add a
    # constraint with a plain ALTER TABLE) as well as PostgreSQL, per the
    # "Database portability" notes in backend/README.md.
    with op.batch_alter_table('findings', schema=None) as batch_op:
        batch_op.add_column(sa.Column('file_id', datasentinel_backend.core.types.GUID(), nullable=True))
        batch_op.create_foreign_key('fk_findings_file_id_files', 'files', ['file_id'], ['id'])


def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table('findings', schema=None) as batch_op:
        batch_op.drop_constraint('fk_findings_file_id_files', type_='foreignkey')
        batch_op.drop_column('file_id')
