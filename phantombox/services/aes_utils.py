"""
AES-GCM encryption utilities for PhantomBox.
Provides authenticated encryption with HKDF key derivation.
"""
import os
import hashlib
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.hkdf import HKDF
from cryptography.hazmat.backends import default_backend
import secrets
from typing import Tuple, Optional

class AESGCMCipher:
    """
    AES-256-GCM authenticated encryption.
    Uses HKDF for key derivation from system secret.
    """
    
    def __init__(self):
        """Initialize with system secret from environment"""
        self.system_secret = os.getenv('SYSTEM_SECRET', 
            'default_insecure_secret_change_in_production').encode()
        self.backend = default_backend()
        
        if self.system_secret == b'default_insecure_secret_change_in_production':
            print("⚠️ WARNING: Using default SYSTEM_SECRET. Change this in production!")
    
    def _derive_key(self, salt: bytes, context: bytes) -> bytes:
        """
        Derive AES-256 key using HKDF.
        """
        hkdf = HKDF(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            info=context,
            backend=self.backend
        )
        return hkdf.derive(self.system_secret)
    
    def encrypt(self, plaintext: bytes, aad: bytes = None, context: bytes = b'default') -> Tuple[bytes, bytes, bytes, bytes]:
        """
        Encrypt data using AES-256-GCM.
        
        Returns:
            Tuple of (ciphertext, nonce, auth_tag, salt) - 4 values!
        """
        # Generate random salt and nonce
        salt = secrets.token_bytes(16)
        nonce = secrets.token_bytes(12)
        
        # Derive key using HKDF
        key = self._derive_key(salt, context)
        
        # Create cipher
        cipher = Cipher(
            algorithms.AES(key),
            modes.GCM(nonce),
            backend=self.backend
        )
        
        encryptor = cipher.encryptor()
        
        # Add additional authenticated data if provided
        if aad:
            encryptor.authenticate_additional_data(aad)
        
        # Encrypt
        ciphertext = encryptor.update(plaintext) + encryptor.finalize()
        
        # Get auth tag
        auth_tag = encryptor.tag
        
        return ciphertext, nonce, auth_tag, salt  # 4 values!
    
    def decrypt(self, ciphertext: bytes, nonce: bytes, auth_tag: bytes, 
                salt: bytes, aad: bytes = None, context: bytes = b'default') -> Optional[bytes]:
        """
        Decrypt and verify AES-256-GCM ciphertext.
        """
        try:
            # Derive key using same salt and context
            key = self._derive_key(salt, context)
            
            # Create cipher
            cipher = Cipher(
                algorithms.AES(key),
                modes.GCM(nonce, auth_tag),
                backend=self.backend
            )
            
            decryptor = cipher.decryptor()
            
            # Add additional authenticated data if provided
            if aad:
                decryptor.authenticate_additional_data(aad)
            
            # Decrypt
            plaintext = decryptor.update(ciphertext) + decryptor.finalize()
            
            return plaintext
            
        except Exception as e:
            print(f"❌ Decryption failed: {e}")
            return None
    
    def encrypt_fragment(self, fragment_data: bytes, fragment_index: int, 
                        file_hash: str) -> Tuple[bytes, bytes, bytes, bytes]:
        """
        Encrypt a fragment with fragment-specific context.
        
        Returns:
            Tuple of (ciphertext, nonce, auth_tag, salt)
        """
        context = f"fragment_{fragment_index}_{file_hash[:16]}".encode()
        aad = file_hash.encode()
        return self.encrypt(fragment_data, aad, context)
    
    def decrypt_fragment(self, ciphertext: bytes, nonce: bytes, auth_tag: bytes,
                        salt: bytes, fragment_index: int, file_hash: str) -> Optional[bytes]:
        """
        Decrypt a fragment with fragment-specific context.
        """
        context = f"fragment_{fragment_index}_{file_hash[:16]}".encode()
        aad = file_hash.encode()
        return self.decrypt(ciphertext, nonce, auth_tag, salt, aad, context)

# Singleton instance
aes_cipher = AESGCMCipher()