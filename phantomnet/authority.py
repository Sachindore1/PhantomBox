from typing import List, Dict, Any

class AuthorityValidator:
    def __init__(self, authorized_nodes: List[str]):
        self.authorized_nodes = authorized_nodes
    
    def validate_node(self, node_id: str) -> bool:
        """Check if node is authorized to create blocks"""
        return node_id in self.authorized_nodes
    
    def validate_block(self, block_data: Dict, validator_id: str) -> bool:
        """Validate block creation request"""
        if not self.validate_node(validator_id):
            return False
        
        # Check required fields for file registration
        if block_data.get('type') == 'file_registration':
            required = ['file_id', 'file_hash', 'fragment_map']
            return all(field in block_data for field in required)
        
        return True