import unittest
import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from phantomnet.blockchain import Blockchain, Block

class TestBlockchain(unittest.TestCase):
    def test_genesis_block(self):
        blockchain = Blockchain()
        self.assertEqual(len(blockchain.chain), 1)
        self.assertEqual(blockchain.chain[0].index, 0)
        self.assertEqual(blockchain.chain[0].previous_hash, "0")
    
    def test_add_block(self):
        blockchain = Blockchain()
        block_data = {'test': 'data'}
        blockchain.add_block(block_data)
        
        self.assertEqual(len(blockchain.chain), 2)
        self.assertEqual(blockchain.chain[1].data, block_data)
    
    def test_chain_validity(self):
        blockchain = Blockchain()
        blockchain.add_block({'test': 'data1'})
        blockchain.add_block({'test': 'data2'})
        
        self.assertTrue(blockchain.is_chain_valid())
    
    def test_file_registration(self):
        blockchain = Blockchain()
        file_id = "test123"
        file_hash = "abc123"
        fragment_map = {"frag1": "node1", "frag2": "node2"}
        
        blockchain.register_file_metadata(file_id, file_hash, fragment_map)
        
        metadata = blockchain.get_file_metadata(file_id)
        self.assertIsNotNone(metadata)
        self.assertEqual(metadata['file_hash'], file_hash)
        self.assertEqual(metadata['fragment_map'], fragment_map)

if __name__ == '__main__':
    unittest.main()