import json
import time
from typing import List, Dict, Any, Optional
from .crypto_utils import CryptoUtils

class Block:
    def __init__(self, index: int, timestamp: float, data: Dict, previous_hash: str):
        self.index = index
        self.timestamp = timestamp
        self.data = data
        self.previous_hash = previous_hash
        self.nonce = 0
        self.hash = self.calculate_hash()
    
    def calculate_hash(self) -> str:
        """Calculate hash of the block"""
        block_string = json.dumps({
            'index': self.index,
            'timestamp': self.timestamp,
            'data': self.data,
            'previous_hash': self.previous_hash,
            'nonce': self.nonce
        }, sort_keys=True)
        return CryptoUtils.hash_data(block_string)
    
    def to_dict(self) -> Dict:
        """Convert block to dictionary"""
        return {
            'index': self.index,
            'timestamp': self.timestamp,
            'data': self.data,
            'previous_hash': self.previous_hash,
            'hash': self.hash,
            'nonce': self.nonce
        }

class Blockchain:
    def __init__(self):
        self.chain: List[Block] = []
        self.pending_transactions: List[Dict] = []
        self.difficulty = 2
        self.create_genesis_block()
    
    def create_genesis_block(self):
        """Create the first block in the chain"""
        genesis_block = Block(0, time.time(), {
            'type': 'genesis',
            'message': 'PhantomNet Genesis Block'
        }, "0")
        self.chain.append(genesis_block)
    
    def get_last_block(self) -> Block:
        """Get the last block in the chain"""
        return self.chain[-1]
    
    def add_block(self, data: Dict, validator_key: str = None) -> Block:
        """Add a new block to the chain (Proof-of-Authority)"""
        last_block = self.get_last_block()
        
        new_block = Block(
            index=len(self.chain),
            timestamp=time.time(),
            data=data,
            previous_hash=last_block.hash
        )
        
        # In PoA, we simply accept the block (simplified)
        self.chain.append(new_block)
        return new_block
    
    def is_chain_valid(self) -> bool:
        """Validate the entire blockchain"""
        for i in range(1, len(self.chain)):
            current_block = self.chain[i]
            previous_block = self.chain[i-1]
            
            # Check hash integrity
            if current_block.hash != current_block.calculate_hash():
                return False
            
            # Check chain linkage
            if current_block.previous_hash != previous_block.hash:
                return False
        
        return True

    def register_file_metadata(self, file_id: str, file_hash: str, fragment_map: Dict, 
                              access_rules: Dict = None) -> bool:
        """
        Register file metadata on blockchain with encrypted fragment info.
        """
        metadata = {
            'type': 'file_registration',
            'file_id': file_id,
            'file_hash': file_hash,
            'encryption': fragment_map.get('encryption', 'AES-256-GCM'),
            'key_derivation': fragment_map.get('key_derivation', 'HKDF-SHA256'),
            'fragment_count': fragment_map.get('fragment_count', 3),
            'fragment_map': {
                frag_id: {
                    'cipher_hash': frag_info.get('cipher_hash'),  # Hash of ciphertext
                    'index': frag_info.get('index'),
                    'nonce': frag_info.get('nonce'),  # Store nonce in blockchain
                    'salt': frag_info.get('salt')     # Store salt in blockchain
                }
                for frag_id, frag_info in fragment_map.get('fragments', {}).items()
            },
            'storage_map': fragment_map.get('storage_map', {}),
            'original_filename': fragment_map.get('original_filename'),
            'original_size': fragment_map.get('original_size'),
            'timestamp': time.time(),
            'access_rules': access_rules or {}
        }
        
        block = self.add_block(metadata)
        print(f"File {file_id} registered in block {block.index}")
        print(f"   Encryption: AES-256-GCM with HKDF key derivation")
        print(f"   Fragment cipher hashes stored: {len(metadata['fragment_map'])}")
        return True
    
    def get_file_metadata(self, file_id: str) -> Dict:
        """Retrieve file metadata from blockchain"""
        for block in reversed(self.chain):
            if (block.data.get('type') == 'file_registration' and 
                block.data.get('file_id') == file_id):
                return block.data
        return None
    
    def to_dict(self) -> List[Dict]:
        """Convert blockchain to list of dictionaries"""
        return [block.to_dict() for block in self.chain]