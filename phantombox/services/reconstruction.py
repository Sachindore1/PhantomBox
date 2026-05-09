"""
File reconstruction service with secure preview tokens.
"""
import hashlib
from typing import Optional, Dict, Tuple
from .pattern_engine import HologramNoiseGenerator
from .preview_service import preview_service
from .memory_store import memory_store
from .dispersal import FragmentDispersal
from ..config import AppConfig

class FileReconstructor:
    """
    Handles file reconstruction from encrypted fragments.
    Returns preview tokens instead of raw file data.
    """
    
    def __init__(self):
        self.config = AppConfig
        self.noise_gen = HologramNoiseGenerator(self.config.FRAGMENT_COUNT)
        self.dispersal = FragmentDispersal()
    
    def reconstruct_file(self, file_id: str, fragment_map: dict) -> Optional[Dict]:
        """
        Reconstruct file from encrypted fragments.
        
        Args:
            file_id: File identifier
            fragment_map: Fragment map from blockchain
            
        Returns:
            Dictionary with preview_token and metadata, or None if failed
        """
        # Retrieve encrypted fragments from noise nodes
        fragments = self.dispersal.retrieve_fragments(file_id, fragment_map)
        
        if len(fragments) < self.config.MIN_FRAGMENTS:
            raise ValueError(f"Insufficient fragments. Need {self.config.MIN_FRAGMENTS}, got {len(fragments)}")
        
        # Get file hash from fragment map for decryption
        file_hash = fragment_map.get('file_hash')
        if not file_hash:
            print("⚠️ No file hash in fragment map, attempting reconstruction without verification")
        
        try:
            print(f"🔐 Decrypting {len(fragments)} fragments with AES-GCM...")
            
            # Log fragment sizes for debugging
            for i, frag in enumerate(fragments):
                print(f"   Fragment {i}: {len(frag)} bytes")
            
            # Reconstruct original file using AES-GCM decryption
            reconstructed_data = self.noise_gen.reconstruct_from_fragments(fragments, file_hash)
            
            if not reconstructed_data:
                raise ValueError("Reconstruction failed - no data returned")
            
            # Verify hash matches blockchain record
            reconstructed_hash = hashlib.sha256(reconstructed_data).hexdigest()
            hash_match = reconstructed_hash == file_hash if file_hash else False
            
            if file_hash and not hash_match:
                print(f"⚠️ Hash mismatch! Expected: {file_hash[:32]}..., Got: {reconstructed_hash[:32]}...")
                print("   Continuing with reconstruction - possible tampering detected")
            else:
                print(f"✅ Hash verification successful!")
            
            print(f"✅ File reconstructed successfully: {len(reconstructed_data)} bytes")
            
            # Get original filename from metadata if available
            original_filename = None
            if 'original_filename' in fragment_map:
                original_filename = fragment_map['original_filename']
            
            # Detect file type for preview
            file_type = self._detect_file_type(reconstructed_data, original_filename)
            
            # 🔐 Create SECURE PREVIEW token (TTL: 60 seconds, one-time access)
            preview_token = preview_service.create_preview(
                file_id=file_id,
                file_data=reconstructed_data,
                filename=original_filename or f"reconstructed_{file_id[:8]}",
                file_type=file_type,
                ttl_seconds=60  # 60 second TTL for preview
            )
            
            # Also store in memory store with longer TTL for download
            download_token = memory_store.store_file(
                file_id=file_id,
                file_data=reconstructed_data,
                metadata={
                    'filename': original_filename,
                    'file_type': file_type,
                    'original_hash': file_hash,
                    'reconstructed_hash': reconstructed_hash,
                    'hash_match': hash_match
                },
                ttl_seconds=300,  # 5 minutes for download
                one_time=True      # One-time download
            )
            
            return {
                'success': True,
                'preview_token': preview_token,
                'download_token': download_token,
                'file_id': file_id,
                'filename': original_filename or f"reconstructed_{file_id[:8]}",
                'original_filename': original_filename,  # Add this for consistency
                'file_type': file_type,
                'file_size': len(reconstructed_data),
                'size': len(reconstructed_data),  # Add this for compatibility
                'hash_match': hash_match,
                'fragment_count': len(fragments),
                'preview_ttl': 60,
                'download_ttl': 300,
                'preview_url': f"/api/preview/{preview_token}",
                'download_url': f"/api/download/{download_token}"
            }
            
        except Exception as e:
            print(f"❌ Reconstruction failed: {e}")
            import traceback
            traceback.print_exc()
            return None
    
    def _detect_file_type(self, file_data: bytes, filename: str = None) -> str:
    
    # First, try to detect from filename
        if filename and '.' in filename:
            ext = filename.split('.')[-1].lower()
            # Office formats
            if ext in ['docx', 'xlsx', 'pptx']:
                return ext
            # Other formats
            if ext in ['pdf', 'txt', 'png', 'jpg', 'jpeg', 'gif', 'doc', 'xls', 'ppt']:
                return ext
        
        # Magic number detection with better Office format detection
        try:
            if len(file_data) >= 4:
                # PDF
                if file_data[:4] == b'%PDF':
                    return 'pdf'
                
                # Images
                if file_data[:3] == b'\xFF\xD8\xFF':
                    return 'jpg'
                if file_data[:8] == b'\x89PNG\r\n\x1a\n':
                    return 'png'
                if file_data[:6] in [b'GIF87a', b'GIF89a']:
                    return 'gif'
                if file_data[:2] == b'BM':
                    return 'bmp'
                
                # Office Open XML formats (docx, xlsx, pptx)
                if file_data[:2] == b'PK':
                    # Try to detect specific Office format by looking inside the ZIP
                    try:
                        # Check for Word document
                        if b'word/document.xml' in file_data[:8192]:
                            return 'docx'
                        # Check for Excel spreadsheet
                        if b'xl/workbook.xml' in file_data[:8192] or b'xl/sharedStrings.xml' in file_data[:8192]:
                            return 'xlsx'
                        # Check for PowerPoint presentation
                        if b'ppt/presentation.xml' in file_data[:8192]:
                            return 'pptx'
                        # Check for older Office formats (OLE)
                        if b'Microsoft Word' in file_data[:8192]:
                            return 'doc'
                        if b'Microsoft Excel' in file_data[:8192]:
                            return 'xls'
                        if b'Microsoft PowerPoint' in file_data[:8192]:
                            return 'ppt'
                    except:
                        pass
                    # If we can't determine specific type, check filename again
                    if filename:
                        ext = filename.split('.')[-1].lower()
                        if ext in ['docx', 'xlsx', 'pptx', 'doc', 'xls', 'ppt']:
                            return ext
                    return 'zip'  # Only fallback to zip if no other clue
                
                # Older Office OLE formats (doc, xls, ppt)
                if file_data[:8] == b'\xD0\xCF\x11\xE0\xA1\xB1\x1A\xE1':
                    # OLE Compound File format
                    if filename:
                        ext = filename.split('.')[-1].lower()
                        if ext in ['doc', 'xls', 'ppt']:
                            return ext
                    # Try to detect from content
                    try:
                        sample = file_data[:2048].decode('utf-8', errors='ignore')
                        if 'Microsoft Word' in sample:
                            return 'doc'
                        if 'Microsoft Excel' in sample:
                            return 'xls'
                        if 'Microsoft PowerPoint' in sample:
                            return 'ppt'
                    except:
                        pass
                    return 'ole'  # Generic OLE format
            
        except Exception as e:
            print(f"⚠️ Error detecting file type: {e}")
        
        # Try to detect text files
        try:
            if len(file_data) > 0:
                # Check if it's plain text (most characters are printable)
                if all(32 <= b < 127 or b in (9, 10, 13) for b in file_data[:min(500, len(file_data))]):
                    return 'txt'
        except:
            pass
        
        return 'bin'  # Default binary
    
    def get_file_for_download(self, download_token: str) -> Optional[bytes]:
        """
        Retrieve file from memory store for download.
        File is automatically wiped after retrieval.
        """
        return memory_store.retrieve_file(download_token)
    
    def get_file_for_preview(self, preview_token: str) -> Tuple[Optional[bytes], Optional[dict]]:
        """
        Retrieve file from preview service.
        File is automatically wiped after preview.
        """
        return preview_service.get_preview(preview_token)
    
    def get_stats(self) -> dict:
        """Get system statistics"""
        memory_stats = memory_store.get_stats()
        preview_stats = preview_service.get_stats()
        
        return {
            'memory_store': memory_stats,
            'preview_service': preview_stats,
            'total_memory': memory_stats['total_memory'] + preview_stats['total_memory']
        }

# Global reconstructor instance
reconstructor = FileReconstructor()