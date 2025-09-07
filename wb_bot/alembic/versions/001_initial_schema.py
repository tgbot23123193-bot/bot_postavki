"""Initial database schema

Revision ID: 001
Revises: 
Create Date: 2024-01-01 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '001'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade database schema."""
    
    # Create users table
    op.create_table(
        'users',
        sa.Column('id', sa.BigInteger(), nullable=False),
        sa.Column('username', sa.String(length=255), nullable=True),
        sa.Column('first_name', sa.String(length=255), nullable=True),
        sa.Column('last_name', sa.String(length=255), nullable=True),
        sa.Column('language_code', sa.String(length=10), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False),
        sa.Column('is_premium', sa.Boolean(), nullable=False),
        sa.Column('trial_bookings', sa.Integer(), nullable=False),
        sa.Column('default_check_interval', sa.Integer(), nullable=False),
        sa.Column('default_max_coefficient', sa.Float(), nullable=False),
        sa.Column('default_supply_type', sa.String(length=20), nullable=False),
        sa.Column('default_delivery_type', sa.String(length=20), nullable=False),
        sa.Column('default_monitoring_mode', sa.String(length=20), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.Column('last_activity', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.CheckConstraint('trial_bookings >= 0', name='check_trial_bookings_positive'),
        sa.CheckConstraint('default_check_interval >= 1', name='check_interval_positive'),
        sa.CheckConstraint('default_max_coefficient >= 1.0', name='check_coefficient_positive'),
    )
    
    # Create indexes for users table
    op.create_index('idx_user_activity', 'users', ['is_active', 'last_activity'])
    op.create_index(op.f('ix_users_id'), 'users', ['id'])
    op.create_index(op.f('ix_users_username'), 'users', ['username'])
    op.create_index(op.f('ix_users_is_active'), 'users', ['is_active'])
    op.create_index(op.f('ix_users_created_at'), 'users', ['created_at'])
    op.create_index(op.f('ix_users_last_activity'), 'users', ['last_activity'])
    
    # Create api_keys table
    op.create_table(
        'api_keys',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('user_id', sa.BigInteger(), nullable=False),
        sa.Column('encrypted_key', sa.String(length=500), nullable=False),
        sa.Column('salt', sa.String(length=100), nullable=False),
        sa.Column('name', sa.String(length=100), nullable=True),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('is_valid', sa.Boolean(), nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=False),
        sa.Column('last_validation', sa.DateTime(), nullable=True),
        sa.Column('validation_error', sa.Text(), nullable=True),
        sa.Column('last_used', sa.DateTime(), nullable=True),
        sa.Column('total_requests', sa.Integer(), nullable=False),
        sa.Column('successful_requests', sa.Integer(), nullable=False),
        sa.Column('failed_requests', sa.Integer(), nullable=False),
        sa.Column('requests_per_minute', sa.Integer(), nullable=False),
        sa.Column('last_rate_reset', sa.DateTime(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.CheckConstraint('total_requests >= 0', name='check_total_requests_positive'),
        sa.CheckConstraint('successful_requests >= 0', name='check_successful_requests_positive'),
        sa.CheckConstraint('failed_requests >= 0', name='check_failed_requests_positive'),
        sa.CheckConstraint('requests_per_minute >= 0', name='check_rpm_positive'),
    )
    
    # Create indexes for api_keys table
    op.create_index('idx_apikey_user_active', 'api_keys', ['user_id', 'is_active'])
    op.create_index('idx_apikey_usage', 'api_keys', ['last_used', 'total_requests'])
    op.create_index('idx_apikey_user_valid', 'api_keys', ['user_id', 'is_valid', 'is_active'])
    op.create_index(op.f('ix_api_keys_user_id'), 'api_keys', ['user_id'])
    op.create_index(op.f('ix_api_keys_is_valid'), 'api_keys', ['is_valid'])
    op.create_index(op.f('ix_api_keys_created_at'), 'api_keys', ['created_at'])
    op.create_index(op.f('ix_api_keys_last_used'), 'api_keys', ['last_used'])
    
    # Create monitoring_tasks table
    op.create_table(
        'monitoring_tasks',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('user_id', sa.BigInteger(), nullable=False),
        sa.Column('warehouse_id', sa.Integer(), nullable=False),
        sa.Column('warehouse_name', sa.String(length=100), nullable=False),
        sa.Column('date_from', sa.Date(), nullable=False),
        sa.Column('date_to', sa.Date(), nullable=False),
        sa.Column('check_interval', sa.Integer(), nullable=False),
        sa.Column('max_coefficient', sa.Float(), nullable=False),
        sa.Column('supply_type', sa.String(length=20), nullable=False),
        sa.Column('delivery_type', sa.String(length=20), nullable=False),
        sa.Column('monitoring_mode', sa.String(length=20), nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=False),
        sa.Column('is_paused', sa.Boolean(), nullable=False),
        sa.Column('total_checks', sa.Integer(), nullable=False),
        sa.Column('slots_found', sa.Integer(), nullable=False),
        sa.Column('successful_bookings', sa.Integer(), nullable=False),
        sa.Column('failed_bookings', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.Column('last_check', sa.DateTime(), nullable=True),
        sa.Column('next_check', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.CheckConstraint('date_to >= date_from', name='check_date_range_valid'),
        sa.CheckConstraint('check_interval >= 1', name='check_interval_positive'),
        sa.CheckConstraint('max_coefficient >= 1.0', name='check_coefficient_positive'),
        sa.CheckConstraint('total_checks >= 0', name='check_total_checks_positive'),
        sa.CheckConstraint('slots_found >= 0', name='check_slots_found_positive'),
        sa.CheckConstraint('successful_bookings >= 0', name='check_successful_bookings_positive'),
        sa.CheckConstraint('failed_bookings >= 0', name='check_failed_bookings_positive'),
        sa.UniqueConstraint('user_id', 'warehouse_id', 'date_from', 'date_to', 'supply_type', 'delivery_type', 
                          name='uq_monitoring_task'),
    )
    
    # Create indexes for monitoring_tasks table
    op.create_index('idx_monitoring_active', 'monitoring_tasks', ['is_active', 'next_check'])
    op.create_index('idx_monitoring_warehouse', 'monitoring_tasks', ['warehouse_id', 'date_from', 'date_to'])
    op.create_index('idx_user_active_monitoring', 'monitoring_tasks', ['user_id', 'is_active', 'next_check'])
    op.create_index(op.f('ix_monitoring_tasks_user_id'), 'monitoring_tasks', ['user_id'])
    op.create_index(op.f('ix_monitoring_tasks_warehouse_id'), 'monitoring_tasks', ['warehouse_id'])
    op.create_index(op.f('ix_monitoring_tasks_date_from'), 'monitoring_tasks', ['date_from'])
    op.create_index(op.f('ix_monitoring_tasks_date_to'), 'monitoring_tasks', ['date_to'])
    op.create_index(op.f('ix_monitoring_tasks_is_active'), 'monitoring_tasks', ['is_active'])
    op.create_index(op.f('ix_monitoring_tasks_created_at'), 'monitoring_tasks', ['created_at'])
    op.create_index(op.f('ix_monitoring_tasks_last_check'), 'monitoring_tasks', ['last_check'])
    op.create_index(op.f('ix_monitoring_tasks_next_check'), 'monitoring_tasks', ['next_check'])
    
    # Create booking_results table
    op.create_table(
        'booking_results',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('task_id', sa.Integer(), nullable=False),
        sa.Column('booking_date', sa.Date(), nullable=False),
        sa.Column('slot_time', sa.String(length=50), nullable=True),
        sa.Column('coefficient', sa.Float(), nullable=True),
        sa.Column('wb_booking_id', sa.String(length=100), nullable=True),
        sa.Column('wb_response', sa.Text(), nullable=True),
        sa.Column('status', sa.String(length=50), nullable=False),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('retry_count', sa.Integer(), nullable=False),
        sa.Column('api_key_id', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.Column('confirmed_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['task_id'], ['monitoring_tasks.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['api_key_id'], ['api_keys.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.CheckConstraint('retry_count >= 0', name='check_retry_count_positive'),
        sa.CheckConstraint('coefficient >= 1.0 OR coefficient IS NULL', name='check_coefficient_valid'),
    )
    
    # Create indexes for booking_results table
    op.create_index('idx_booking_status', 'booking_results', ['status', 'created_at'])
    op.create_index('idx_booking_date', 'booking_results', ['booking_date', 'status'])
    op.create_index('idx_booking_wb_id', 'booking_results', ['wb_booking_id'])
    op.create_index('idx_booking_task_status', 'booking_results', ['task_id', 'status', 'created_at'])
    op.create_index(op.f('ix_booking_results_task_id'), 'booking_results', ['task_id'])
    op.create_index(op.f('ix_booking_results_booking_date'), 'booking_results', ['booking_date'])
    op.create_index(op.f('ix_booking_results_status'), 'booking_results', ['status'])
    op.create_index(op.f('ix_booking_results_created_at'), 'booking_results', ['created_at'])


def downgrade() -> None:
    """Downgrade database schema."""
    
    # Drop tables in reverse order
    op.drop_table('booking_results')
    op.drop_table('monitoring_tasks')
    op.drop_table('api_keys')
    op.drop_table('users')
