import os
from dotenv import load_dotenv

load_dotenv()

class AppConfig:
    # PhantomNet nodes
    GENESIS_NODE = os.getenv('GENESIS_NODE', 'http://127.0.0.1:5001')
    PEER_NODE = os.getenv('PEER_NODE', 'http://127.0.0.1:5002')
    
    # Noise storage nodes
    NOISE_NODES = [
        node.strip() for node in 
        os.getenv('NOISE_NODES', 'http://127.0.0.1:9001,http://127.0.0.1:9002').split(',')
        if node.strip()
    ]
    
    # App configuration
    PHANTOMBOX_URL = os.getenv('PHANTOMBOX_URL', 'http://127.0.0.1:8000')
    FRAGMENT_COUNT = int(os.getenv('FRAGMENT_COUNT', '3'))
    MIN_FRAGMENTS = int(os.getenv('MIN_FRAGMENTS', '2'))
    
    # Security
    MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB
    ALLOWED_EXTENSIONS = {'txt', 'pdf', 'png', 'jpg', 'jpeg', 'doc', 'docx'}
    
    # Temporary storage
    TEMP_DIR = os.path.join(os.path.dirname(__file__), 'temp')
    LOG_DIR = os.path.join(os.path.dirname(__file__), 'logs')