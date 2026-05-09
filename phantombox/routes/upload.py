"""
phantombox/routes/upload.py  — RBAC-aware version
Requires JWT. Records file ownership in MySQL after upload.
"""

from flask import Blueprint, request, jsonify
import time
from ..config import AppConfig
from ..services.dispersal import FragmentDispersal
from ..services.verifier  import BlockchainVerifier
from ..auth.middleware     import jwt_required
from ..auth.mysql_service  import register_file_owner
from ..auth.db             import write_audit
from flask import g

upload_bp = Blueprint('upload', __name__)
dispersal = FragmentDispersal()
verifier  = BlockchainVerifier()


@upload_bp.route('/upload', methods=['POST'])
@jwt_required
def upload_file():
    """
    Upload a file. Requires valid JWT.
    Records ownership in MySQL: only this user can later download.
    """
    if 'file' not in request.files:
        return jsonify({'error': 'No file provided'}), 400

    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': 'No file selected'}), 400

    # Size check
    file.seek(0, 2)
    file_size = file.tell()
    file.seek(0)
    if file_size > AppConfig.MAX_FILE_SIZE:
        return jsonify({'error': f'File too large. Max: {AppConfig.MAX_FILE_SIZE} bytes'}), 400

    file_data         = file.read()
    original_filename = file.filename
    current_user      = g.current_user   # injected by @jwt_required

    print(f"📤 Upload by {current_user['email']} [{current_user['role']}]: {original_filename}")

    try:
        # Encrypt + fragment + disperse
        metadata = dispersal.disperse_file(file_data, original_filename)
        if not metadata:
            return jsonify({'error': 'Failed to process file'}), 500

        file_id   = metadata['file_id']
        file_hash = metadata['file_hash']

        # Register on blockchain
        blockchain_metadata = {
            'type':              'file_registration',
            'file_id':           file_id,
            'file_hash':         file_hash,
            'fragment_map':      metadata['fragment_map'],
            'original_filename': original_filename,
            'original_size':     len(file_data),
            'timestamp':         time.time(),
            'owner_id':          current_user['id'],   # stored in blockchain too
            'encryption':        'AES-256-GCM',
        }
        if not verifier.register_file_metadata(blockchain_metadata):
            return jsonify({'error': 'Blockchain registration failed'}), 500

        # ── Record ownership in MySQL ────────────────────────
        register_file_owner(
            file_id           = file_id,
            owner_id          = current_user['id'],
            original_filename = original_filename,
            file_hash         = file_hash,
            fragment_count    = metadata.get('fragment_count', 3),
            file_size         = len(file_data),
        )

        verification = verifier.verify_file_registration(file_id, file_hash)

        write_audit(
            "UPLOAD",
            user_id  = current_user['id'],
            file_id  = file_id,
            details  = f"Uploaded {original_filename} ({len(file_data)} bytes)",
            ip       = request.remote_addr,
        )

        return jsonify({
            'success':           True,
            'message':           'File encrypted and secured',
            'file_id':           file_id,
            'file_hash':         file_hash,
            'original_filename': original_filename,
            'original_size':     len(file_data),
            'fragment_count':    metadata.get('fragment_count', 0),
            'encryption':        'AES-256-GCM',
            'timestamp':         metadata['timestamp'],
            'verification':      verification,
            'owner':             current_user['email'],
        })

    except Exception as e:
        import traceback; traceback.print_exc()
        return jsonify({'error': str(e)}), 500


@upload_bp.route('/verify/<file_id>', methods=['GET'])
def verify_upload(file_id):
    file_hash  = request.args.get('hash')
    if not file_hash:
        return jsonify({'error': 'Hash required'}), 400
    is_valid = verifier.verify_file_registration(file_id, file_hash)
    return jsonify({'file_id': file_id, 'verified': is_valid, 'timestamp': time.time()})