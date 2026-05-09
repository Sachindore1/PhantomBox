import time
from typing import Dict
class FileRegistry:
    def __init__(self, blockchain):
        self.blockchain = blockchain
        self.file_index = {}
    
    def register(self, file_id: str, file_hash: str, fragment_map: Dict, 
                access_rules: Dict = None) -> bool:
        """Register file metadata"""
        success = self.blockchain.register_file_metadata(
            file_id, file_hash, fragment_map, access_rules
        )
        if success:
            self.file_index[file_id] = {
                'hash': file_hash,
                'timestamp': time.time(),
                'block_index': len(self.blockchain.chain) - 1
            }
        return success
    
    def verify(self, file_id: str, provided_hash: str) -> bool:
        """Verify file integrity against blockchain record"""
        metadata = self.blockchain.get_file_metadata(file_id)
        if not metadata:
            return False
        return metadata['file_hash'] == provided_hash
    
    def get_fragment_map(self, file_id: str) -> Dict:
        """Get fragment distribution map for a file"""
        metadata = self.blockchain.get_file_metadata(file_id)
        return metadata.get('fragment_map', {}) if metadata else {}