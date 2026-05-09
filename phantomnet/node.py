from flask import Flask, request, jsonify
from flask_cors import CORS
import threading
import time
import requests
import json
import hashlib
from datetime import datetime

app = Flask(__name__)
CORS(app)

# Simple Block class
class SimpleBlock:
    def __init__(self, index, timestamp, data, previous_hash):
        self.index = index
        self.timestamp = timestamp
        self.data = data
        self.previous_hash = previous_hash
        self.nonce = 0
        self.hash = self.calculate_hash()
    
    def calculate_hash(self):
        block_string = json.dumps({
            'index': self.index,
            'timestamp': self.timestamp,
            'data': self.data,
            'previous_hash': self.previous_hash,
            'nonce': self.nonce
        }, sort_keys=True)
        return hashlib.sha256(str(block_string).encode()).hexdigest()
    
    def to_dict(self):
        return {
            'index': self.index,
            'timestamp': self.timestamp,
            'data': self.data,
            'previous_hash': self.previous_hash,
            'hash': self.hash,
            'nonce': self.nonce
        }

class SimpleBlockchain:
    def __init__(self):
        self.chain = []
        self.create_genesis_block()
    
    def create_genesis_block(self):
        genesis_block = SimpleBlock(0, time.time(), {
            'type': 'genesis',
            'message': 'PhantomNet Genesis Block'
        }, "0")
        self.chain.append(genesis_block)
    
    def get_last_block(self):
        return self.chain[-1]
    
    def add_block(self, data, validator_key=None):
        last_block = self.get_last_block()
        new_block = SimpleBlock(
            index=len(self.chain),
            timestamp=time.time(),
            data=data,
            previous_hash=last_block.hash
        )
        self.chain.append(new_block)
        return new_block
    
    def register_file_metadata(self, file_id, file_hash, fragment_map, access_rules=None):
        metadata = {
            'type': 'file_registration',
            'file_id': file_id,
            'file_hash': file_hash,
            'fragment_map': fragment_map,
            'timestamp': time.time(),
            'access_rules': access_rules or {}
        }
        
        block = self.add_block(metadata)
        print(f"File {file_id} registered in block {block.index}")
        return True
    
    def get_file_metadata(self, file_id):
        for block in reversed(self.chain):
            if (block.data.get('type') == 'file_registration' and 
                block.data.get('file_id') == file_id):
                return block.data
        return None
    
    def to_dict(self):
        return [block.to_dict() for block in self.chain]

class AuthorityValidator:
    def __init__(self, authorized_nodes):
        self.authorized_nodes = authorized_nodes
    
    def validate_node(self, node_id):
        return node_id in self.authorized_nodes
    
    def validate_block(self, block_data, validator_id):
        if not self.validate_node(validator_id):
            return False
        
        if block_data.get('type') == 'file_registration':
            required = ['file_id', 'file_hash', 'fragment_map']
            return all(field in block_data for field in required)
        
        return True

class FileRegistry:
    def __init__(self, blockchain):
        self.blockchain = blockchain
        self.file_index = {}
    
    def register(self, file_id, file_hash, fragment_map, access_rules=None):
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
    
    def verify(self, file_id, provided_hash):
        metadata = self.blockchain.get_file_metadata(file_id)
        if not metadata:
            return False
        return metadata['file_hash'] == provided_hash
    
    def get_fragment_map(self, file_id):
        metadata = self.blockchain.get_file_metadata(file_id)
        return metadata.get('fragment_map', {}) if metadata else {}

class BlockchainNode:
    def __init__(self, node_id, port, is_genesis=False, peer_url=None):
        self.node_id = node_id
        self.port = port
        self.blockchain = SimpleBlockchain()
        self.registry = FileRegistry(self.blockchain)
        self.peer_url = peer_url
        self.is_genesis = is_genesis
        
        # Simple authority - for demo, accept all
        self.authority = AuthorityValidator(['node1_key', 'node2_key'])
        
        if not is_genesis and peer_url:
            threading.Thread(target=self.sync_with_peer, daemon=True).start()
    
    def sync_with_peer(self):
        time.sleep(2)
        try:
            response = requests.get(f"{self.peer_url}/chain")
            if response.status_code == 200:
                peer_chain = response.json()['chain']
                if len(peer_chain) > len(self.blockchain.chain):
                    # Simple sync - replace with longer chain
                    self.blockchain.chain = []
                    for block_data in peer_chain:
                        block = SimpleBlock(
                            block_data['index'],
                            block_data['timestamp'],
                            block_data['data'],
                            block_data['previous_hash']
                        )
                        block.hash = block_data['hash']
                        self.blockchain.chain.append(block)
                    print(f"Node {self.node_id} synced with peer")
        except Exception as e:
            print(f"Sync failed: {e}")

node = None

@app.route('/')
def home():
    return f"PhantomNet Node: {node.node_id} (Port: {node.port})"

@app.route('/chain', methods=['GET'])
def get_chain():
    return jsonify({
        'chain': node.blockchain.to_dict(),
        'length': len(node.blockchain.chain)
    })

# In phantomnet/node.py, update the register_file function:

@app.route('/register', methods=['POST'])
def register_file():
    data = request.json
    
    # For demo, skip complex validation
    required = ['file_id', 'file_hash', 'fragment_map']
    if not all(field in data for field in required):
        return jsonify({'error': 'Missing required fields'}), 400
    
    success = node.registry.register(
        data['file_id'],
        data['file_hash'],
        data['fragment_map'],
        data.get('access_rules', {})
    )
    
    if success:
        # Store additional metadata in the blockchain entry
        metadata = {
            'type': 'file_registration',
            'file_id': data['file_id'],
            'file_hash': data['file_hash'],
            'fragment_map': data['fragment_map'],
            'original_filename': data.get('original_filename', 'unknown'),
            'original_size': data.get('original_size', 0),
            'timestamp': time.time(),
            'access_rules': data.get('access_rules', {})
        }
        
        # Propagate to peer if exists
        if node.peer_url:
            try:
                requests.post(f"{node.peer_url}/register", json=metadata, timeout=2)
            except:
                pass
        
        return jsonify({
            'success': True, 
            'message': 'File registered',
            'block_index': len(node.blockchain.chain) - 1
        })
    return jsonify({'error': 'Registration failed'}), 500


@app.route('/verify/<file_id>', methods=['GET'])
def verify_file(file_id):
    provided_hash = request.args.get('hash')
    if not provided_hash:
        return jsonify({'error': 'Hash required'}), 400
    
    is_valid = node.registry.verify(file_id, provided_hash)
    return jsonify({'valid': is_valid})

@app.route('/fragments/<file_id>', methods=['GET'])
def get_fragments(file_id):
    fragment_map = node.registry.get_fragment_map(file_id)
    return jsonify({'fragment_map': fragment_map})

@app.route('/status', methods=['GET'])
def status():
    return jsonify({
        'node_id': node.node_id,
        'is_genesis': node.is_genesis,
        'chain_length': len(node.blockchain.chain),
        'peer_url': node.peer_url,
        'status': 'running'
    })

@app.route('/test', methods=['GET'])
def test():
    """Simple test endpoint"""
    return jsonify({
        'message': f'Node {node.node_id} is running',
        'port': node.port,
        'time': datetime.now().isoformat()
    })

def run_node(node_id, port, is_genesis=False, peer_url=None):
    """Start blockchain node"""
    global node
    node = BlockchainNode(node_id, port, is_genesis, peer_url)
    print(f"🚀 Starting {node_id} node on port {port}")
    print(f"   Genesis: {is_genesis}")
    print(f"   Peer URL: {peer_url}")
    print(f"   Access at: http://localhost:{port}")
    app.run(host='0.0.0.0', port=port, debug=False, threaded=True)

if __name__ == '__main__':
    import sys
    if len(sys.argv) > 3:
        node_id = sys.argv[1]
        port = int(sys.argv[2])
        is_genesis = sys.argv[3] == 'genesis'
        peer_url = sys.argv[4] if len(sys.argv) > 4 else None
        run_node(node_id, port, is_genesis, peer_url)
    else:
        print("Usage: python node.py <node_id> <port> <genesis|peer> [peer_url]")
        print("Example (Genesis): python node.py genesis 5001 genesis")
        print("Example (Peer): python node.py peer 5002 http://localhost:5001")