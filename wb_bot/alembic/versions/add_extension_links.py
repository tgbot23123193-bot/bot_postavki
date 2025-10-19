"""Add extension_links table

Revision ID: add_extension_links_20251019
Revises: 8346b614344c
Create Date: 2025-10-19 16:50:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'add_extension_links_20251019'
down_revision = '8346b614344c'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create extension_links table
    op.create_table(
        'extension_links',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.BigInteger(), nullable=False),
        sa.Column('link_key', sa.String(length=100), nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('extension_version', sa.String(length=20), nullable=True),
        sa.Column('last_activity', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('now()')),
        sa.Column('linked_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('user_id'),
        sa.UniqueConstraint('link_key')
    )
    
    # Create indexes
    op.create_index('idx_extension_links_user_id', 'extension_links', ['user_id'])
    op.create_index('idx_extension_links_link_key', 'extension_links', ['link_key'])
    op.create_index('idx_extension_links_active', 'extension_links', ['is_active'])
    op.create_index('idx_extension_links_created_at', 'extension_links', ['created_at'])
    op.create_index('idx_extension_links_last_activity', 'extension_links', ['last_activity'])
    op.create_index('idx_extension_links_linked_at', 'extension_links', ['linked_at'])


def downgrade() -> None:
    # Drop indexes
    op.drop_index('idx_extension_links_linked_at', 'extension_links')
    op.drop_index('idx_extension_links_last_activity', 'extension_links')
    op.drop_index('idx_extension_links_created_at', 'extension_links')
    op.drop_index('idx_extension_links_active', 'extension_links')
    op.drop_index('idx_extension_links_link_key', 'extension_links')
    op.drop_index('idx_extension_links_user_id', 'extension_links')
    
    # Drop table
    op.drop_table('extension_links')

