"""
Enhanced memory store with token-based access and secure preview support.
"""
import threading
import time
import hashlib
import secrets
from typing import Dict, Optional
from datetime import datetime, timedelta

class SecureMemoryEntry:
    """Secure memory entry with automatic wipe"""
    
    def __init__(self, file_id: str, file_data: bytes, metadata: dict = None,
                 ttl_seconds: int = 60, one_time: bool = True):
        self.store_key = secrets.token_urlsafe(16)
        self.file_id = file_id
        self.file_data = bytearray(file_data)  # Mutable for secure wipe
        self.metadata = metadata or {}
        self.created_at = time.time()
        self.expires_at = self.created_at + ttl_seconds
        self.access_count = 0
        self.max_access = 1 if one_time else 999
        self.one_time = one_time
    
    def is_expired(self) -> bool:
        """Check if entry has expired"""
        return time.time() > self.expires_at
    
    def can_access(self) -> bool:
        """Check if entry can be accessed"""
        return not self.is_expired() and self.access_count < self.max_access
    
    def get_data(self) -> Optional[bytes]:
        """Get file data and increment access counter"""
        if self.can_access():
            self.access_count += 1
            return bytes(self.file_data)  # Return immutable copy
        return None
    
    def secure_wipe(self):
        """Securely wipe data from memory"""
        if self.file_data:
            # Overwrite multiple times
            length = len(self.file_data)
            # Pass 1: zeros
            for i in range(length):
                self.file_data[i] = 0x00
            # Pass 2: ones
            for i in range(length):
                self.file_data[i] = 0xFF
            # Pass 3: zeros
            for i in range(length):
                self.file_data[i] = 0x00
            # Clear reference
            self.file_data = bytearray()
    
    def to_dict(self) -> dict:
        """Convert to dictionary for display"""
        return {
            'store_key': self.store_key[:8] + '...',
            'file_id': self.file_id[:16] + '...',
            'size': len(self.file_data) if self.file_data else 0,
            'age': int(time.time() - self.created_at),
            'expires_in': int(self.expires_at - time.time()),
            'access_count': self.access_count,
            'one_time': self.one_time,
            'filename': self.metadata.get('filename', 'unknown')
        }

class MemoryStore:
    """
    Enhanced memory store with token-based access and auto-wipe.
    Supports both one-time access and TTL-based expiration.
    """
    
    def __init__(self, cleanup_interval: int = 10, default_ttl: int = 60):
        self.store: Dict[str, SecureMemoryEntry] = {}
        self.cleanup_interval = cleanup_interval
        self.default_ttl = default_ttl
        self.lock = threading.Lock()
        
        # Start cleanup thread
        self.cleanup_thread = threading.Thread(target=self._cleanup_loop, daemon=True)
        self.cleanup_thread.start()
        
        print(f"🧠 Memory store initialized (TTL: {default_ttl}s)")
    
    def store_file(self, file_id: str, file_data: bytes, 
                  metadata: dict = None, ttl_seconds: int = None,
                  one_time: bool = True) -> str:
        """
        Store file data in memory with secure auto-wipe.
        
        Args:
            file_id: Original file identifier
            file_data: File bytes to store
            metadata: Additional metadata (filename, type, etc.)
            ttl_seconds: Time-to-live in seconds (default: 60)
            one_time: Whether to allow only one access
            
        Returns:
            Secure access token
        """
        if ttl_seconds is None:
            ttl_seconds = self.default_ttl
        
        # Create secure memory entry
        entry = SecureMemoryEntry(
            file_id=file_id,
            file_data=file_data,
            metadata=metadata or {},
            ttl_seconds=ttl_seconds,
            one_time=one_time
        )
        
        with self.lock:
            self.store[entry.store_key] = entry
        
        print(f"✅ Stored {metadata.get('filename', file_id[:16])} in memory")
        print(f"   Token: {entry.store_key[:16]}... (expires in {ttl_seconds}s, one_time={one_time})")
        
        return entry.store_key
    
    def retrieve_file(self, store_key: str) -> Optional[bytes]:
        """
        Retrieve file data from memory.
        Data is automatically wiped if one_time access.
        
        Args:
            store_key: Secure access token
            
        Returns:
            File bytes or None if not found/expired
        """
        with self.lock:
            entry = self.store.get(store_key)
            
            if not entry:
                print(f"❌ Invalid store key: {store_key[:16]}...")
                return None
            
            if entry.is_expired():
                print(f"⚠️ Store key expired: {store_key[:16]}...")
                self.secure_wipe(store_key)
                return None
            
            # Get data (increments access counter)
            data = entry.get_data()
            
            if data is None:
                print(f"⚠️ Store key max accesses reached: {store_key[:16]}...")
                if entry.one_time:
                    self.secure_wipe(store_key)
                return None
            
            # If one-time access and this was the last access, schedule wipe
            if entry.one_time and not entry.can_access():
                threading.Thread(
                    target=self._delayed_wipe,
                    args=(store_key,),
                    daemon=True
                ).start()
            
            return data
    
    def _delayed_wipe(self, store_key: str, delay: float = 1.0):
        """Delayed secure wipe after file access"""
        import time
        time.sleep(delay)
        self.secure_wipe(store_key)
    
    def secure_wipe(self, store_key: str) -> bool:
        """
        Securely wipe data from memory.
        
        Returns:
            True if wiped, False if not found
        """
        with self.lock:
            entry = self.store.pop(store_key, None)
            if entry:
                entry.secure_wipe()
                print(f"🗑️ Securely wiped memory for token {store_key[:16]}...")
                return True
        
        return False
    
    def _cleanup_loop(self):
        """Background thread to clean up expired entries"""
        while True:
            time.sleep(self.cleanup_interval)
            
            with self.lock:
                expired_keys = [
                    key for key, entry in self.store.items()
                    if entry.is_expired()
                ]
                
                for key in expired_keys:
                    self.secure_wipe(key)
    
    def get_stats(self) -> dict:
        """Get memory store statistics"""
        with self.lock:
            total_size = sum(len(entry.file_data) for entry in self.store.values())
            
            return {
                'total_entries': len(self.store),
                'total_memory': total_size,
                'default_ttl': self.default_ttl,
                'entries': [entry.to_dict() for entry in self.store.values()]
            }

# Global memory store instance
memory_store = MemoryStore(default_ttl=60)