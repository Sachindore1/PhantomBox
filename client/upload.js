// client/upload.js  — JWT-aware version
// All API calls include Authorization: Bearer <token>

class FileUploader {
    constructor() {
        this.phantomboxUrl = `http://${window.location.hostname}:8000/api`;
        this.maxFileSize   = 10 * 1024 * 1024;
    }

    _headers() {
        // Include JWT from localStorage (set by auth-guard)
        const token = localStorage.getItem('pb_token');
        return token ? { 'Authorization': `Bearer ${token}` } : {};
    }

    async uploadFile(file) {
        const formData = new FormData();
        formData.append('file', file);

        try {
            this.showProgress('🔐 Converting to hologram noise...', 25);
            this.log(`📤 Uploading: ${file.name} (${this.formatFileSize(file.size)})`);

            const response = await fetch(`${this.phantomboxUrl}/upload`, {
                method:  'POST',
                headers: this._headers(),   // JWT here
                body:    formData
            });

            if (response.status === 401) {
                this.showResult('error', '<h4 style="color:var(--danger)">⛔ Session expired. Please <a href="auth.html" style="color:var(--primary)">sign in</a> again.</h4>');
                return;
            }

            if (!response.ok) {
                const err = await response.json();
                throw new Error(err.error || `Upload failed: ${response.statusText}`);
            }

            const result = await response.json();

            if (result.success) {
                this.showProgress('📦 Distributing fragments...', 60);

                ['step-hash','step-sharding'].forEach(id => {
                    document.getElementById(id)?.classList.add('completed');
                    document.getElementById(id)?.classList.remove('active');
                });
                document.getElementById('step-distribute')?.classList.add('active');
                await new Promise(r => setTimeout(r, 800));
                document.getElementById('step-distribute')?.classList.add('completed');
                document.getElementById('step-distribute')?.classList.remove('active');
                document.getElementById('step-blockchain')?.classList.add('active');
                await this.verifyOnBlockchain(result.file_id, result.file_hash);
                document.getElementById('step-blockchain')?.classList.add('completed');
                document.getElementById('step-blockchain')?.classList.remove('active');
                this.showProgress('✅ Upload complete!', 100);

                // Record in history
                const uploadRecord = {
                    id:         result.file_id,
                    name:       file.name,
                    file_name:  file.name,
                    hash:       result.file_hash,
                    file_hash:  result.file_hash,
                    size:       file.size,
                    timestamp:  new Date().toISOString(),
                    fragment_count: result.fragment_count || 3,
                    status:     'verified'
                };

                if (window.historyManager?.addUpload) {
                    window.historyManager.addUpload(uploadRecord);
                } else {
                    try {
                        const stored = JSON.parse(localStorage.getItem('phantombox_uploads') || '[]');
                        stored.unshift(uploadRecord);
                        localStorage.setItem('phantombox_uploads', JSON.stringify(stored.slice(0, 50)));
                    } catch(e) {}
                }

                this.showResult('success', `
                    <div style="text-align:left;">
                        <h4 style="color:var(--success);margin-bottom:1rem;">
                            <i class="fa-solid fa-circle-check"></i> File Secured!
                        </h4>
                        <p style="margin-bottom:.75rem;word-break:break-all;">
                            <strong>File ID:</strong>
                            <span style="font-family:var(--font-mono);background:rgba(0,0,0,.2);
                                         padding:.2rem .5rem;border-radius:4px;">${result.file_id}</span>
                        </p>
                        <p style="margin-bottom:.75rem;">
                            <strong>Owner:</strong> ${result.owner || 'You'}<br>
                            <strong>Size:</strong> ${this.formatFileSize(file.size)}<br>
                            <strong>Fragments:</strong> ${result.fragment_count || 3} (2-of-3)<br>
                            <strong>Encryption:</strong> AES-256-GCM
                        </p>
                        <div style="padding:.75rem;background:rgba(15,186,129,.1);border:1px solid var(--success);
                                    border-radius:8px;font-size:.82rem;color:var(--success);margin-bottom:1rem;">
                            <i class="fa-solid fa-lock"></i>
                            <strong>Only you</strong> can download this file.
                            Admins can access all files via the Audit Ledger.
                        </div>
                        <div style="display:flex;gap:1rem;">
                            <button onclick="window.historyManager?.copyFileId('${result.file_id}')"
                                    style="flex:1;padding:.75rem;background:var(--bg-dark);border:1px solid var(--primary);
                                           color:white;border-radius:8px;cursor:pointer;">
                                <i class="fa-regular fa-copy"></i> Copy ID
                            </button>
                            <button onclick="window.historyManager?.downloadFromHistory('${result.file_id}')"
                                    style="flex:1;padding:.75rem;background:var(--success);border:none;
                                           color:white;border-radius:8px;cursor:pointer;">
                                <i class="fa-solid fa-download"></i> Download Now
                            </button>
                        </div>
                    </div>
                `);

                this.log(`✅ Upload OK! File ID: ${result.file_id.substring(0,16)}...`);
                setTimeout(() => { if (typeof checkSystemStatus === 'function') checkSystemStatus(); }, 500);
            } else {
                throw new Error(result.error || 'Upload failed');
            }

        } catch (error) {
            console.error('Upload error:', error);
            this.showResult('error', `
                <h4 style="color:var(--danger);">
                    <i class="fa-solid fa-circle-exclamation"></i> Upload Failed
                </h4>
                <p>${error.message}</p>
            `);
            this.log(`❌ Upload failed: ${error.message}`);
            this.resetVisualizer();
        } finally {
            setTimeout(() => this.hideProgress(), 1000);
        }
    }

    async verifyOnBlockchain(fileId, fileHash) {
        try {
            const r = await fetch(
                `${this.phantomboxUrl}/verify/${fileId}?hash=${fileHash}`,
                { headers: this._headers(), signal: AbortSignal.timeout(5000) }
            );
            if (r.ok) {
                const d = await r.json();
                if (d.verified) { this.log(`✅ Blockchain verified`); return true; }
            }
            this.log(`⚠️ Blockchain verification warning`);
            return false;
        } catch(e) {
            return false;
        }
    }

    resetVisualizer() {
        ['step-hash','step-sharding','step-distribute','step-blockchain'].forEach(id => {
            const el = document.getElementById(id);
            if (el) el.classList.remove('active','completed');
        });
    }

    showProgress(text, percent) {
        const progress = document.getElementById('upload-progress');
        const fill     = document.getElementById('progress-fill');
        const label    = document.getElementById('progress-text');
        if (progress) progress.style.display = 'block';
        if (fill)     fill.style.width = `${percent}%`;
        if (label)    label.textContent = text;

        if (percent >= 25) document.getElementById('step-hash')?.classList.add('active');
        if (percent >= 50) {
            document.getElementById('step-hash')?.classList.replace('active','completed') ||
            document.getElementById('step-hash')?.classList.add('completed');
            document.getElementById('step-sharding')?.classList.add('active');
        }
        if (percent >= 75) {
            document.getElementById('step-sharding')?.classList.add('completed');
            document.getElementById('step-distribute')?.classList.add('active');
        }
        if (percent >= 90) {
            document.getElementById('step-distribute')?.classList.add('completed');
            document.getElementById('step-blockchain')?.classList.add('active');
        }
        if (percent >= 100) document.getElementById('step-blockchain')?.classList.add('completed');
    }

    hideProgress() {
        const p = document.getElementById('upload-progress');
        const f = document.getElementById('progress-fill');
        if (p) p.style.display = 'none';
        if (f) f.style.width = '0%';
    }

    showResult(type, message) {
        const r = document.getElementById('upload-result');
        if (!r) return;
        r.className = `upload-result ${type}`;
        r.innerHTML = message;
        r.style.display = 'block';
        if (type === 'success') setTimeout(() => { r.style.display = 'none'; }, 30000);
    }

    formatFileSize(bytes) {
        if (!bytes) return '0 Bytes';
        const k = 1024, sizes = ['Bytes','KB','MB','GB'];
        const i = Math.floor(Math.log(bytes) / Math.log(k));
        return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
    }

    log(msg) {
        const el = document.getElementById('global-log');
        if (!el) return;
        const line = document.createElement('div');
        line.className = 'log-line';
        line.innerHTML = `<span class="ts">[UPLOAD]</span> ${msg}`;
        el.prepend(line);
        if (el.children.length > 20) el.lastChild.remove();
    }
}

// ── Setup ────────────────────────────────────────────────────
const uploader = new FileUploader();
const dropZone  = document.getElementById('drop-zone');
const fileInput = document.getElementById('file-input');
let selectedFile = null;

if (dropZone) {
    dropZone.addEventListener('click', () => fileInput?.click());
    dropZone.addEventListener('dragover', e => { e.preventDefault(); dropZone.classList.add('dragover'); });
    dropZone.addEventListener('dragleave', () => dropZone.classList.remove('dragover'));
    dropZone.addEventListener('drop', e => {
        e.preventDefault(); dropZone.classList.remove('dragover');
        if (e.dataTransfer.files.length) handleFileSelect({ target: { files: e.dataTransfer.files } });
    });
}
if (fileInput) fileInput.addEventListener('change', handleFileSelect);

function handleFileSelect(e) {
    const file = e.target.files[0];
    if (!file) return;
    if (file.size > uploader.maxFileSize) { alert(`File too large. Max 10 MB.`); return; }
    selectedFile = file;
    document.getElementById('file-preview')?.classList.remove('hidden');
    document.getElementById('drop-zone')?.classList.add('hidden');
    const n = document.getElementById('preview-name');
    const s = document.getElementById('preview-size');
    if (n) n.textContent = file.name;
    if (s) s.textContent = uploader.formatFileSize(file.size);
    const btn = document.getElementById('btn-encrypt');
    if (btn) btn.disabled = false;
    uploader.log(`📁 Selected: ${file.name} (${uploader.formatFileSize(file.size)})`);
}

window.resetUpload = function() {
    selectedFile = null;
    if (fileInput) fileInput.value = '';
    document.getElementById('file-preview')?.classList.add('hidden');
    document.getElementById('drop-zone')?.classList.remove('hidden');
    const btn = document.getElementById('btn-encrypt');
    if (btn) btn.disabled = true;
    const r = document.getElementById('upload-result');
    if (r) r.style.display = 'none';
    uploader.resetVisualizer();
};

document.addEventListener('DOMContentLoaded', () => {
    const btn = document.getElementById('btn-encrypt');
    if (btn) {
        btn.addEventListener('click', async e => {
            e.preventDefault();
            if (!selectedFile) { alert('Please select a file first'); return; }
            btn.disabled = true;
            btn.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> Processing...';
            try { await uploader.uploadFile(selectedFile); }
            finally {
                btn.disabled = false;
                btn.innerHTML = '<i class="fa-solid fa-lock"></i> Encrypt & Disperse';
            }
        });
    }
    uploader.log('📋 Upload system initialized (JWT-auth mode)');
});