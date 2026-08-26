"""add exclusion_rules

Revision ID: db5e71b7d5fc
Revises: 8ec99e7c2072
Create Date: 2026-08-26 03:05:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import datasentinel_backend.core.types


# revision identifiers, used by Alembic.
revision: str = 'db5e71b7d5fc'
down_revision: Union[str, Sequence[str], None] = '8ec99e7c2072'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table('exclusion_rules',
    sa.Column('id', datasentinel_backend.core.types.GUID(), nullable=False),
    sa.Column('org_id', datasentinel_backend.core.types.GUID(), nullable=False),
    sa.Column('category', sa.String(), nullable=True),
    sa.Column('path_pattern', sa.String(), nullable=True),
    sa.Column('created_by', datasentinel_backend.core.types.GUID(), nullable=False),
    sa.Column('reason', sa.String(), nullable=False),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.ForeignKeyConstraint(['created_by'], ['users.id'], ),
    sa.ForeignKeyConstraint(['org_id'], ['organizations.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_exclusion_rules_org_id', 'exclusion_rules', ['org_id'], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index('ix_exclusion_rules_org_id', table_name='exclusion_rules')
    op.drop_table('exclusion_rules')
