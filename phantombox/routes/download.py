"""
phantombox/routes/download.py  — RBAC-aware version
Requires JWT. Checks file ownership before reconstruction.
Admin can download any file. User only their own.
"""

from flask import Blueprint, request, jsonify, send_file, make_response, g
import io, time, requests as http_req
from ..services.reconstruction import reconstructor
from ..services.preview_service import preview_service
from ..services.memory_store    import memory_store
from ..config                   import AppConfig
from ..auth.middleware          import jwt_required
from ..auth.mysql_service       import can_access_file, get_file_owner
from ..auth.db                  import write_audit

download_bp = Blueprint('download', __name__)


# ── Request download (ownership-gated) ───────────────────────

@download_bp.route('/request_download/<file_id>', methods=['GET'])
@jwt_required
def request_download(file_id):
    """
    Reconstruct file from fragments.
    • Admin  → any file
    • User   → only files they uploaded
    """
    user = g.current_user

    # ── Ownership check ──────────────────────────────────────
    allowed, reason = can_access_file(file_id, user["id"], user["role"])
    if not allowed:
        write_audit("DOWNLOAD_DENIED", user_id=user["id"], file_id=file_id,
                    details=reason, ip=request.remote_addr)
        return jsonify({"error": reason, "code": "FORBIDDEN"}), 403

    try:
        # Get fragment map from blockchain
        res = http_req.get(f"{AppConfig.GENESIS_NODE}/fragments/{file_id}", timeout=10)
        if res.status_code != 200:
            return jsonify({'error': 'File not found on blockchain'}), 404

        fragment_map = res.json().get('fragment_map', {})
        if not fragment_map:
            return jsonify({'error': 'No fragment map available'}), 404

        # Get original filename from blockchain
        try:
            chain_res = http_req.get(f"{AppConfig.GENESIS_NODE}/chain", timeout=5)
            if chain_res.status_code == 200:
                for block in reversed(chain_res.json().get('chain', [])):
                    bd = block.get('data', {})
                    if bd.get('type') == 'file_registration' and bd.get('file_id') == file_id:
                        fragment_map['original_filename'] = bd.get('original_filename')
                        break
        except Exception:
            pass

        # Fallback filename from MySQL
        if not fragment_map.get('original_filename'):
            row = get_file_owner(file_id)
            if row:
                fragment_map['original_filename'] = row.get('original_filename')

        # Reconstruct in RAM
        result = reconstructor.reconstruct_file(file_id, fragment_map)
        if not result:
            return jsonify({'error': 'File reconstruction failed'}), 500

        write_audit("DOWNLOAD", user_id=user["id"], file_id=file_id,
                    details=f"Downloaded {result.get('filename')} by {user['email']}",
                    ip=request.remote_addr)

        return jsonify({
            'success':           True,
            'message':           'File reconstructed in memory',
            'preview_token':     result['preview_token'],
            'download_token':    result['download_token'],
            'file_id':           result['file_id'],
            'filename':          result['filename'],
            'original_filename': result.get('original_filename', result['filename']),
            'file_type':         result['file_type'],
            'file_size':         result['file_size'],
            'hash_match':        result['hash_match'],
            'fragment_count':    result['fragment_count'],
            'preview_ttl':       result['preview_ttl'],
            'download_ttl':      result['download_ttl'],
            'preview_url':       f"/api/preview/{result['preview_token']}",
            'download_url':      f"/api/download/{result['download_token']}",
        })

    except Exception as e:
        import traceback; traceback.print_exc()
        return jsonify({'error': f'Download request failed: {str(e)}'}), 500


# ── Preview (one-time, no auth needed — token is the secret) ─

@download_bp.route('/preview/<preview_token>', methods=['GET'])
def preview_file(preview_token):
    file_data, metadata = reconstructor.get_file_for_preview(preview_token)
    if not file_data:
        return jsonify({'error': 'Preview not available or expired'}), 404

    filename  = metadata.get('filename', 'preview.bin')
    file_type = metadata.get('file_type', 'bin')
    mime_type = _mime(file_type, filename)

    resp = make_response(send_file(
        io.BytesIO(file_data),
        as_attachment=False,
        download_name=filename,
        mimetype=mime_type,
    ))
    resp.headers['Cache-Control']             = 'no-store'
    resp.headers['X-Frame-Options']           = 'ALLOWALL'
    resp.headers['Content-Security-Policy']   = "frame-ancestors *;"
    resp.headers['Access-Control-Allow-Origin'] = '*'
    return resp


# ── Download (one-time, token is the secret) ─────────────────

@download_bp.route('/download/<download_token>', methods=['GET'])
def download_file(download_token):
    file_data = reconstructor.get_file_for_download(download_token)
    if not file_data:
        return jsonify({'error': 'Download not available or expired'}), 404

    # Try to get original filename from metadata
    # You'll need to store it in the memory store
    from ..services.memory_store import memory_store
    
    # Get the entry to retrieve original filename
    original_filename = None
    with memory_store.lock:
        for entry in memory_store.store.values():
            if entry.store_key == download_token:
                original_filename = entry.metadata.get('filename')
                break
    
    file_type = _detect(file_data)
    
    # Use original filename if available, otherwise generate one
    if original_filename and '.' in original_filename:
        ext = original_filename.split('.')[-1].lower()
        # Only use original extension if it's appropriate
        if ext in ['docx', 'xlsx', 'pptx', 'doc', 'xls', 'ppt', 'pdf', 'txt', 'png', 'jpg', 'jpeg']:
            filename = original_filename
        else:
            ext = _ext(file_type)
            filename = original_filename.rsplit('.', 1)[0] + ext if '.' in original_filename else f"{original_filename}{ext}"
    else:
        ext = _ext(file_type)
        filename = f"reconstructed_{int(time.time())}{ext}"
    
    mime_type = _mime(file_type, filename)
    
    resp = make_response(send_file(
        io.BytesIO(file_data),
        as_attachment=True,
        download_name=filename,
        mimetype=mime_type,
    ))
    resp.headers['Cache-Control'] = 'no-store'
    resp.headers['Access-Control-Allow-Origin'] = '*'
    return resp


# ── Memory stats ─────────────────────────────────────────────

@download_bp.route('/memory_stats', methods=['GET'])
def memory_stats():
    return jsonify(reconstructor.get_stats())


# ── Revoke token ─────────────────────────────────────────────

@download_bp.route('/revoke/<token>', methods=['DELETE'])
def revoke_token(token):
    if preview_service.revoke_preview(token):
        return jsonify({'success': True, 'message': 'Preview token revoked'})
    if memory_store.secure_wipe(token):
        return jsonify({'success': True, 'message': 'Download token revoked'})
    return jsonify({'error': 'Token not found'}), 404


# ── Helpers ───────────────────────────────────────────────────

def _detect(d):
    if d[:4] == b'%PDF': return 'pdf'
    if d[:3] == b'\xFF\xD8\xFF': return 'jpg'
    if d[:8] == b'\x89PNG\r\n\x1a\n': return 'png'
    if d[:2] == b'PK': return 'zip'
    try:
        if all(32 <= b < 127 or b in (9,10,13) for b in d[:200]):
            return 'txt'
    except Exception:
        pass
    return 'bin'

def _ext(t):
    return {
        'pdf':'.pdf','docx':'.docx','xlsx':'.xlsx','pptx':'.pptx',
        'zip':'.zip','jpg':'.jpg','jpeg':'.jpeg','png':'.png',
        'gif':'.gif','txt':'.txt'
    }.get(t, '.bin')

def _mime(t, fn=None):
    # Office Open XML formats
    if fn:
        if fn.endswith('.docx'):
            return 'application/vnd.openxmlformats-officedocument.wordprocessingml.document'
        if fn.endswith('.xlsx'):
            return 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        if fn.endswith('.pptx'):
            return 'application/vnd.openxmlformats-officedocument.presentationml.presentation'
        # Older Office formats
        if fn.endswith('.doc'):
            return 'application/msword'
        if fn.endswith('.xls'):
            return 'application/vnd.ms-excel'
        if fn.endswith('.ppt'):
            return 'application/vnd.ms-powerpoint'
    
    # Based on file type
    mime_map = {
        'pdf': 'application/pdf',
        'docx': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
        'xlsx': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        'pptx': 'application/vnd.openxmlformats-officedocument.presentationml.presentation',
        'doc': 'application/msword',
        'xls': 'application/vnd.ms-excel',
        'ppt': 'application/vnd.ms-powerpoint',
        'zip': 'application/zip',
        'jpg': 'image/jpeg',
        'jpeg': 'image/jpeg',
        'png': 'image/png',
        'gif': 'image/gif',
        'txt': 'text/plain',
        'bin': 'application/octet-stream',
        'ole': 'application/octet-stream',
    }
    return mime_map.get(t, 'application/octet-stream')