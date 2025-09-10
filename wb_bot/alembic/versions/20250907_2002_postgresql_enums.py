"""Add PostgreSQL enum types

Revision ID: postgresql_enums
Revises: 001
Create Date: 2025-09-07 20:02:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'postgresql_enums'
down_revision: Union[str, None] = '001'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade database schema."""
    # Create enum types first
    booking_status_enum = postgresql.ENUM('PENDING', 'CONFIRMED', 'CANCELLED', 'FAILED', name='booking_status_enum')
    supply_type_enum = postgresql.ENUM('BOX', 'MONO_PALLET', name='supply_type_enum')
    delivery_type_enum = postgresql.ENUM('DIRECT', 'TRANSIT', name='delivery_type_enum')
    monitoring_mode_enum = postgresql.ENUM('NOTIFICATION', 'AUTO_BOOKING', name='monitoring_mode_enum')
    
    booking_status_enum.create(op.get_bind())
    supply_type_enum.create(op.get_bind())
    delivery_type_enum.create(op.get_bind())
    monitoring_mode_enum.create(op.get_bind())
    
    # Update booking_results table
    op.execute("ALTER TABLE booking_results ALTER COLUMN status TYPE booking_status_enum USING status::text::booking_status_enum")
    
    # Update monitoring_tasks table
    op.execute("ALTER TABLE monitoring_tasks ALTER COLUMN supply_type TYPE supply_type_enum USING supply_type::text::supply_type_enum")
    op.execute("ALTER TABLE monitoring_tasks ALTER COLUMN delivery_type TYPE delivery_type_enum USING delivery_type::text::delivery_type_enum")
    op.execute("ALTER TABLE monitoring_tasks ALTER COLUMN monitoring_mode TYPE monitoring_mode_enum USING monitoring_mode::text::monitoring_mode_enum")
    
    # Update users table
    op.execute("ALTER TABLE users ALTER COLUMN default_supply_type TYPE supply_type_enum USING default_supply_type::text::supply_type_enum")
    op.execute("ALTER TABLE users ALTER COLUMN default_delivery_type TYPE delivery_type_enum USING default_delivery_type::text::delivery_type_enum")
    op.execute("ALTER TABLE users ALTER COLUMN default_monitoring_mode TYPE monitoring_mode_enum USING default_monitoring_mode::text::monitoring_mode_enum")


def downgrade() -> None:
    """Downgrade database schema."""
    # Convert enum columns back to varchar
    op.execute("ALTER TABLE booking_results ALTER COLUMN status TYPE varchar(50) USING status::text")
    op.execute("ALTER TABLE monitoring_tasks ALTER COLUMN supply_type TYPE varchar(20) USING supply_type::text")
    op.execute("ALTER TABLE monitoring_tasks ALTER COLUMN delivery_type TYPE varchar(20) USING delivery_type::text")
    op.execute("ALTER TABLE monitoring_tasks ALTER COLUMN monitoring_mode TYPE varchar(20) USING monitoring_mode::text")
    op.execute("ALTER TABLE users ALTER COLUMN default_supply_type TYPE varchar(20) USING default_supply_type::text")
    op.execute("ALTER TABLE users ALTER COLUMN default_delivery_type TYPE varchar(20) USING default_delivery_type::text")
    op.execute("ALTER TABLE users ALTER COLUMN default_monitoring_mode TYPE varchar(20) USING default_monitoring_mode::text")
    
    # Drop enum types
    booking_status_enum = postgresql.ENUM('PENDING', 'CONFIRMED', 'CANCELLED', 'FAILED', name='booking_status_enum')
    supply_type_enum = postgresql.ENUM('BOX', 'MONO_PALLET', name='supply_type_enum')
    delivery_type_enum = postgresql.ENUM('DIRECT', 'TRANSIT', name='delivery_type_enum')
    monitoring_mode_enum = postgresql.ENUM('NOTIFICATION', 'AUTO_BOOKING', name='monitoring_mode_enum')
    
    booking_status_enum.drop(op.get_bind())
    supply_type_enum.drop(op.get_bind())
    delivery_type_enum.drop(op.get_bind())
    monitoring_mode_enum.drop(op.get_bind())


