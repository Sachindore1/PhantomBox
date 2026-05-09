import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    GENESIS_NODE = os.getenv('GENESIS_NODE', 'http://127.0.0.1:5001')
    PEER_NODE = os.getenv('PEER_NODE', 'http://127.0.0.1:5002')
    NOISE_NODES = os.getenv('NOISE_NODES', '').split(',')
    AUTHORITY_KEYS = os.getenv('AUTHORITY_KEYS', '').split(',')
    
    @classmethod
    def get_noise_nodes(cls):
        return [node.strip() for node in cls.NOISE_NODES if node.strip()]