"""add_cookies_data_to_browser_sessions

Revision ID: 8346b614344c
Revises: 6e180f1a2e24
Create Date: 2025-10-03 11:27:52.690845

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '8346b614344c'
down_revision: Union[str, None] = '6e180f1a2e24'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade database schema."""
    # Добавляем поле cookies_data для хранения cookies в БД как JSON
    op.add_column('browser_sessions', sa.Column('cookies_data', sa.Text(), nullable=True))


def downgrade() -> None:
    """Downgrade database schema."""
    # Удаляем поле cookies_data
    op.drop_column('browser_sessions', 'cookies_data')
