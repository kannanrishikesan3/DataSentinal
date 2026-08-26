"""add agent_scan_id to scans (idempotent scan ingestion)

Revision ID: fe10d265a106
Revises: db5e71b7d5fc
Create Date: 2026-08-26 06:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'fe10d265a106'
down_revision: Union[str, Sequence[str], None] = '4c709f9bd950'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    with op.batch_alter_table('scans', schema=None) as batch_op:
        batch_op.add_column(sa.Column('agent_scan_id', sa.String(), nullable=True))
        batch_op.create_unique_constraint('uq_scans_endpoint_agent_scan_id', ['endpoint_id', 'agent_scan_id'])


def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table('scans', schema=None) as batch_op:
        batch_op.drop_constraint('uq_scans_endpoint_agent_scan_id', type_='unique')
        batch_op.drop_column('agent_scan_id')
