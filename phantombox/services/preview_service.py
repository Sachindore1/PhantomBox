"""
Secure preview service for PhantomBox.
Files are stored in RAM with TTL and one-time access tokens.
"""
import secrets
import time
import threading
import hashlib
from typing import Dict, Optional, Tuple
from datetime import datetime, timedelta
import os

class PreviewToken:
    """Represents a secure preview token with TTL"""
    
    def __init__(self, file_id: str, file_data: bytes, filename: str, 
                 file_type: str, ttl_seconds: int = 60):
        self.token = secrets.token_urlsafe(32)
        self.file_id = file_id
        self.file_data = bytearray(file_data)  # Mutable for secure wipe
        self.filename = filename
        self.file_type = file_type
        self.size = len(file_data)
        self.created_at = time.time()
        self.expires_at = self.created_at + ttl_seconds
        self.access_count = 0
        self.max_access = 1  # One-time access by default
        self.preview_sent = False
    
    def is_expired(self) -> bool:
        """Check if token has expired"""
        return time.time() > self.expires_at
    
    def can_access(self) -> bool:
        """Check if token can be used for access"""
        return not self.is_expired() and self.access_count < self.max_access
    
    def secure_wipe(self):
        """Securely wipe file data from memory"""
        if self.file_data:
            # Overwrite multiple times (simplified DoD 5220.22-M)
            for i in range(len(self.file_data)):
                self.file_data[i] = 0x00
            for i in range(len(self.file_data)):
                self.file_data[i] = 0xFF
            for i in range(len(self.file_data)):
                self.file_data[i] = 0x00
            self.file_data = bytearray()
    
    def get_preview_data(self) -> Optional[bytes]:
        """Get preview data and mark as accessed"""
        if self.can_access():
            self.access_count += 1
            self.preview_sent = True
            return bytes(self.file_data)  # Return immutable copy
        return None
    
    def to_dict(self) -> dict:
        """Convert to dictionary for status display"""
        return {
            'token': self.token[:16] + '...',
            'file_id': self.file_id[:16] + '...',
            'filename': self.filename,
            'type': self.file_type,
            'size': self.size,
            'expires_in': int(self.expires_at - time.time()),
            'accessed': self.access_count,
            'preview_sent': self.preview_sent
        }

class PreviewService:
    """
    Secure in-memory preview service.
    Files are stored only in RAM with automatic TTL-based cleanup.
    """
    
    def __init__(self, default_ttl: int = 60):
        self.default_ttl = default_ttl
        self.tokens: Dict[str, PreviewToken] = {}
        self.lock = threading.Lock()
        
        # Start cleanup thread
        self.cleanup_thread = threading.Thread(target=self._cleanup_loop, daemon=True)
        self.cleanup_thread.start()
        
        print(f"🔐 Preview service initialized (TTL: {default_ttl}s)")
    
    def create_preview(self, file_id: str, file_data: bytes, 
                      filename: str = None, file_type: str = None,
                      ttl_seconds: int = None) -> str:
        """
        Create a secure preview token for a file.
        
        Args:
            file_id: Original file identifier
            file_data: File bytes to preview
            filename: Original filename
            file_type: MIME type or file extension
            ttl_seconds: Time-to-live in seconds (default: 60)
            
        Returns:
            Preview token string
        """
        if ttl_seconds is None:
            ttl_seconds = self.default_ttl
        
        # Detect file type if not provided
        if not file_type:
            file_type = self._detect_file_type(file_data, filename)
        
        # Create token
        token = PreviewToken(
            file_id=file_id,
            file_data=file_data,
            filename=filename or f"preview_{file_id[:8]}",
            file_type=file_type,
            ttl_seconds=ttl_seconds
        )
        
        with self.lock:
            self.tokens[token.token] = token
        
        print(f"✅ Preview token created for {filename or file_id[:16]}...")
        print(f"   Token: {token.token[:16]}... (expires in {ttl_seconds}s)")
        
        return token.token
    
    def get_preview(self, token_str: str) -> Tuple[Optional[bytes], Optional[dict]]:
        """
        Retrieve preview data by token.
        One-time access - data is wiped after retrieval.
        
        Args:
            token_str: Preview token
            
        Returns:
            Tuple of (file_data, metadata) or (None, None) if invalid
        """
        with self.lock:
            token = self.tokens.get(token_str)
            
            if not token:
                print(f"❌ Invalid preview token: {token_str[:16]}...")
                return None, None
            
            if token.is_expired():
                print(f"⚠️ Preview token expired: {token_str[:16]}...")
                self._secure_wipe_token(token_str)
                return None, {'error': 'Token expired'}
            
            # Get preview data (this increments access count)
            data = token.get_preview_data()
            
            if data is None:
                print(f"⚠️ Preview token already used: {token_str[:16]}...")
                return None, {'error': 'Token already used'}
            
            # Prepare metadata
            metadata = {
                'filename': token.filename,
                'file_type': token.file_type,
                'size': token.size,
                'file_id': token.file_id,
                'expires_at': token.expires_at,
                'access_count': token.access_count
            }
            
            # If this was the last access, schedule secure wipe
            if not token.can_access():
                threading.Thread(
                    target=self._delayed_wipe,
                    args=(token_str,),
                    daemon=True
                ).start()
            
            return data, metadata
    
    def _delayed_wipe(self, token_str: str, delay: float = 1.0):
        """Delayed secure wipe after preview is served"""
        import time
        time.sleep(delay)
        self._secure_wipe_token(token_str)
    
    def _secure_wipe_token(self, token_str: str):
        """Securely wipe token data from memory"""
        with self.lock:
            token = self.tokens.pop(token_str, None)
            if token:
                token.secure_wipe()
                print(f"🗑️ Securely wiped preview data for token {token_str[:16]}...")
    
    def revoke_preview(self, token_str: str) -> bool:
        """Immediately revoke a preview token"""
        return self._secure_wipe_token(token_str)
    
    def _cleanup_loop(self):
        """Background thread to clean up expired tokens"""
        while True:
            time.sleep(10)  # Check every 10 seconds
            
            with self.lock:
                expired_tokens = [
                    token_str for token_str, token in self.tokens.items()
                    if token.is_expired()
                ]
                
                for token_str in expired_tokens:
                    self._secure_wipe_token(token_str)
    
    def get_stats(self) -> dict:
        """Get preview service statistics"""
        with self.lock:
            active_tokens = len(self.tokens)
            total_memory = sum(len(t.file_data) for t in self.tokens.values())
            
            return {
                'active_previews': active_tokens,
                'total_memory': total_memory,
                'default_ttl': self.default_ttl,
                'tokens': [token.to_dict() for token in self.tokens.values()][:10]  # First 10
            }
    
    def _detect_file_type(self, file_data: bytes, filename: str = None) -> str:
    
    
        # Check filename first
        if filename and '.' in filename:
            ext = filename.split('.')[-1].lower()
            if ext in ['pdf', 'txt', 'png', 'jpg', 'jpeg', 'gif', 'bmp', 'svg', 
                    'doc', 'docx', 'xls', 'xlsx', 'ppt', 'pptx']:
                return ext
        
        # Magic number detection
        try:
            if len(file_data) >= 4:
                if file_data[:4] == b'%PDF':
                    return 'pdf'
                elif file_data[:3] == b'\xFF\xD8\xFF':
                    return 'jpeg'
                elif file_data[:8] == b'\x89PNG\r\n\x1a\n':
                    return 'png'
                elif file_data[:6] in [b'GIF87a', b'GIF89a']:
                    return 'gif'
                elif file_data[:2] == b'BM':
                    return 'bmp'
                elif file_data[:2] == b'PK':
                    # Office Open XML detection
                    try:
                        if len(file_data) > 100:
                            sample = file_data[:8192]
                            if b'word/document.xml' in sample:
                                return 'docx'
                            elif b'xl/workbook.xml' in sample or b'xl/sharedStrings.xml' in sample:
                                return 'xlsx'
                            elif b'ppt/presentation.xml' in sample:
                                return 'pptx'
                    except:
                        pass
                    return 'zip'
                elif file_data[:8] == b'\xD0\xCF\x11\xE0\xA1\xB1\x1A\xE1':
                    # OLE Compound File (older Office)
                    if filename:
                        ext = filename.split('.')[-1].lower()
                        if ext in ['doc', 'xls', 'ppt']:
                            return ext
                    return 'ole'
        except:
            pass
        
        return 'bin'
# Global preview service instance
preview_service = PreviewService(default_ttl=60)