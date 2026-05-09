import requests
from ..config import AppConfig

class BlockchainVerifier:
    def __init__(self):
        self.genesis_node = AppConfig.GENESIS_NODE
        self.peer_node = AppConfig.PEER_NODE
    
    def verify_file_registration(self, file_id: str, file_hash: str) -> bool:
        """
        Verify file registration on blockchain.
        """
        try:
            # Try genesis node first
            response = requests.get(
                f"{self.genesis_node}/verify/{file_id}",
                params={'hash': file_hash},
                timeout=5
            )
            
            if response.status_code == 200:
                return response.json().get('valid', False)
            
            # Fall back to peer node
            response = requests.get(
                f"{self.peer_node}/verify/{file_id}",
                params={'hash': file_hash},
                timeout=5
            )
            
            if response.status_code == 200:
                return response.json().get('valid', False)
            
        except Exception as e:
            print(f"Verification failed: {e}")
        
        return False
    
    def register_file_metadata(self, metadata: dict) -> bool:
        """
        Register file metadata on blockchain.
        """
        try:
            # Register on genesis node
            response = requests.post(
                f"{self.genesis_node}/register",
                json=metadata,
                timeout=5
            )
            
            if response.status_code == 200:
                print(f"File {metadata['file_id']} registered on blockchain")
                return True
            
        except Exception as e:
            print(f"Registration failed: {e}")
        
        return False
    
    def get_fragment_map(self, file_id: str) -> dict:
        """
        Get fragment map from blockchain.
        """
        try:
            response = requests.get(
                f"{self.genesis_node}/fragments/{file_id}",
                timeout=5
            )
            
            if response.status_code == 200:
                return response.json().get('fragment_map', {})
            
        except Exception as e:
            print(f"Failed to get fragment map: {e}")
        
        return {}