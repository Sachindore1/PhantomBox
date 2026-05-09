"""
Hologram Noise Pattern Engine with AES-GCM encryption.
Files are encrypted per fragment with unique keys.
"""
import hashlib
import struct
from typing import List, Dict, Tuple, Optional
import os
from .aes_utils import aes_cipher

class HologramNoiseGenerator:
    """
    Generates hologram noise fragments using AES-GCM encryption.
    Each fragment is independently encrypted with unique key.
    """
    
    def __init__(self, fragment_count: int = 3):
        self.fragment_count = fragment_count
        self.system_secret = os.getenv('SYSTEM_SECRET', 
            'default_insecure_secret_change_in_production')
    
    def generate_noise_fragments(self, file_data: bytes, file_hash: str = None) -> List[bytes]:
        """
        Convert file data into encrypted hologram noise fragments.
        
        Args:
            file_data: Original file bytes
            file_hash: SHA-256 hash of file (generated if not provided)
            
        Returns:
            List of encrypted fragment bytes
        """
        if not file_data:
            return []
        
        # Generate file hash if not provided
        if not file_hash:
            file_hash = hashlib.sha256(file_data).hexdigest()
        
        data_length = len(file_data)
        
        # Calculate fragment size (round up)
        fragment_size = (data_length + self.fragment_count - 1) // self.fragment_count
        
        # Pad data to ensure equal fragment sizes
        padded_length = fragment_size * self.fragment_count
        padding_needed = padded_length - data_length
        padded_data = file_data + bytes(padding_needed)
        
        fragments = []
        
        for i in range(self.fragment_count):
            # Extract this fragment's portion
            start_idx = i * fragment_size
            end_idx = start_idx + fragment_size
            fragment_data = padded_data[start_idx:end_idx]
            
            # 🔐 AES-GCM encrypt the fragment
            ciphertext, nonce, auth_tag, salt = aes_cipher.encrypt_fragment(
                fragment_data, i, file_hash
            )
            
            # Build fragment with metadata header
            fragment = bytearray()
            
            # Header: index (2 bytes), original size (4 bytes), 
            # fragment size (4 bytes), encrypted flag (1 byte)
            header = struct.pack('!HIIB', i, data_length, fragment_size, 0x01)
            fragment.extend(header)
            
            # Store encryption metadata
            # nonce (12 bytes), auth_tag (16 bytes), salt (16 bytes)
            fragment.extend(nonce)
            fragment.extend(auth_tag)
            fragment.extend(salt)
            
            # Store ciphertext
            fragment.extend(ciphertext)
            
            # Add fragment hash for integrity check (8 bytes)
            fragment_hash = hashlib.sha256(ciphertext).digest()[:8]
            fragment.extend(fragment_hash)
            
            fragments.append(bytes(fragment))
            
            print(f"🔐 Generated fragment {i}: total={len(fragment)} bytes")
        
        return fragments
    
    def reconstruct_from_fragments(self, fragments: List[bytes], file_hash: str = None) -> bytes:
        """
        Reconstruct original file from encrypted fragments.
        
        Args:
            fragments: List of encrypted fragment bytes
            file_hash: Expected file hash (for verification)
            
        Returns:
            Reconstructed file bytes
        """
        if len(fragments) < 2:
            raise ValueError(f"Insufficient fragments. Need at least 2, got {len(fragments)}")
        
        parsed_fragments = []
        original_size = None
        fragment_size = None
        
        for fragment in fragments:
            try:
                # Parse header (11 bytes: H + I + I + B)
                if len(fragment) < 11:
                    continue
                
                header = fragment[:11]
                frag_index, orig_size, frag_size, encrypted_flag = struct.unpack('!HIIB', header)
                
                if encrypted_flag != 0x01:
                    print(f"Warning: Fragment {frag_index} not encrypted with expected flag")
                
                if original_size is None:
                    original_size = orig_size
                    fragment_size = frag_size
                
                # Calculate positions
                pos = 11
                
                # Extract encryption metadata
                nonce = fragment[pos:pos+12]
                pos += 12
                
                auth_tag = fragment[pos:pos+16]
                pos += 16
                
                salt = fragment[pos:pos+16]
                pos += 16
                
                # Extract ciphertext
                ciphertext = fragment[pos:pos+frag_size]
                pos += frag_size
                
                # Extract fragment hash
                fragment_hash = fragment[pos:pos+8]
                
                # Verify fragment integrity
                calculated_hash = hashlib.sha256(ciphertext).digest()[:8]
                if calculated_hash != fragment_hash:
                    print(f"Warning: Fragment {frag_index} hash mismatch - possible corruption")
                    continue
                
                parsed_fragments.append({
                    'index': frag_index,
                    'ciphertext': ciphertext,
                    'nonce': nonce,
                    'auth_tag': auth_tag,
                    'salt': salt,
                    'fragment_size': frag_size
                })
                
            except Exception as e:
                print(f"Error parsing fragment: {e}")
                continue
        
        if not parsed_fragments:
            raise ValueError("No valid fragments found")
        
        # Sort by fragment index
        parsed_fragments.sort(key=lambda x: x['index'])
        
        # Need file hash for decryption context
        if not file_hash:
            print("⚠️ No file hash provided, attempting decryption with placeholder")
            file_hash = "unknown_hash_placeholder"
        
        # Reconstruct
        padded_size = fragment_size * len(parsed_fragments)
        result = bytearray(padded_size)
        
        for frag_info in parsed_fragments:
            frag_index = frag_info['index']
            ciphertext = frag_info['ciphertext']
            nonce = frag_info['nonce']
            auth_tag = frag_info['auth_tag']
            salt = frag_info['salt']
            
            # 🔐 AES-GCM decrypt the fragment
            decrypted_data = aes_cipher.decrypt_fragment(
                ciphertext, nonce, auth_tag, salt, frag_index, file_hash
            )
            
            if decrypted_data is None:
                print(f"❌ Failed to decrypt fragment {frag_index}")
                continue
            
            # Place decrypted data in correct position
            start_idx = frag_index * fragment_size
            for j in range(len(decrypted_data)):
                if start_idx + j < len(result):
                    result[start_idx + j] = decrypted_data[j]
        
        # Trim padding and return only original data
        return bytes(result[:original_size])
    
    def generate_fragment_map(self, file_hash: str, fragment_hashes: List[str], 
                             fragments_metadata: List[Dict] = None) -> dict:
        """
        Generate map of fragments with encryption metadata.
        
        Args:
            file_hash: SHA-256 hash of original file
            fragment_hashes: List of fragment ciphertext hashes
            fragments_metadata: List of fragment encryption metadata (already hex strings!)
            
        Returns:
            Fragment map dictionary for blockchain registration
        """
        fragment_map = {
            'file_hash': file_hash,
            'encryption': 'AES-256-GCM',
            'key_derivation': 'HKDF-SHA256',
            'fragment_count': len(fragment_hashes),
            'fragments': {},
            'storage_map': {}
        }
        
        for i, frag_hash in enumerate(fragment_hashes):
            fragment_map['fragments'][f"fragment_{i}"] = {
                'cipher_hash': frag_hash,
                'index': i,
                'encrypted': True
            }
            
            # Add encryption metadata if provided
            # IMPORTANT: fragments_metadata already contains hex strings, NOT bytes!
            if fragments_metadata and i < len(fragments_metadata):
                # Get the hex strings directly - NO .hex() call!
                nonce_hex = fragments_metadata[i].get('nonce')
                salt_hex = fragments_metadata[i].get('salt')
                
                if nonce_hex:
                    fragment_map['fragments'][f"fragment_{i}"]['nonce'] = nonce_hex
                if salt_hex:
                    fragment_map['fragments'][f"fragment_{i}"]['salt'] = salt_hex
            
            # Distribute fragments across nodes (round-robin)
            node_index = i % 2
            fragment_map['storage_map'][f"fragment_{i}"] = {
                'node': f"http://127.0.0.1:{9001 + node_index}",
                'cipher_hash': frag_hash,
                'index': i
            }
        
        return fragment_map