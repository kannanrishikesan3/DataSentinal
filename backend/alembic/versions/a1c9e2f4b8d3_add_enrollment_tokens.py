"""add enrollment_tokens

Revision ID: a1c9e2f4b8d3
Revises: fe10d265a106
Create Date: 2026-08-26 07:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import datasentinel_backend.core.types


# revision identifiers, used by Alembic.
revision: str = 'a1c9e2f4b8d3'
down_revision: Union[str, Sequence[str], None] = 'fe10d265a106'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        'enrollment_tokens',
        sa.Column('id', datasentinel_backend.core.types.GUID(), nullable=False),
        sa.Column('org_id', datasentinel_backend.core.types.GUID(), nullable=False),
        sa.Column('name', sa.String(), nullable=False),
        sa.Column('created_by', datasentinel_backend.core.types.GUID(), nullable=False),
        sa.Column('hashed_token', sa.String(), nullable=False),
        sa.Column('expires_at', sa.DateTime(), nullable=False),
        sa.Column('max_uses', sa.Integer(), nullable=False),
        sa.Column('current_uses', sa.Integer(), nullable=False),
        sa.Column('allowed_os', sa.String(), nullable=True),
        sa.Column('revoked_at', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['org_id'], ['organizations.id']),
        sa.ForeignKeyConstraint(['created_by'], ['users.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_enrollment_tokens_org_id', 'enrollment_tokens', ['org_id'])


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index('ix_enrollment_tokens_org_id', table_name='enrollment_tokens')
    op.drop_table('enrollment_tokens')
