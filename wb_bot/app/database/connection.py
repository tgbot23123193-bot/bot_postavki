"""
Database connection and session management.

This module provides async database connection management with proper
connection pooling, session handling, and error recovery.
"""

import asyncio
import logging
from contextlib import asynccontextmanager
from typing import AsyncGenerator, Optional

from sqlalchemy.ext.asyncio import (
    AsyncSession, AsyncEngine, create_async_engine, async_sessionmaker
)
from sqlalchemy.pool import QueuePool, StaticPool, AsyncAdaptedQueuePool
from sqlalchemy.exc import SQLAlchemyError, DisconnectionError
from sqlalchemy import text

from ..config import get_settings

logger = logging.getLogger(__name__)


class DatabaseManager:
    """
    Async database manager with connection pooling and health checks.
    
    Provides:
    - Async SQLAlchemy engine with connection pooling
    - Session factory for creating database sessions
    - Health check functionality
    - Automatic reconnection on connection loss
    - Proper resource cleanup
    """
    
    def __init__(self, database_url: Optional[str] = None):
        """Initialize database manager."""
        self.settings = get_settings()
        self.database_url = database_url or self.settings.database.url
        self.engine: Optional[AsyncEngine] = None
        self.session_factory: Optional[async_sessionmaker] = None
        self._is_connected = False
    
    async def initialize(self) -> None:
        """Initialize database engine and session factory."""
        try:
            # Use appropriate pool class based on database type
            if "sqlite" in self.database_url:
                pool_class = StaticPool
                engine_kwargs = {
                    "poolclass": pool_class,
                    "pool_pre_ping": True,
                    "connect_args": {"check_same_thread": False},
                    "future": True,
                }
            elif "postgresql" in self.database_url:
                pool_class = AsyncAdaptedQueuePool
                engine_kwargs = {
                    "pool_size": self.settings.database.pool_size,
                    "max_overflow": self.settings.database.max_overflow,
                    "pool_timeout": self.settings.database.pool_timeout,
                    "pool_recycle": self.settings.database.pool_recycle,
                    "poolclass": pool_class,
                    "pool_pre_ping": True,
                    "pool_reset_on_return": 'commit',
                    "future": True,
                    # PostgreSQL specific settings
                    "connect_args": {
                        "command_timeout": 60,
                        "server_settings": {
                            "jit": "off",  # Disable JIT for better performance on small queries
                            "application_name": "wb_auto_booking_bot",
                        }
                    }
                }
            else:
                pool_class = QueuePool
                engine_kwargs = {
                    "pool_size": self.settings.database.pool_size,
                    "max_overflow": self.settings.database.max_overflow,
                    "pool_timeout": self.settings.database.pool_timeout,
                    "pool_recycle": self.settings.database.pool_recycle,
                    "poolclass": pool_class,
                    "pool_pre_ping": True,
                    "pool_reset_on_return": 'commit',
                    "future": True,
                }
            
            self.engine = create_async_engine(
                self.database_url,
                echo=self.settings.database.echo,
                **engine_kwargs
            )
            
            self.session_factory = async_sessionmaker(
                bind=self.engine,
                class_=AsyncSession,
                expire_on_commit=False,
                autoflush=True,
                autocommit=False,
            )
            
            # Test connection
            await self._test_connection()
            self._is_connected = True
            
            logger.info("Database connection initialized successfully")
            
        except Exception as e:
            logger.error(f"Failed to initialize database connection: {e}")
            raise
    
    async def _test_connection(self) -> None:
        """Test database connection with a simple query."""
        if not self.engine:
            raise RuntimeError("Database engine not initialized")
        
        try:
            async with self.engine.begin() as conn:
                await conn.execute(text("SELECT 1"))
            logger.debug("Database connection test successful")
        except Exception as e:
            logger.error(f"Database connection test failed: {e}")
            raise
    
    async def health_check(self) -> bool:
        """Perform database health check."""
        if not self._is_connected or not self.engine:
            return False
        
        try:
            await self._test_connection()
            return True
        except Exception as e:
            logger.warning(f"Database health check failed: {e}")
            self._is_connected = False
            return False
    
    async def reconnect(self) -> None:
        """Attempt to reconnect to the database."""
        logger.info("Attempting to reconnect to database...")
        
        if self.engine:
            await self.close()
        
        await self.initialize()
    
    async def close(self) -> None:
        """Close database connections and cleanup resources."""
        if self.engine:
            await self.engine.dispose()
            self.engine = None
            self.session_factory = None
            self._is_connected = False
            logger.info("Database connections closed")
    
    @asynccontextmanager
    async def get_session(self) -> AsyncGenerator[AsyncSession, None]:
        """
        Get async database session with automatic cleanup.
        
        Usage:
            async with db_manager.get_session() as session:
                # Use session here
                result = await session.execute(query)
        """
        if not self.session_factory:
            raise RuntimeError("Database not initialized. Call initialize() first.")
        
        session = self.session_factory()
        try:
            yield session
            await session.commit()
        except Exception as e:
            await session.rollback()
            logger.error(f"Database session error: {e}")
            raise
        finally:
            await session.close()
    
    @asynccontextmanager
    async def get_transaction(self) -> AsyncGenerator[AsyncSession, None]:
        """
        Get async database session with explicit transaction management.
        
        The session will be automatically rolled back if an exception occurs.
        You must manually commit if you want changes to persist.
        """
        if not self.session_factory:
            raise RuntimeError("Database not initialized. Call initialize() first.")
        
        session = self.session_factory()
        try:
            async with session.begin():
                yield session
        except Exception as e:
            logger.error(f"Database transaction error: {e}")
            raise
        finally:
            await session.close()
    
    async def execute_with_retry(
        self, 
        operation,
        max_retries: int = 3,
        delay: float = 1.0
    ):
        """
        Execute database operation with retry logic.
        
        Args:
            operation: Async function to execute
            max_retries: Maximum number of retry attempts
            delay: Delay between retries in seconds
        """
        last_exception = None
        
        for attempt in range(max_retries + 1):
            try:
                return await operation()
            except (DisconnectionError, SQLAlchemyError) as e:
                last_exception = e
                
                if attempt < max_retries:
                    logger.warning(
                        f"Database operation failed (attempt {attempt + 1}/{max_retries + 1}): {e}"
                    )
                    
                    # Try to reconnect if connection was lost
                    if isinstance(e, DisconnectionError):
                        try:
                            await self.reconnect()
                        except Exception as reconnect_error:
                            logger.error(f"Reconnection failed: {reconnect_error}")
                    
                    await asyncio.sleep(delay * (2 ** attempt))  # Exponential backoff
                else:
                    logger.error(f"Database operation failed after {max_retries + 1} attempts: {e}")
        
        raise last_exception
    
    def is_connected(self) -> bool:
        """Check if database is connected."""
        return self._is_connected


# Global database manager instance
db_manager = DatabaseManager()


async def init_database() -> None:
    """Initialize global database manager."""
    await db_manager.initialize()


async def close_database() -> None:
    """Close global database manager."""
    await db_manager.close()


@asynccontextmanager
async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """
    Get database session from global manager.
    
    Convenience function for getting a database session.
    """
    async with db_manager.get_session() as session:
        yield session


@asynccontextmanager 
async def get_transaction() -> AsyncGenerator[AsyncSession, None]:
    """
    Get database transaction from global manager.
    
    Convenience function for getting a database transaction.
    """
    async with db_manager.get_transaction() as session:
        yield session


async def health_check() -> bool:
    """Perform database health check."""
    return await db_manager.health_check()


# Session dependency for dependency injection
async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    """
    Database session dependency for dependency injection.
    
    Use this in your handlers or services that need database access.
    """
    async with get_session() as session:
        yield session
