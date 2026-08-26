"""add scan_errors

Revision ID: 4c709f9bd950
Revises: db5e71b7d5fc
Create Date: 2026-08-26 03:10:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import datasentinel_backend.core.types


# revision identifiers, used by Alembic.
revision: str = '4c709f9bd950'
down_revision: Union[str, Sequence[str], None] = 'db5e71b7d5fc'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table('scan_errors',
    sa.Column('id', datasentinel_backend.core.types.GUID(), nullable=False),
    sa.Column('scan_id', datasentinel_backend.core.types.GUID(), nullable=False),
    sa.Column('path', sa.String(), nullable=False),
    sa.Column('error_type', sa.String(), nullable=False),
    sa.Column('message', sa.String(), nullable=False),
    sa.Column('occurred_at', sa.DateTime(), nullable=False),
    sa.ForeignKeyConstraint(['scan_id'], ['scans.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_scan_errors_scan_id', 'scan_errors', ['scan_id'], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index('ix_scan_errors_scan_id', table_name='scan_errors')
    op.drop_table('scan_errors')
