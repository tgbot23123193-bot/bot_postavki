"""
AES-256 encryption service for secure API key storage.

This module provides enterprise-grade encryption for storing sensitive
API keys with unique salts and secure key derivation.
"""

import os
import base64
import secrets
from typing import Tuple, Optional
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.backends import default_backend
from cryptography.exceptions import InvalidSignature

from ..config import get_settings


class EncryptionError(Exception):
    """Custom exception for encryption operations."""
    pass


class EncryptionService:
    """
    AES-256 encryption service for API keys.
    
    Features:
    - AES-256-GCM encryption for authenticated encryption
    - PBKDF2 key derivation with unique salts
    - Base64 encoding for database storage
    - Secure random salt generation
    - Protection against timing attacks
    """
    
    def __init__(self, master_key: Optional[str] = None):
        """
        Initialize encryption service.
        
        Args:
            master_key: Master encryption key. If None, uses from settings.
        """
        self.settings = get_settings()
        self._master_key = master_key or self.settings.security.encryption_key
        
        if len(self._master_key.encode()) < 32:
            raise EncryptionError("Master key must be at least 32 bytes long")
        
        self.backend = default_backend()
    
    def _derive_key(self, password: str, salt: bytes, iterations: int = 100000) -> bytes:
        """
        Derive encryption key from master password and salt using PBKDF2.
        
        Args:
            password: Master password
            salt: Unique salt for key derivation
            iterations: Number of PBKDF2 iterations
            
        Returns:
            Derived 32-byte encryption key
        """
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,  # 256 bits
            salt=salt,
            iterations=iterations,
            backend=self.backend
        )
        return kdf.derive(password.encode())
    
    def generate_salt(self, length: int = 32) -> bytes:
        """
        Generate cryptographically secure random salt.
        
        Args:
            length: Salt length in bytes
            
        Returns:
            Random salt bytes
        """
        return secrets.token_bytes(length)
    
    def encrypt_api_key(self, api_key: str) -> Tuple[str, str]:
        """
        Encrypt API key with AES-256-GCM.
        
        Args:
            api_key: Plain text API key to encrypt
            
        Returns:
            Tuple of (encrypted_data_base64, salt_base64)
        """
        try:
            # Generate unique salt for this API key
            salt = self.generate_salt()
            
            # Derive encryption key
            derived_key = self._derive_key(self._master_key, salt)
            
            # Generate random IV for GCM mode
            iv = secrets.token_bytes(12)  # 96 bits for GCM
            
            # Create cipher
            cipher = Cipher(
                algorithms.AES(derived_key),
                modes.GCM(iv),
                backend=self.backend
            )
            encryptor = cipher.encryptor()
            
            # Encrypt the API key
            ciphertext = encryptor.update(api_key.encode()) + encryptor.finalize()
            
            # Combine IV, ciphertext, and auth tag
            encrypted_data = iv + ciphertext + encryptor.tag
            
            # Encode to base64 for storage
            encrypted_b64 = base64.b64encode(encrypted_data).decode('utf-8')
            salt_b64 = base64.b64encode(salt).decode('utf-8')
            
            return encrypted_b64, salt_b64
            
        except Exception as e:
            raise EncryptionError(f"Encryption failed: {str(e)}")
    
    def decrypt_api_key(self, encrypted_data_b64: str, salt_b64: str) -> str:
        """
        Decrypt API key from encrypted data.
        
        Args:
            encrypted_data_b64: Base64 encoded encrypted data
            salt_b64: Base64 encoded salt
            
        Returns:
            Decrypted API key
        """
        try:
            # Decode from base64
            encrypted_data = base64.b64decode(encrypted_data_b64)
            salt = base64.b64decode(salt_b64)
            
            # Extract IV, ciphertext, and auth tag
            iv = encrypted_data[:12]  # First 12 bytes
            auth_tag = encrypted_data[-16:]  # Last 16 bytes
            ciphertext = encrypted_data[12:-16]  # Middle part
            
            # Derive decryption key
            derived_key = self._derive_key(self._master_key, salt)
            
            # Create cipher
            cipher = Cipher(
                algorithms.AES(derived_key),
                modes.GCM(iv, auth_tag),
                backend=self.backend
            )
            decryptor = cipher.decryptor()
            
            # Decrypt and return
            plaintext = decryptor.update(ciphertext) + decryptor.finalize()
            return plaintext.decode('utf-8')
            
        except Exception as e:
            raise EncryptionError(f"Decryption failed: {str(e)}")
    
    def is_encrypted_data_valid(self, encrypted_data_b64: str, salt_b64: str) -> bool:
        """
        Validate encrypted data without decrypting.
        
        Args:
            encrypted_data_b64: Base64 encoded encrypted data
            salt_b64: Base64 encoded salt
            
        Returns:
            True if data appears to be valid encrypted data
        """
        try:
            # Basic validation
            encrypted_data = base64.b64decode(encrypted_data_b64)
            salt = base64.b64decode(salt_b64)
            
            # Check minimum sizes
            if len(encrypted_data) < 28:  # IV(12) + min_ciphertext(1) + tag(16)
                return False
            
            if len(salt) < 16:  # Minimum salt size
                return False
            
            return True
            
        except Exception:
            return False
    
    def rotate_encryption(self, encrypted_data_b64: str, salt_b64: str, new_master_key: str) -> Tuple[str, str]:
        """
        Rotate encryption with new master key.
        
        Args:
            encrypted_data_b64: Current encrypted data
            salt_b64: Current salt
            new_master_key: New master key for encryption
            
        Returns:
            Tuple of (new_encrypted_data_b64, new_salt_b64)
        """
        # Decrypt with current key
        api_key = self.decrypt_api_key(encrypted_data_b64, salt_b64)
        
        # Create new encryption service with new key
        new_service = EncryptionService(new_master_key)
        
        # Re-encrypt with new key
        return new_service.encrypt_api_key(api_key)


# Global encryption service instance
encryption_service = EncryptionService()


def encrypt_api_key(api_key: str) -> Tuple[str, str]:
    """
    Convenience function to encrypt API key.
    
    Args:
        api_key: Plain text API key
        
    Returns:
        Tuple of (encrypted_data_base64, salt_base64)
    """
    return encryption_service.encrypt_api_key(api_key)


def decrypt_api_key(encrypted_data_b64: str, salt_b64: str) -> str:
    """
    Convenience function to decrypt API key.
    
    Args:
        encrypted_data_b64: Base64 encoded encrypted data
        salt_b64: Base64 encoded salt
        
    Returns:
        Decrypted API key
    """
    return encryption_service.decrypt_api_key(encrypted_data_b64, salt_b64)


def validate_encrypted_data(encrypted_data_b64: str, salt_b64: str) -> bool:
    """
    Convenience function to validate encrypted data.
    
    Args:
        encrypted_data_b64: Base64 encoded encrypted data
        salt_b64: Base64 encoded salt
        
    Returns:
        True if data is valid
    """
    return encryption_service.is_encrypted_data_valid(encrypted_data_b64, salt_b64)
