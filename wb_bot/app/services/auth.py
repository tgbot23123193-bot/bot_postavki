"""
Authentication and API key management service.

This module handles API key validation, encryption, and management
for secure interaction with Wildberries API.
"""

import asyncio
from typing import List, Optional, Tuple
from datetime import datetime

from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from ..database import get_session, User, APIKey
from ..api import WBAPIClient, WBAPIError
from ..utils.encryption import encrypt_api_key, decrypt_api_key
from ..utils.logger import get_logger, UserLogger
from ..config import get_settings

logger = get_logger(__name__)


class AuthService:
    """
    Service for managing user authentication and API keys.
    
    Features:
    - API key validation with WB API
    - Secure encryption/decryption of API keys
    - User API key management (add, remove, validate)
    - Rate limiting and usage tracking
    - Automatic key validation and cleanup
    """
    
    def __init__(self):
        """Initialize auth service."""
        self.settings = get_settings()
    
    async def validate_api_key(self, api_key: str) -> Tuple[bool, Optional[str]]:
        """
        Validate API key with Wildberries API.
        
        Args:
            api_key: API key to validate
            
        Returns:
            Tuple of (is_valid, error_message)
        """
        try:
            async with WBAPIClient(api_key) as client:
                validation_response = await client.validate_api_key()
                return validation_response.is_valid, None
                
        except WBAPIError as e:
            logger.warning(f"API key validation failed: {e}")
            return False, str(e)
        except Exception as e:
            logger.error(f"Unexpected error during API key validation: {e}")
            return False, "Unexpected validation error"
    
    async def add_api_key(
        self, 
        user_id: int, 
        api_key: str, 
        name: Optional[str] = None,
        description: Optional[str] = None
    ) -> Tuple[bool, str]:
        """
        Add new API key for user.
        
        Args:
            user_id: User ID
            api_key: API key to add
            name: Optional name for the key
            description: Optional description
            
        Returns:
            Tuple of (success, message)
        """
        user_logger = UserLogger(user_id)
        
        async with get_session() as session:
            # Check if user exists
            user_query = select(User).where(User.id == user_id)
            user_result = await session.execute(user_query)
            user = user_result.scalar_one_or_none()
            
            if not user:
                return False, "User not found"
            
            # Check API key limit
            existing_keys_query = select(APIKey).where(
                and_(
                    APIKey.user_id == user_id,
                    APIKey.is_active == True
                )
            )
            existing_keys_result = await session.execute(existing_keys_query)
            existing_keys = existing_keys_result.scalars().all()
            
            if len(existing_keys) >= self.settings.monitoring.max_api_keys_per_user:
                return False, f"Maximum {self.settings.monitoring.max_api_keys_per_user} API keys allowed"
            
            # Check if API key already exists
            for existing_key in existing_keys:
                try:
                    decrypted_existing = decrypt_api_key(existing_key.encrypted_key, existing_key.salt)
                    if decrypted_existing == api_key:
                        return False, "This API key is already added"
                except Exception:
                    # If decryption fails, skip this key
                    continue
            
            # Validate API key with WB
            is_valid, error_message = await self.validate_api_key(api_key)
            
            if not is_valid:
                user_logger.warning("Failed to add invalid API key")
                return False, f"Invalid API key: {error_message}"
            
            # Encrypt and store API key
            try:
                encrypted_key, salt = encrypt_api_key(api_key)
                
                new_api_key = APIKey(
                    user_id=user_id,
                    encrypted_key=encrypted_key,
                    salt=salt,
                    name=name or f"API Key {len(existing_keys) + 1}",
                    description=description,
                    is_valid=True,
                    is_active=True,
                    last_validation=datetime.utcnow()
                )
                
                session.add(new_api_key)
                await session.commit()
                
                user_logger.info(f"Added new API key: {new_api_key.name}")
                return True, "API key added successfully"
                
            except Exception as e:
                logger.error(f"Failed to encrypt and store API key: {e}")
                return False, "Failed to store API key"
    
    async def remove_api_key(self, user_id: int, api_key_id: int) -> Tuple[bool, str]:
        """
        Remove API key for user.
        
        Args:
            user_id: User ID
            api_key_id: API key ID to remove
            
        Returns:
            Tuple of (success, message)
        """
        user_logger = UserLogger(user_id)
        
        async with get_session() as session:
            # Find API key
            query = select(APIKey).where(
                and_(
                    APIKey.id == api_key_id,
                    APIKey.user_id == user_id
                )
            )
            result = await session.execute(query)
            api_key = result.scalar_one_or_none()
            
            if not api_key:
                return False, "API key not found"
            
            # Deactivate instead of deleting (for audit trail)
            api_key.is_active = False
            session.add(api_key)
            await session.commit()
            
            user_logger.info(f"Removed API key: {api_key.name}")
            return True, "API key removed successfully"
    
    async def get_user_api_keys(self, user_id: int) -> List[APIKey]:
        """
        Get all active API keys for user.
        
        Args:
            user_id: User ID
            
        Returns:
            List of API keys
        """
        async with get_session() as session:
            query = select(APIKey).where(
                and_(
                    APIKey.user_id == user_id,
                    APIKey.is_active == True
                )
            ).order_by(APIKey.created_at.desc())
            
            result = await session.execute(query)
            return result.scalars().all()
    
    async def get_decrypted_api_keys(self, user_id: int) -> List[str]:
        """
        Get decrypted API keys for user.
        
        Args:
            user_id: User ID
            
        Returns:
            List of decrypted API keys
        """
        api_keys = await self.get_user_api_keys(user_id)
        decrypted_keys = []
        
        for api_key in api_keys:
            try:
                decrypted = decrypt_api_key(api_key.encrypted_key, api_key.salt)
                decrypted_keys.append(decrypted)
            except Exception as e:
                logger.error(f"Failed to decrypt API key {api_key.id}: {e}")
                # Mark key as invalid
                await self._mark_key_invalid(api_key.id, str(e))
        
        return decrypted_keys
    
    async def validate_all_user_keys(self, user_id: int) -> Tuple[int, int]:
        """
        Validate all API keys for user.
        
        Args:
            user_id: User ID
            
        Returns:
            Tuple of (valid_count, total_count)
        """
        user_logger = UserLogger(user_id)
        api_keys = await self.get_user_api_keys(user_id)
        
        valid_count = 0
        validation_tasks = []
        
        for api_key in api_keys:
            task = self._validate_single_key(api_key)
            validation_tasks.append(task)
        
        results = await asyncio.gather(*validation_tasks, return_exceptions=True)
        
        for i, result in enumerate(results):
            if isinstance(result, bool) and result:
                valid_count += 1
            elif isinstance(result, Exception):
                logger.error(f"Error validating API key {api_keys[i].id}: {result}")
        
        user_logger.info(f"Validated API keys: {valid_count}/{len(api_keys)} valid")
        return valid_count, len(api_keys)
    
    async def _validate_single_key(self, api_key: APIKey) -> bool:
        """
        Validate single API key.
        
        Args:
            api_key: API key to validate
            
        Returns:
            True if valid, False otherwise
        """
        try:
            decrypted_key = decrypt_api_key(api_key.encrypted_key, api_key.salt)
            is_valid, error_message = await self.validate_api_key(decrypted_key)
            
            # Update validation status
            await self._update_key_validation(api_key.id, is_valid, error_message)
            
            return is_valid
            
        except Exception as e:
            logger.error(f"Failed to validate API key {api_key.id}: {e}")
            await self._mark_key_invalid(api_key.id, str(e))
            return False
    
    async def _update_key_validation(
        self, 
        api_key_id: int, 
        is_valid: bool, 
        error_message: Optional[str] = None
    ) -> None:
        """Update API key validation status."""
        async with get_session() as session:
            query = select(APIKey).where(APIKey.id == api_key_id)
            result = await session.execute(query)
            api_key = result.scalar_one_or_none()
            
            if api_key:
                api_key.is_valid = is_valid
                api_key.last_validation = datetime.utcnow()
                api_key.validation_error = error_message
                
                session.add(api_key)
                await session.commit()
    
    async def _mark_key_invalid(self, api_key_id: int, error_message: str) -> None:
        """Mark API key as invalid."""
        await self._update_key_validation(api_key_id, False, error_message)
    
    async def update_key_usage(self, api_key_id: int, success: bool) -> None:
        """
        Update API key usage statistics.
        
        Args:
            api_key_id: API key ID
            success: Whether the request was successful
        """
        async with get_session() as session:
            query = select(APIKey).where(APIKey.id == api_key_id)
            result = await session.execute(query)
            api_key = result.scalar_one_or_none()
            
            if api_key:
                api_key.total_requests += 1
                api_key.last_used = datetime.utcnow()
                
                if success:
                    api_key.successful_requests += 1
                else:
                    api_key.failed_requests += 1
                
                session.add(api_key)
                await session.commit()
    
    async def cleanup_invalid_keys(self) -> int:
        """
        Cleanup invalid API keys older than 7 days.
        
        Returns:
            Number of keys cleaned up
        """
        async with get_session() as session:
            # Find invalid keys older than 7 days
            cutoff_date = datetime.utcnow() - timedelta(days=7)
            
            query = select(APIKey).where(
                and_(
                    APIKey.is_valid == False,
                    APIKey.last_validation < cutoff_date
                )
            )
            
            result = await session.execute(query)
            invalid_keys = result.scalars().all()
            
            # Deactivate invalid keys
            for api_key in invalid_keys:
                api_key.is_active = False
                session.add(api_key)
            
            await session.commit()
            
            logger.info(f"Cleaned up {len(invalid_keys)} invalid API keys")
            return len(invalid_keys)
    
    async def get_key_statistics(self, user_id: int) -> dict:
        """
        Get API key statistics for user.
        
        Args:
            user_id: User ID
            
        Returns:
            Dictionary with statistics
        """
        api_keys = await self.get_user_api_keys(user_id)
        
        stats = {
            "total_keys": len(api_keys),
            "valid_keys": sum(1 for key in api_keys if key.is_valid),
            "total_requests": sum(key.total_requests for key in api_keys),
            "successful_requests": sum(key.successful_requests for key in api_keys),
            "failed_requests": sum(key.failed_requests for key in api_keys),
            "success_rate": 0.0
        }
        
        if stats["total_requests"] > 0:
            stats["success_rate"] = stats["successful_requests"] / stats["total_requests"]
        
        return stats


# Global auth service instance
auth_service = AuthService()
