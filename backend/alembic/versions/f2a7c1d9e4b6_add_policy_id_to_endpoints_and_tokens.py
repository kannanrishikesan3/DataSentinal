"""add policy_id to endpoints and enrollment_tokens

Revision ID: f2a7c1d9e4b6
Revises: a1c9e2f4b8d3
Create Date: 2026-08-26 08:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import datasentinel_backend.core.types


# revision identifiers, used by Alembic.
revision: str = 'f2a7c1d9e4b6'
down_revision: Union[str, Sequence[str], None] = 'a1c9e2f4b8d3'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # batch_alter_table so this applies cleanly on SQLite as well as
    # PostgreSQL, per the "Database portability" notes in backend/README.md.
    with op.batch_alter_table('endpoints', schema=None) as batch_op:
        batch_op.add_column(sa.Column('policy_id', datasentinel_backend.core.types.GUID(), nullable=True))
        batch_op.create_foreign_key('fk_endpoints_policy_id_policies', 'policies', ['policy_id'], ['id'])

    with op.batch_alter_table('enrollment_tokens', schema=None) as batch_op:
        batch_op.add_column(sa.Column('policy_id', datasentinel_backend.core.types.GUID(), nullable=True))
        batch_op.create_foreign_key('fk_enrollment_tokens_policy_id_policies', 'policies', ['policy_id'], ['id'])


def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table('enrollment_tokens', schema=None) as batch_op:
        batch_op.drop_constraint('fk_enrollment_tokens_policy_id_policies', type_='foreignkey')
        batch_op.drop_column('policy_id')

    with op.batch_alter_table('endpoints', schema=None) as batch_op:
        batch_op.drop_constraint('fk_endpoints_policy_id_policies', type_='foreignkey')
        batch_op.drop_column('policy_id')
