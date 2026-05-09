import hashlib
import json
from datetime import datetime
from Crypto.PublicKey import RSA
from Crypto.Signature import pkcs1_15
from Crypto.Hash import SHA256

class CryptoUtils:
    @staticmethod
    def hash_data(data):
        """Generate SHA-256 hash"""
        if isinstance(data, dict):
            data = json.dumps(data, sort_keys=True)
        return hashlib.sha256(str(data).encode()).hexdigest()
    
    @staticmethod
    def generate_key_pair():
        """Generate RSA key pair for digital signatures"""
        key = RSA.generate(2048)
        private_key = key.export_key()
        public_key = key.publickey().export_key()
        return private_key.decode(), public_key.decode()
    
    @staticmethod
    def sign_data(private_key_str, data):
        """Sign data with private key"""
        key = RSA.import_key(private_key_str.encode())
        h = SHA256.new(json.dumps(data, sort_keys=True).encode())
        signature = pkcs1_15.new(key).sign(h)
        return signature.hex()
    
    @staticmethod
    def verify_signature(public_key_str, data, signature):
        """Verify signature with public key"""
        try:
            key = RSA.import_key(public_key_str.encode())
            h = SHA256.new(json.dumps(data, sort_keys=True).encode())
            pkcs1_15.new(key).verify(h, bytes.fromhex(signature))
            return True
        except (ValueError, TypeError):
            return False