"""
Noise Storage Node with persistent disk storage and proper error handling.
"""
from flask import Flask, request, jsonify, Response, send_file
from flask_cors import CORS
import os
import hashlib
import json
import time
from datetime import datetime

app = Flask(__name__)
CORS(app)

# Configuration
STORAGE_ROOT = "noise_storage_B"
os.makedirs(STORAGE_ROOT, exist_ok=True)

def get_fragment_path(file_id, fragment_index):
    """Get file path for storing a fragment"""
    file_dir = os.path.join(STORAGE_ROOT, file_id)
    os.makedirs(file_dir, exist_ok=True)
    return os.path.join(file_dir, f"fragment_{fragment_index}.bin")

def get_metadata_path(file_id, fragment_index):
    """Get metadata file path"""
    file_dir = os.path.join(STORAGE_ROOT, file_id)
    os.makedirs(file_dir, exist_ok=True)
    return os.path.join(file_dir, f"fragment_{fragment_index}.meta.json")

@app.route('/store', methods=['POST'])
def store_fragment():
    """Store a hologram noise fragment persistently on disk"""
    try:
        if 'fragment' not in request.files:
            return jsonify({'error': 'No fragment provided'}), 400
        
        # Get parameters - try multiple possible field names
        file_id = request.form.get('file_id') or request.form.get('fileId')
        fragment_index = request.form.get('fragment_index') or request.form.get('fragmentIndex') or request.form.get('index')
        cipher_hash = request.form.get('cipher_hash') or request.form.get('cipherHash') or request.form.get('fragment_hash')
        encryption = request.form.get('encryption', 'AES-256-GCM')
        
        # Debug print received parameters
        print(f"📦 Received store request:")
        print(f"   file_id: {file_id}")
        print(f"   fragment_index: {fragment_index}")
        print(f"   cipher_hash: {cipher_hash[:16] if cipher_hash else 'None'}...")
        print(f"   encryption: {encryption}")
        
        if not file_id:
            return jsonify({'error': 'Missing file_id parameter'}), 400
        if fragment_index is None:
            return jsonify({'error': 'Missing fragment_index parameter'}), 400
        if not cipher_hash:
            return jsonify({'error': 'Missing cipher_hash parameter'}), 400
        
        # Convert fragment_index to int if it's a string
        try:
            fragment_index = int(fragment_index)
        except ValueError:
            return jsonify({'error': f'Invalid fragment_index: {fragment_index}'}), 400
        
        # Read the encrypted fragment
        fragment_file = request.files['fragment']
        fragment_data = fragment_file.read()
        
        # Verify fragment hash matches expected
        actual_hash = hashlib.sha256(fragment_data).hexdigest()
        if actual_hash != cipher_hash:
            print(f"⚠️ Hash mismatch! Expected: {cipher_hash[:16]}..., Got: {actual_hash[:16]}...")
            # Continue anyway? Or reject? Let's accept but log warning
            print(f"   Warning: Storing fragment with hash mismatch")
        
        # Save fragment to disk
        frag_path = get_fragment_path(file_id, fragment_index)
        with open(frag_path, 'wb') as f:
            f.write(fragment_data)
        
        # Save metadata
        metadata = {
            'file_id': file_id,
            'fragment_index': fragment_index,
            'cipher_hash': actual_hash,  # Store actual hash
            'expected_hash': cipher_hash, # Store expected hash for debugging
            'encryption': encryption,
            'size_bytes': len(fragment_data),
            'timestamp': datetime.now().isoformat(),
            'node': os.path.basename(STORAGE_ROOT)
        }
        
        meta_path = get_metadata_path(file_id, fragment_index)
        with open(meta_path, 'w') as f:
            json.dump(metadata, f, indent=2)
        
        print(f"💾 Stored fragment {fragment_index} for file {file_id}")
        print(f"   Path: {frag_path}")
        print(f"   Size: {len(fragment_data)} bytes")
        print(f"   Hash: {actual_hash[:16]}...")
        
        return jsonify({
            'success': True,
            'message': 'Fragment stored successfully',
            'file_id': file_id,
            'fragment_index': fragment_index,
            'size': len(fragment_data),
            'hash': actual_hash[:16],
            'path': frag_path
        })
        
    except Exception as e:
        print(f"❌ Error storing fragment: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': f'Storage failed: {str(e)}'}), 500

@app.route('/retrieve/<file_id>/<int:fragment_index>', methods=['GET'])
def retrieve_fragment(file_id, fragment_index):
    """Retrieve a hologram noise fragment from disk"""
    try:
        frag_path = get_fragment_path(file_id, fragment_index)
        
        if not os.path.exists(frag_path):
            return jsonify({'error': f'Fragment not found: {file_id}/{fragment_index}'}), 404
        
        print(f"📂 Loading fragment {fragment_index} for file {file_id} from disk")
        
        with open(frag_path, 'rb') as f:
            fragment_data = f.read()
        
        print(f"✅ Loaded {len(fragment_data)} bytes")
        
        return Response(
            fragment_data,
            mimetype='application/octet-stream',
            headers={
                'Content-Disposition': f'attachment; filename=fragment_{fragment_index}.bin',
                'X-Fragment-Type': 'encrypted-hologram-noise',
                'X-Fragment-Size': str(len(fragment_data))
            }
        )
        
    except Exception as e:
        print(f"❌ Error retrieving fragment: {e}")
        return jsonify({'error': f'Retrieval failed: {str(e)}'}), 500

@app.route('/cleanup/<file_id>/<int:fragment_index>', methods=['DELETE'])
def cleanup_fragment(file_id, fragment_index):
    """Clean up a stored fragment"""
    try:
        frag_path = get_fragment_path(file_id, fragment_index)
        meta_path = get_metadata_path(file_id, fragment_index)
        
        fragments_deleted = 0
        
        if os.path.exists(frag_path):
            os.remove(frag_path)
            fragments_deleted += 1
        
        if os.path.exists(meta_path):
            os.remove(meta_path)
        
        # Try to remove empty directory
        file_dir = os.path.join(STORAGE_ROOT, file_id)
        if os.path.exists(file_dir):
            try:
                if not os.listdir(file_dir):
                    os.rmdir(file_dir)
            except:
                pass
        
        if fragments_deleted > 0:
            print(f"🗑️ Cleaned up fragment {fragment_index} for file {file_id}")
            return jsonify({'success': True, 'message': 'Fragment cleaned up'})
        
        return jsonify({'error': 'Fragment not found'}), 404
        
    except Exception as e:
        return jsonify({'error': f'Cleanup failed: {str(e)}'}), 500

@app.route('/status', methods=['GET'])
def status():
    """Get node status"""
    try:
        fragments = []
        total_size = 0
        
        if os.path.exists(STORAGE_ROOT):
            for file_id in os.listdir(STORAGE_ROOT):
                file_dir = os.path.join(STORAGE_ROOT, file_id)
                if os.path.isdir(file_dir):
                    for fname in os.listdir(file_dir):
                        if fname.startswith("fragment_") and fname.endswith(".bin"):
                            try:
                                frag_index = int(fname.replace("fragment_", "").replace(".bin", ""))
                                frag_path = os.path.join(file_dir, fname)
                                size = os.path.getsize(frag_path)
                                total_size += size
                                fragments.append({
                                    'file_id': file_id,
                                    'fragment_index': frag_index,
                                    'size': size
                                })
                            except:
                                pass
        
        return jsonify({
            'node': os.path.basename(STORAGE_ROOT),
            'status': 'active',
            'fragment_count': len(fragments),
            'total_size': total_size,
            'storage_root': STORAGE_ROOT,
            'fragments': fragments[:10]  # First 10 for display
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/test', methods=['GET'])
def test():
    """Test endpoint"""
    return jsonify({
        'node': os.path.basename(STORAGE_ROOT),
        'status': 'running',
        'storage_root': STORAGE_ROOT,
        'port': 9002
    })

if __name__ == '__main__':
    print("\n" + "="*60)
    print(f"🚀 Starting Persistent Noise Storage Node: {os.path.basename(STORAGE_ROOT)}")
    print("="*60)
    print(f"💾 Storage directory: ./{STORAGE_ROOT}/")
    print(f"🌐 Port: 9002")
    print(f"📁 Status: http://localhost:9002/status")
    print(f"🧪 Test: http://localhost:9002/test")
    print("="*60 + "\n")
    
    # Create storage directory if it doesn't exist
    os.makedirs(STORAGE_ROOT, exist_ok=True)
    
    app.run(host='0.0.0.0', port=9002, debug=False, threaded=True)