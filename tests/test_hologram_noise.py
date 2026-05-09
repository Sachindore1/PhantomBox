import unittest
import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from phantombox.services.pattern_engine import HologramNoiseGenerator

class TestHologramNoise(unittest.TestCase):
    def setUp(self):
        self.noise_gen = HologramNoiseGenerator(fragment_count=3)
    
    def test_fragment_generation(self):
        test_data = b"This is a test file for PhantomBox secure storage."
        fragments = self.noise_gen.generate_noise_fragments(test_data)
        
        self.assertEqual(len(fragments), 3)
        
        # Each fragment should have header
        for fragment in fragments:
            self.assertIn(b'F', fragment)
            self.assertIn(b':', fragment)
    
    def test_reconstruction(self):
        original_data = b"Original data that needs to be secured."
        
        # Generate fragments
        fragments = self.noise_gen.generate_noise_fragments(original_data)
        
        # Reconstruct
        reconstructed = self.noise_gen.reconstruct_from_fragments(fragments)
        
        # Should reconstruct to original length
        self.assertEqual(len(reconstructed), len(original_data))
    
    def test_fragment_map(self):
        file_hash = "test_hash_123"
        fragment_hashes = ["hash1", "hash2", "hash3"]
        
        fragment_map = self.noise_gen.generate_fragment_map(file_hash, fragment_hashes)
        
        self.assertEqual(fragment_map['file_hash'], file_hash)
        self.assertEqual(len(fragment_map['fragments']), 3)

if __name__ == '__main__':
    unittest.main()