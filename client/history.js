// client/history.js — Server-backed, user-scoped version
// Uploads are fetched from MySQL (only shows YOUR files)
// Downloads come from audit log (only YOUR download events)
console.log('📁 Loading history.js (server-backed)…');

class FileHistory {
    constructor() {
        this.STORAGE_KEY_UPLOADS   = 'phantombox_uploads';
        this.STORAGE_KEY_DOWNLOADS = 'phantombox_downloads';
        this.uploads   = [];
        this.downloads = [];
        this.maxItems  = 50;
        this._loaded   = false;
    }

    // ── API helper ───────────────────────────────────────────
    _token() { return localStorage.getItem('pb_token'); }
    _headers() {
        const t = this._token();
        return t ? { 'Authorization': `Bearer ${t}` } : {};
    }
    _apiBase() { return `http://${window.location.hostname}:8000/api`; }

    // ── Load from server ─────────────────────────────────────
    async loadFromServer() {
        try {
            // Upload history (from MySQL file_registry, filtered by owner)
            const upRes = await fetch(`${this._apiBase()}/history/uploads?limit=50`, {
                headers: this._headers()
            });
            if (upRes.ok) {
                const data = await upRes.json();
                if (data.success) {
                    this.uploads = (data.files || []).map(f => ({
                        id:        f.file_id,
                        fileName:  f.original_filename || 'unknown',
                        fileHash:  f.file_hash,
                        size:      f.file_size || 0,
                        timestamp: f.upload_time || new Date().toISOString(),
                        status:    'verified',
                        fromServer: true,
                    }));
                    // Also cache locally as fallback
                    this._saveLocal();
                }
            }

            // Download history (from audit_ledger)
            const dlRes = await fetch(`${this._apiBase()}/history/downloads?limit=50`, {
                headers: this._headers()
            });
            if (dlRes.ok) {
                const data = await dlRes.json();
                if (data.success) {
                    this.downloads = (data.downloads || []).map(d => ({
                        id:        d.file_id || 'unknown',
                        fileName:  d.original_filename || d.details || 'unknown',
                        size:      0,
                        timestamp: d.timestamp || new Date().toISOString(),
                        status:    'verified',
                        fromServer: true,
                    }));
                }
            }

            this._loaded = true;
            this.updateUploadHistoryUI();
            this.updateDownloadHistoryUI();

        } catch(e) {
            console.warn('Server history unavailable, using local cache:', e);
            this._loadLocal();
            this.updateUploadHistoryUI();
            this.updateDownloadHistoryUI();
        }
    }

    // ── Local cache (fallback) ───────────────────────────────
    _loadLocal() {
        try {
            const u = localStorage.getItem(this.STORAGE_KEY_UPLOADS);
            const d = localStorage.getItem(this.STORAGE_KEY_DOWNLOADS);
            if (u) this.uploads   = JSON.parse(u);
            if (d) this.downloads = JSON.parse(d);
        } catch(e) {}
    }

    _saveLocal() {
        try {
            localStorage.setItem(this.STORAGE_KEY_UPLOADS,   JSON.stringify(this.uploads.slice(0, this.maxItems)));
            localStorage.setItem(this.STORAGE_KEY_DOWNLOADS, JSON.stringify(this.downloads.slice(0, this.maxItems)));
        } catch(e) {}
    }

    // ── Add (optimistic local update before server confirms) ─
    addUpload(fileInfo) {
        const rec = {
            id:        fileInfo.id || fileInfo.file_id,
            fileName:  fileInfo.name || fileInfo.file_name || 'unknown',
            fileHash:  fileInfo.hash || fileInfo.file_hash,
            size:      fileInfo.size || fileInfo.original_size || 0,
            timestamp: new Date().toISOString(),
            status:    'verified',
        };
        // Add at front, remove duplicates
        this.uploads = [rec, ...this.uploads.filter(u => u.id !== rec.id)].slice(0, this.maxItems);
        this._saveLocal();
        this.updateUploadHistoryUI();
        return rec;
    }

    addDownload(downloadInfo) {
        const rec = {
            id:        downloadInfo.file_id || downloadInfo.id || 'unknown',
            fileName:  downloadInfo.original_filename || downloadInfo.fileName || 'unknown',
            size:      downloadInfo.file_size || downloadInfo.size || 0,
            timestamp: new Date().toISOString(),
            status:    downloadInfo.hash_match ? 'verified' : 'warning',
        };
        this.downloads = [rec, ...this.downloads].slice(0, this.maxItems);
        this._saveLocal();
        this.updateDownloadHistoryUI();
        return rec;
    }

    // ── UI renderers ─────────────────────────────────────────
    updateUploadHistoryUI() {
        // Sidebar quick list (upload page)
        const uploadList = document.getElementById('upload-history-list');
        if (uploadList) {
            if (!this.uploads.length) {
                uploadList.innerHTML = '<div class="empty-history"><i class="fa-solid fa-cloud-arrow-up"></i><p>No uploads yet</p></div>';
            } else {
                uploadList.innerHTML = this.uploads.slice(0, 5).map(f => `
                    <div class="file-preview" style="margin-top:.5rem;cursor:pointer" onclick="window.historyManager.copyFileId('${f.id}')">
                        <i class="fa-solid fa-file-circle-check" style="color:var(--success)"></i>
                        <div style="flex:1;overflow:hidden">
                            <div style="font-weight:600;white-space:nowrap;overflow:hidden;text-overflow:ellipsis">${f.fileName}</div>
                            <div style="display:flex;gap:.75rem;font-size:.75rem;color:var(--text-muted)">
                                <span>${this.formatFileSize(f.size)}</span>
                                <span>${new Date(f.timestamp).toLocaleDateString()}</span>
                                <span class="file-id-cell">${f.id.substring(0,12)}…</span>
                            </div>
                        </div>
                        <button class="copy-btn" onclick="event.stopPropagation();window.historyManager.copyFileId('${f.id}')">
                            <i class="fa-regular fa-copy"></i> Copy ID
                        </button>
                    </div>`).join('');
            }
        }

        // Count badges
        document.querySelectorAll('#upload-count,#total-upload-count').forEach(el => {
            if (el) el.textContent = `${this.uploads.length} file${this.uploads.length !== 1 ? 's' : ''}`;
        });

        // Full history table
        const tbody = document.getElementById('upload-history-body');
        if (!tbody) return;
        if (!this.uploads.length) {
            tbody.innerHTML = '<tr><td colspan="6"><div class="empty-history"><i class="fa-solid fa-cloud-arrow-up"></i><p>No upload history</p></div></td></tr>';
            return;
        }
        tbody.innerHTML = this.uploads.map(f => `
            <tr>
                <td style="max-width:200px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap">
                    <i class="fa-solid fa-file" style="color:var(--primary);margin-right:.5rem"></i>${f.fileName}
                </td>
                <td class="file-id-cell">${f.id.substring(0,16)}…</td>
                <td>${this.formatFileSize(f.size)}</td>
                <td>${new Date(f.timestamp).toLocaleDateString()}<br>
                    <small style="color:var(--text-muted)">${new Date(f.timestamp).toLocaleTimeString()}</small></td>
                <td><span class="status-badge status-verified"><i class="fa-solid fa-check-circle"></i> Verified</span></td>
                <td>
                    <button class="preview-btn" onclick="window.historyManager.previewFromHistory('${f.id}')"
                        style="display:inline-block;margin-right:.4rem;padding:.35rem .75rem;background:var(--primary);border:none;color:white;border-radius:6px;cursor:pointer">
                        <i class="fa-solid fa-eye"></i> Preview
                    </button>
                    <button class="download-btn" onclick="window.historyManager.downloadFromHistory('${f.id}')"
                        style="display:inline-block;margin-right:.4rem;padding:.35rem .75rem;background:var(--success);border:none;color:white;border-radius:6px;cursor:pointer">
                        <i class="fa-solid fa-download"></i> Download
                    </button>
                    <button onclick="window.historyManager.openShareDialog('${f.id}')"
                        style="display:inline-block;padding:.35rem .75rem;background:rgba(245,158,11,.15);border:1px solid var(--warning);color:var(--warning);border-radius:6px;cursor:pointer;font-size:.75rem">
                        <i class="fa-solid fa-share-nodes"></i> Share
                    </button>
                </td>
            </tr>`).join('');
    }

    updateDownloadHistoryUI() {
        // Sidebar quick list
        const dlList = document.getElementById('download-history-list');
        if (dlList) {
            if (!this.downloads.length) {
                dlList.innerHTML = '<div class="empty-history"><i class="fa-solid fa-file-arrow-down"></i><p>No downloads yet</p></div>';
            } else {
                dlList.innerHTML = this.downloads.slice(0, 5).map(f => `
                    <div class="file-preview" style="margin-top:.5rem">
                        <i class="fa-solid fa-circle-check" style="color:var(--success)"></i>
                        <div style="flex:1;overflow:hidden">
                            <div style="font-weight:600;white-space:nowrap;overflow:hidden;text-overflow:ellipsis">${f.fileName}</div>
                            <div style="display:flex;gap:.75rem;font-size:.75rem;color:var(--text-muted)">
                                <span>${this.formatFileSize(f.size)}</span>
                                <span>${new Date(f.timestamp).toLocaleDateString()}</span>
                            </div>
                        </div>
                    </div>`).join('');
            }
        }

        document.querySelectorAll('#download-count,#total-download-count').forEach(el => {
            if (el) el.textContent = `${this.downloads.length} file${this.downloads.length !== 1 ? 's' : ''}`;
        });

        const tbody = document.getElementById('download-history-body');
        if (!tbody) return;
        if (!this.downloads.length) {
            tbody.innerHTML = '<tr><td colspan="6"><div class="empty-history"><i class="fa-solid fa-file-arrow-down"></i><p>No download history</p></div></td></tr>';
            return;
        }
        tbody.innerHTML = this.downloads.map(f => `
            <tr>
                <td style="max-width:200px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap">
                    <i class="fa-solid fa-file" style="color:var(--success);margin-right:.5rem"></i>${f.fileName}
                </td>
                <td class="file-id-cell">${(f.id||'').substring(0,16)}…</td>
                <td>${this.formatFileSize(f.size)}</td>
                <td>${new Date(f.timestamp).toLocaleDateString()}<br>
                    <small style="color:var(--text-muted)">${new Date(f.timestamp).toLocaleTimeString()}</small></td>
                <td><span class="status-badge status-verified"><i class="fa-solid fa-check-circle"></i> Verified</span></td>
                <td>
                    <button class="download-btn" onclick="window.historyManager.downloadFromHistory('${f.id}')"
                        style="display:inline-block;padding:.35rem .75rem;background:var(--success);border:none;color:white;border-radius:6px;cursor:pointer">
                        <i class="fa-solid fa-download"></i> Again
                    </button>
                </td>
            </tr>`).join('');
    }

    // ── Share dialog ─────────────────────────────────────────
    openShareDialog(fileId) {
        const existing = document.getElementById('share-modal');
        if (existing) existing.remove();

        const modal = document.createElement('div');
        modal.id = 'share-modal';
        modal.style.cssText = 'position:fixed;inset:0;background:rgba(0,0,0,.85);display:flex;align-items:center;justify-content:center;z-index:9999;';
        modal.innerHTML = `
            <div style="background:#101828;border:1px solid rgba(255,255,255,.1);border-radius:16px;padding:2rem;width:460px;max-width:95vw">
                <h3 style="margin-bottom:.35rem;display:flex;align-items:center;gap:.6rem">
                    <span>👻</span> Create Phantom Share Link
                </h3>
                <p style="font-size:.82rem;color:#64748b;margin-bottom:1.5rem">
                    Generate a self-destruct link. It vanishes after use or expiry.
                </p>
                <div style="display:grid;grid-template-columns:1fr 1fr;gap:.75rem;margin-bottom:.75rem">
                    <div>
                        <label style="display:block;font-size:.7rem;font-family:monospace;text-transform:uppercase;letter-spacing:1px;color:#64748b;margin-bottom:.3rem">Expires In</label>
                        <select id="sm-expires" style="width:100%;padding:.6rem;background:#0c1120;border:1px solid rgba(255,255,255,.1);border-radius:8px;color:white;font-size:.82rem">
                            <option value="1">1 hour</option>
                            <option value="6">6 hours</option>
                            <option value="24" selected>24 hours</option>
                            <option value="72">3 days</option>
                            <option value="168">7 days</option>
                        </select>
                    </div>
                    <div>
                        <label style="display:block;font-size:.7rem;font-family:monospace;text-transform:uppercase;letter-spacing:1px;color:#64748b;margin-bottom:.3rem">Max Downloads</label>
                        <select id="sm-max" style="width:100%;padding:.6rem;background:#0c1120;border:1px solid rgba(255,255,255,.1);border-radius:8px;color:white;font-size:.82rem">
                            <option value="1" selected>1 (One-time)</option>
                            <option value="3">3</option>
                            <option value="5">5</option>
                            <option value="10">10</option>
                        </select>
                    </div>
                </div>
                <div style="margin-bottom:1.25rem">
                    <label style="display:block;font-size:.7rem;font-family:monospace;text-transform:uppercase;letter-spacing:1px;color:#64748b;margin-bottom:.3rem">Label (optional)</label>
                    <input id="sm-label" placeholder="e.g. Shared with client" style="width:100%;padding:.6rem .85rem;background:#0c1120;border:1px solid rgba(255,255,255,.1);border-radius:8px;color:white;font-size:.82rem;outline:none">
                </div>
                <div id="sm-result" style="display:none;margin-bottom:1rem"></div>
                <div style="display:flex;gap:.75rem">
                    <button id="sm-create" onclick="window.historyManager.doCreateShare('${fileId}')"
                        style="flex:1;padding:.8rem;background:linear-gradient(135deg,#3b82f6,#1d4ed8);border:none;border-radius:8px;color:white;font-weight:700;cursor:pointer;font-size:.9rem">
                        <i class="fa-solid fa-ghost"></i> Generate Link
                    </button>
                    <button onclick="document.getElementById('share-modal').remove()"
                        style="padding:.8rem 1.25rem;background:rgba(255,255,255,.06);border:1px solid rgba(255,255,255,.1);border-radius:8px;color:white;cursor:pointer">
                        Cancel
                    </button>
                </div>
            </div>`;
        document.body.appendChild(modal);
    }

    async doCreateShare(fileId) {
        const btn     = document.getElementById('sm-create');
        const expires = parseInt(document.getElementById('sm-expires').value);
        const maxDl   = parseInt(document.getElementById('sm-max').value);
        const label   = document.getElementById('sm-label')?.value.trim() || '';

        btn.disabled = true;
        btn.textContent = 'Creating…';

        try {
            const res  = await fetch(`${this._apiBase()}/share/create`, {
                method:  'POST',
                headers: { ...this._headers(), 'Content-Type': 'application/json' },
                body:    JSON.stringify({ file_id: fileId, expires_in_hours: expires, max_downloads: maxDl, label })
            });
            const data = await res.json();

            if (!data.success) {
                this.showToast(data.error || 'Failed to create share link', 'error');
                btn.disabled = false;
                btn.innerHTML = '<i class="fa-solid fa-ghost"></i> Generate Link';
                return;
            }

            const resultEl = document.getElementById('sm-result');
            resultEl.style.display = 'block';
            resultEl.innerHTML = `
                <div style="padding:1rem;background:rgba(16,185,129,.08);border:1px solid rgba(16,185,129,.2);border-radius:8px">
                    <div style="font-size:.72rem;color:#10b981;font-weight:700;margin-bottom:.5rem">
                        ✅ Link created! Expires in ${expires}h · ${maxDl} download${maxDl>1?'s':''}
                    </div>
                    <div style="font-family:monospace;font-size:.72rem;word-break:break-all;
                                padding:.5rem;background:rgba(0,0,0,.3);border-radius:4px;color:#93c5fd;margin-bottom:.5rem">
                        ${data.share_url}
                    </div>
                    <button onclick="navigator.clipboard.writeText('${data.share_url}').then(()=>window.historyManager.showToast('Copied!','success'))"
                        style="padding:.4rem .85rem;background:rgba(59,130,246,.15);border:1px solid rgba(59,130,246,.3);
                               border-radius:6px;color:#60a5fa;font-size:.75rem;cursor:pointer">
                        <i class="fa-solid fa-copy"></i> Copy Link
                    </button>
                </div>`;
            btn.disabled = false;
            btn.innerHTML = '<i class="fa-solid fa-check"></i> Done';

        } catch(e) {
            this.showToast('Connection error', 'error');
            btn.disabled = false;
            btn.innerHTML = '<i class="fa-solid fa-ghost"></i> Generate Link';
        }
    }

    // ── Utilities ────────────────────────────────────────────
    copyFileId(fileId) {
        if (!fileId) return;
        navigator.clipboard.writeText(fileId).then(() =>
            this.showToast(`✅ File ID copied: ${fileId.substring(0,12)}…`, 'success')
        ).catch(() => this.showToast('Failed to copy', 'error'));
    }

    previewFromHistory(fileId) {
        if (!fileId) return;
        if (typeof window.switchView === 'function') window.switchView('download');
        const inp = document.getElementById('file-id-input');
        if (inp) inp.value = fileId;
        if (typeof window.previewFile === 'function')
            setTimeout(() => window.previewFile(fileId), 150);
        this.showToast(`👁️ Previewing: ${fileId.substring(0,12)}…`, 'info');
    }

    downloadFromHistory(fileId) {
        if (!fileId) return;
        if (typeof window.switchView === 'function') window.switchView('download');
        const inp = document.getElementById('file-id-input');
        if (inp) inp.value = fileId;
        if (typeof window.requestDownload === 'function')
            setTimeout(() => window.requestDownload(), 150);
        this.showToast(`📥 Requesting: ${fileId.substring(0,12)}…`, 'info');
    }

    formatFileSize(bytes) {
        if (!bytes) return '0 B';
        const k = 1024, s = ['B','KB','MB','GB'];
        const i = Math.floor(Math.log(bytes)/Math.log(k));
        return parseFloat((bytes/Math.pow(k,i)).toFixed(2))+' '+s[i];
    }

    showToast(msg, type='success') {
        const c = document.getElementById('toast-container');
        if (!c) { console.log(`[${type}] ${msg}`); return; }
        const t   = document.createElement('div');
        t.className = 'toast';
        const icons = { success:'fa-circle-check', error:'fa-circle-exclamation', info:'fa-circle-info' };
        const colors= { success:'var(--success)', error:'var(--danger)', info:'var(--primary)' };
        t.innerHTML = `<i class="fa-solid ${icons[type]||icons.info}" style="color:${colors[type]||colors.info}"></i><span>${msg}</span>`;
        c.appendChild(t);
        setTimeout(() => { t.style.opacity='0'; setTimeout(()=>t.remove(),400); }, 3500);
    }

    clearAllHistory() {
        this.uploads   = [];
        this.downloads = [];
        this._saveLocal();
        this.updateUploadHistoryUI();
        this.updateDownloadHistoryUI();
        this.showToast('History cleared', 'info');
    }

    init() {
        // Try server-backed first; localStorage is fallback
        this._loadLocal();
        this.updateUploadHistoryUI();
        this.updateDownloadHistoryUI();
        // Then load from server (async, will update UI again)
        if (this._token()) this.loadFromServer();
    }
}

// ── Global setup ─────────────────────────────────────────────
const historyManager = new FileHistory();
window.historyManager = historyManager;

window.refreshHistory = () => {
    if (window.historyManager) {
        window.historyManager.loadFromServer();
        window.historyManager.showToast('🔄 History refreshed', 'info');
    }
};

window.clearAllHistory = () => {
    if (confirm('Clear local history cache? Server data is preserved.')) {
        window.historyManager?.clearAllHistory();
    }
};

document.addEventListener('DOMContentLoaded', () => {
    window.historyManager.init();
});

console.log('✅ history.js loaded (server-backed mode)');