import requests
import hashlib
import time
import struct
from typing import List, Dict, Optional
from ..config import AppConfig
from .pattern_engine import HologramNoiseGenerator
from .aes_utils import aes_cipher

class FragmentDispersal:
    """
    Handles dispersion of encrypted fragments to storage nodes.
    Stores ciphertext only - no keys, no plaintext.
    """
    
    def __init__(self):
        self.config = AppConfig
        self.noise_gen = HologramNoiseGenerator(self.config.FRAGMENT_COUNT)
        self.noise_nodes = self.config.NOISE_NODES
    
    def disperse_file(self, file_data: bytes, file_name: str) -> Optional[Dict]:
        """
        Convert file to encrypted fragments and distribute across storage nodes.
        
        Returns:
            Metadata for blockchain registration containing cipher hashes and locations.
        """
        if not file_data:
            return None
        
        # Generate file hash for verification and key derivation
        file_hash = hashlib.sha256(file_data).hexdigest()
        file_id = f"{file_hash[:16]}_{int(time.time())}"
        
        print(f"🔐 Encrypting file {file_name} with AES-256-GCM")
        print(f"   File hash: {file_hash[:32]}...")
        print(f"   File ID: {file_id}")
        
        # Generate encrypted hologram noise fragments
        fragments = self.noise_gen.generate_noise_fragments(file_data, file_hash)
        
        if len(fragments) != self.config.FRAGMENT_COUNT:
            raise ValueError(f"Expected {self.config.FRAGMENT_COUNT} fragments, got {len(fragments)}")
        
        print(f"✅ Generated {len(fragments)} encrypted fragments")
        for i, frag in enumerate(fragments):
            print(f"   Fragment {i}: {len(frag)} bytes")
        
        # Calculate hashes of ciphertext
        fragment_cipher_hashes = [hashlib.sha256(frag).hexdigest() for frag in fragments]
        
        # Extract encryption metadata from fragments for blockchain record
        fragments_metadata = []
        for i, fragment in enumerate(fragments):
            try:
                # Parse header to extract nonce and salt
                if len(fragment) < 11:
                    print(f"⚠️ Fragment {i} too short: {len(fragment)} bytes")
                    fragments_metadata.append({'index': i})
                    continue
                
                # Header: index (2), original_size (4), fragment_size (4), flag (1)
                header = fragment[:11]
                _, _, _, _ = struct.unpack('!HIIB', header)
                
                pos = 11
                # Extract nonce (12 bytes)
                nonce = fragment[pos:pos+12]
                pos += 12
                
                # Skip auth_tag (16 bytes)
                pos += 16
                
                # Extract salt (16 bytes)
                salt = fragment[pos:pos+16]
                
                # IMPORTANT: Convert to hex strings for JSON serialization
                nonce_hex = nonce.hex()
                salt_hex = salt.hex()
                
                fragments_metadata.append({
                    'index': i,
                    'nonce': nonce_hex,  # Store as hex string
                    'salt': salt_hex      # Store as hex string
                })
                
                print(f"   Fragment {i}: nonce={nonce_hex[:8]}..., salt={salt_hex[:8]}...")
                
            except Exception as e:
                print(f"⚠️ Could not extract metadata from fragment {i}: {e}")
                fragments_metadata.append({'index': i})
        
        print(f"📡 Noise nodes: {self.noise_nodes}")
        
        # Distribute fragments to noise nodes
        fragment_map = {}
        successful_stores = []
        
        for i, (fragment, cipher_hash) in enumerate(zip(fragments, fragment_cipher_hashes)):
            node_index = i % len(self.noise_nodes)
            node_url = self.noise_nodes[node_index]
            
            print(f"📤 Sending fragment {i} to {node_url}...")
            
            try:
                # Store encrypted fragment on noise node
                response = requests.post(
                    f"{node_url}/store",
                    files={
                        'fragment': (f"fragment_{i}_{cipher_hash[:8]}.enc", fragment, 'application/octet-stream')
                    },
                    data={
                        'file_id': file_id,
                        'fragment_index': str(i),
                        'cipher_hash': cipher_hash,
                        'encryption': 'AES-256-GCM'
                    },
                    timeout=10
                )
                
                if response.status_code == 200:
                    fragment_map[f"fragment_{i}"] = {
                        'node': node_url,
                        'cipher_hash': cipher_hash,
                        'index': i
                    }
                    successful_stores.append(i)
                    print(f"✅ Stored fragment {i} on {node_url}")
                    print(f"   Response: {response.json().get('message', 'OK')}")
                else:
                    print(f"❌ Failed to store fragment {i}: HTTP {response.status_code}")
                    print(f"   Response: {response.text[:200]}")
                    
            except requests.exceptions.ConnectionError:
                print(f"❌ Connection error: Cannot reach {node_url}")
            except Exception as e:
                print(f"❌ Error storing fragment {i}: {type(e).__name__}: {e}")
        
        # Check if we have enough fragments for reconstruction
        if len(successful_stores) < self.config.MIN_FRAGMENTS:
            self._cleanup_fragments(file_id, successful_stores)
            raise ValueError(f"Insufficient fragments stored. Need {self.config.MIN_FRAGMENTS}, got {len(successful_stores)}")
        
        print(f"✅ Successfully stored {len(successful_stores)} fragments")
        
        # Generate fragment map for blockchain with encryption metadata
        full_fragment_map = self.noise_gen.generate_fragment_map(
            file_hash, 
            fragment_cipher_hashes,
            fragments_metadata  # Now contains hex strings, not bytes
        )
        full_fragment_map['storage_map'] = fragment_map
        full_fragment_map['original_filename'] = file_name
        full_fragment_map['original_size'] = len(file_data)
        
        return {
            'file_id': file_id,
            'file_name': file_name,
            'file_hash': file_hash,
            'original_size': len(file_data),
            'fragment_count': len(fragments),
            'fragment_map': full_fragment_map,
            'timestamp': time.time(),
            'encryption': 'AES-256-GCM',
            'key_derivation': 'HKDF-SHA256'
        }
    
    def _cleanup_fragments(self, file_id: str, fragment_indices: List[int]):
        """Clean up fragments if storage fails"""
        for i in fragment_indices:
            node_index = i % len(self.noise_nodes)
            node_url = self.noise_nodes[node_index]
            try:
                requests.delete(f"{node_url}/cleanup/{file_id}/{i}", timeout=5)
            except:
                pass
    
    def retrieve_fragments(self, file_id: str, fragment_map: Dict) -> List[bytes]:
        """Retrieve encrypted fragments from storage nodes."""
        fragments = []
        for frag_id, frag_info in fragment_map.get('storage_map', {}).items():
            node_url = frag_info['node']
            fragment_index = frag_info['index']
            try:
                response = requests.get(
                    f"{node_url}/retrieve/{file_id}/{fragment_index}",
                    timeout=15
                )
                if response.status_code == 200:
                    fragments.append(response.content)
                    print(f"✅ Retrieved fragment {fragment_index} from {node_url}")
            except Exception as e:
                print(f"❌ Error retrieving fragment {fragment_index}: {e}")
        return fragments