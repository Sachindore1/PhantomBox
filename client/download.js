// client/download.js — Full preview support for all file types

class FileDownloader {
    constructor() {
        this.phantomboxUrl = `http://${window.location.hostname}:8000/api`;
        this._currentPreviewToken  = null;
        this._currentDownloadToken = null;
        this._currentFileId        = null;
        this._currentFilename      = null;
        this._currentFileType      = null;
        this._busy = false;
    }

    _headers() {
        const token = localStorage.getItem('pb_token');
        return token ? { 'Authorization': `Bearer ${token}` } : {};
    }

    reset() {
        this._currentPreviewToken  = null;
        this._currentDownloadToken = null;
        this._currentFileId        = null;
        this._currentFilename      = null;
        this._currentFileType      = null;
        this._busy = false;
        this._hideProgress();
        this._resetSteps();
        this._hideDownloadCard();
        this._clearResult();
    }

    async requestDownload(fileId) {
        if (!fileId || !fileId.trim()) {
            this._showToast('Please enter a File ID', 'error');
            return;
        }
        if (this._busy) {
            this._showToast('Already processing, please wait…', 'warning');
            return;
        }

        this.reset();
        this._currentFileId = fileId.trim();
        this._busy = true;

        this._showProgress('🔍 Verifying on blockchain…', 10);
        this._setStep('step-verify', 'active');

        try {
            const res = await fetch(
                `${this.phantomboxUrl}/request_download/${encodeURIComponent(this._currentFileId)}`,
                { headers: this._headers() }
            );

            if (res.status === 401) {
                this._showResult('error', '⛔ Session expired. Please <a href="auth.html">sign in</a> again.');
                return;
            }
            if (res.status === 403) {
                const err = await res.json();
                this._showResult('error', `🚫 ${err.error || 'Access denied. You do not own this file.'}`);
                return;
            }
            if (!res.ok) {
                const err = await res.json();
                throw new Error(err.error || `Request failed: ${res.statusText}`);
            }

            const data = await res.json();
            if (!data.success) throw new Error(data.error || 'Download request failed');

            this._setStep('step-verify', 'completed');
            this._showProgress('📡 Fetching fragments…', 40);
            this._setStep('step-fetch', 'active');
            await this._delay(400);

            this._setStep('step-fetch', 'completed');
            this._showProgress('🔐 Reconstructing in RAM…', 75);
            this._setStep('step-combine', 'active');
            await this._delay(400);

            this._setStep('step-combine', 'completed');
            this._showProgress('✅ Ready!', 100);

            this._currentPreviewToken  = data.preview_token;
            this._currentDownloadToken = data.download_token;
            this._currentFilename      = data.original_filename || data.filename || 'file';
            this._currentFileType      = data.file_type || '';

            this._showDownloadCard(data);

            if (window.historyManager?.addDownload) {
                window.historyManager.addDownload({
                    file_id:           this._currentFileId,
                    original_filename: this._currentFilename,
                    file_size:         data.file_size || 0,
                    hash_match:        data.hash_match,
                });
            }

            this._log(`✅ Reconstructed: ${this._currentFilename} (${this._fmtSize(data.file_size)})`);

        } catch (err) {
            console.error('Download error:', err);
            this._setStep('step-verify', '');
            this._setStep('step-fetch',  '');
            this._setStep('step-combine','');
            this._showResult('error', `❌ ${err.message}`);
            this._log(`❌ Download failed: ${err.message}`);
        } finally {
            this._busy = false;
            setTimeout(() => this._hideProgress(), 1200);
        }
    }

    async previewFile(fileIdOverride) {
        const fileId = fileIdOverride
            || this._currentFileId
            || document.getElementById('file-id-input')?.value?.trim();

        if (!fileId) {
            this._showToast('Enter a File ID first', 'error');
            return;
        }

        if (!this._currentPreviewToken || this._currentFileId !== fileId) {
            await this.requestDownload(fileId);
            if (!this._currentPreviewToken) return;
        }

        const token    = this._currentPreviewToken;
        const filename = this._currentFilename;
        const fileType = this._currentFileType;

        // Consume immediately to prevent double-use
        this._currentPreviewToken = null;

        const previewUrl = `${this.phantomboxUrl}/preview/${token}`;
        this._openPreviewModal(previewUrl, filename, fileType);
        this._log(`👁️ Preview opened: ${filename}`);
    }

    async downloadFile() {
        const token = this._currentDownloadToken;
        if (!token) {
            this._showToast('No download token. Please reconstruct the file first.', 'error');
            return;
        }

        this._currentDownloadToken = null;
        this._hideDownloadCard();

        const btn = document.getElementById('btn-download-final');
        if (btn) {
            btn.disabled = true;
            btn.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> Downloading…';
        }

        try {
            const res = await fetch(`${this.phantomboxUrl}/download/${token}`, {
                headers: this._headers(),
            });

            if (!res.ok) throw new Error(`Download failed: ${res.statusText}`);

            const blob        = await res.blob();
            const contentDisp = res.headers.get('Content-Disposition') || '';
            const nameMatch   = contentDisp.match(/filename[^;=\n]*=['"]?([^'"\n]+)['"]?/);
            const filename    = nameMatch ? nameMatch[1] : this._currentFilename || 'download';

            const url = URL.createObjectURL(blob);
            const a   = document.createElement('a');
            a.href     = url;
            a.download = filename;
            document.body.appendChild(a);
            a.click();
            URL.revokeObjectURL(url);
            document.body.removeChild(a);

            this._showToast(`✅ Downloaded: ${filename}`, 'success');
            this._log(`📥 Downloaded: ${filename} (${this._fmtSize(blob.size)})`);
            this.reset();

        } catch (err) {
            console.error('Download file error:', err);
            this._showToast(`❌ ${err.message}`, 'error');
            if (btn) {
                btn.disabled = false;
                btn.innerHTML = '<i class="fa-solid fa-download"></i> Download to Device';
            }
        }
    }

    // ── Preview Modal ──────────────────────────────────────────

    _openPreviewModal(previewUrl, filename, fileType) {
        const existing = document.getElementById('preview-modal-overlay');
        if (existing) existing.remove();

        const ext = (filename || '').split('.').pop().toLowerCase();

        const overlay = document.createElement('div');
        overlay.id = 'preview-modal-overlay';
        overlay.style.cssText = `
            position:fixed;inset:0;background:rgba(0,0,0,.88);
            display:flex;flex-direction:column;align-items:center;
            justify-content:center;z-index:9999;padding:1rem;`;

        overlay.innerHTML = `
            <div style="width:100%;max-width:960px;background:#141b2b;border:1px solid #1e293b;
                        border-radius:16px;overflow:hidden;display:flex;flex-direction:column;
                        max-height:92vh;">

                <div style="display:flex;align-items:center;justify-content:space-between;
                            padding:.85rem 1.25rem;border-bottom:1px solid #1e293b;flex-shrink:0;
                            background:#0f1623;">
                    <div style="display:flex;align-items:center;gap:.75rem;font-weight:600;font-size:.9rem;">
                        <span style="font-size:1.1rem;">${this._fileIcon(ext)}</span>
                        <span style="color:#e2e8f0;max-width:400px;overflow:hidden;
                                     text-overflow:ellipsis;white-space:nowrap;">${filename || 'Preview'}</span>
                        <span style="font-size:.62rem;padding:.15rem .45rem;
                                     background:rgba(239,68,68,.15);color:#f87171;
                                     border-radius:5px;font-family:monospace;letter-spacing:.5px;
                                     flex-shrink:0;">ONE-TIME · 60s</span>
                    </div>
                    <div style="display:flex;align-items:center;gap:.75rem;">
                        <span style="font-size:.7rem;color:#475569;font-family:monospace;
                                     text-transform:uppercase;letter-spacing:.5px;">
                            ${this._typeLabel(ext)}
                        </span>
                        <span style="font-size:.75rem;color:#64748b;font-family:monospace;"
                              id="preview-ttl-counter">60s</span>
                        <button id="preview-close-btn"
                            style="background:rgba(255,255,255,.08);border:1px solid rgba(255,255,255,.1);
                                   color:#94a3b8;width:30px;height:30px;border-radius:7px;
                                   cursor:pointer;font-size:.95rem;display:flex;align-items:center;
                                   justify-content:center;">✕</button>
                    </div>
                </div>

                <div id="preview-content-area"
                     style="flex:1;overflow:auto;min-height:0;background:#0a0e1a;">
                    ${this._buildPreviewContent(previewUrl, filename, ext)}
                </div>

                <div style="padding:.55rem 1.25rem;border-top:1px solid #1e293b;font-size:.68rem;
                            color:#334155;font-family:monospace;flex-shrink:0;background:#0f1623;
                            display:flex;align-items:center;gap:1rem;">
                    <span>⚡ RAM-only preview · No disk write · Auto-wiped after view</span>
                    <a href="${previewUrl}" download="${filename}"
                       style="margin-left:auto;color:#2a7de1;text-decoration:none;font-size:.68rem;">
                        ⬇ Download instead
                    </a>
                </div>
            </div>`;

        document.body.appendChild(overlay);

        // Close handlers
        overlay.querySelector('#preview-close-btn').onclick = () => overlay.remove();
        overlay.addEventListener('click', e => { if (e.target === overlay) overlay.remove(); });

        // TTL countdown
        let ttl = 60;
        const counter = overlay.querySelector('#preview-ttl-counter');
        const ttlInterval = setInterval(() => {
            ttl--;
            if (counter) counter.textContent = `${ttl}s`;
            if (ttl <= 10 && counter) counter.style.color = '#ef4444';
            if (ttl <= 0) {
                clearInterval(ttlInterval);
                if (overlay.isConnected) overlay.remove();
            }
        }, 1000);

        // Load text content asynchronously
        const textExts = ['txt','log','md','csv','json','xml','html','htm',
                          'py','js','ts','css','sh','bat','ini','cfg','yaml','yml'];
        if (textExts.includes(ext)) {
            this._loadTextPreview(previewUrl, overlay);
        }
    }

    _buildPreviewContent(previewUrl, filename, ext) {
        // ── Images ────────────────────────────────────────────
        if (['png','jpg','jpeg','gif','bmp','webp','svg'].includes(ext)) {
            return `
                <div style="display:flex;align-items:center;justify-content:center;
                            padding:1.5rem;min-height:400px;">
                    <img src="${previewUrl}" alt="${filename}"
                         style="max-width:100%;max-height:68vh;border-radius:8px;object-fit:contain;"
                         onerror="this.parentElement.innerHTML='<p style=\\'padding:2rem;color:#ef4444;\\'>Image failed to load.</p>'"/>
                </div>`;
        }

        // ── PDF ───────────────────────────────────────────────
        if (ext === 'pdf') {
            return `
                <div style="position:relative;width:100%;height:70vh;">
                    <div id="pdf-spinner" style="position:absolute;inset:0;display:flex;
                         align-items:center;justify-content:center;flex-direction:column;gap:1rem;
                         background:#0a0e1a;z-index:1;">
                        <div style="font-size:2.5rem;">📕</div>
                        <div style="color:#64748b;font-size:.8rem;font-family:monospace;">
                            Loading PDF…
                        </div>
                        <div style="width:36px;height:36px;border:3px solid #1e293b;
                                    border-top-color:#2a7de1;border-radius:50%;
                                    animation:pbspin 1s linear infinite;"></div>
                        <style>@keyframes pbspin{to{transform:rotate(360deg)}}</style>
                    </div>
                    <iframe src="${previewUrl}#toolbar=1&navpanes=0&scrollbar=1"
                            style="width:100%;height:100%;border:none;display:block;
                                   position:relative;z-index:2;"
                            title="PDF Preview"
                            onload="var s=document.getElementById('pdf-spinner');if(s)s.style.display='none'">
                    </iframe>
                </div>`;
        }

        // ── Office Documents ───────────────────────────────────
        if (['docx','doc','pptx','ppt','xlsx','xls'].includes(ext)) {
            return this._officeViewerContent(previewUrl, filename, ext);
        }

        // ── Text / Code ───────────────────────────────────────
        const textExts = ['txt','log','md','csv','json','xml','html','htm',
                          'py','js','ts','css','sh','bat','ini','cfg','yaml','yml'];
        if (textExts.includes(ext)) {
            return `
                <div id="text-preview-container"
                     style="padding:1.5rem;font-family:monospace;font-size:.8rem;
                            color:#cbd5e1;line-height:1.65;min-height:400px;">
                    <div style="display:flex;align-items:center;gap:.75rem;color:#475569;">
                        <div style="width:16px;height:16px;border:2px solid #1e293b;
                                    border-top-color:#2a7de1;border-radius:50%;
                                    animation:pbspin 1s linear infinite;"></div>
                        <style>@keyframes pbspin{to{transform:rotate(360deg)}}</style>
                        Loading content…
                    </div>
                </div>`;
        }

        // ── Fallback ──────────────────────────────────────────
        return this._fallbackCard(previewUrl, filename,
            `Preview not available for .${ext || 'bin'} files`);
    }

    _officeViewerContent(previewUrl, filename, ext) {
        const icons = { docx:'📄', doc:'📄', pptx:'📊', ppt:'📊', xlsx:'📗', xls:'📗' };
        const names = {
            docx:'Word Document', doc:'Word Document (Legacy)',
            pptx:'PowerPoint Presentation', ppt:'PowerPoint (Legacy)',
            xlsx:'Excel Spreadsheet', xls:'Excel (Legacy)'
        };
        const icon = icons[ext] || '📎';
        const name = names[ext] || 'Office Document';

        const isLocal = ['localhost','127.0.0.1'].includes(window.location.hostname)
                     || /^192\.168\./.test(window.location.hostname)
                     || /^10\./.test(window.location.hostname);

        if (isLocal) {
            // Localhost: can't use external viewers — show a clear UI
            return `
                <div style="display:flex;flex-direction:column;align-items:center;
                            justify-content:center;min-height:420px;padding:2.5rem;text-align:center;">

                    <div style="font-size:4rem;margin-bottom:1rem;line-height:1;">${icon}</div>

                    <div style="font-size:1rem;font-weight:600;color:#e2e8f0;margin-bottom:.5rem;">
                        ${name}
                    </div>
                    <div style="font-size:.78rem;color:#94a3b8;margin-bottom:.5rem;">
                        ${filename}
                    </div>

                    <div style="margin:1.25rem 0;padding:1rem 1.5rem;background:rgba(245,158,11,.07);
                                border:1px solid rgba(245,158,11,.2);border-radius:10px;
                                max-width:480px;font-size:.78rem;color:#94a3b8;line-height:1.7;">
                        <strong style="color:#f59e0b;">ℹ Office doc previews</strong> use
                        Microsoft Office Online or Google Docs Viewer,
                        which require a <strong style="color:#e2e8f0;">public HTTPS URL</strong>.<br><br>
                        Running on <code style="color:#2a7de1;background:rgba(42,125,225,.1);
                        padding:.1rem .4rem;border-radius:4px;">localhost</code>
                        — download the file to view it locally.
                    </div>

                    <div style="display:flex;gap:.75rem;flex-wrap:wrap;justify-content:center;">
                        <a href="${previewUrl}" download="${filename}"
                           style="display:inline-flex;align-items:center;gap:.5rem;
                                  padding:.7rem 1.4rem;
                                  background:linear-gradient(135deg,#2a7de1,#1a5cb0);
                                  color:white;border-radius:10px;text-decoration:none;
                                  font-size:.85rem;font-weight:600;">
                            ⬇ Download ${filename}
                        </a>
                        <button onclick="window.open('${previewUrl}','_blank')"
                                style="display:inline-flex;align-items:center;gap:.5rem;
                                       padding:.7rem 1.4rem;
                                       background:rgba(255,255,255,.05);
                                       border:1px solid rgba(255,255,255,.12);
                                       color:#94a3b8;border-radius:10px;
                                       cursor:pointer;font-size:.85rem;">
                            ↗ Open raw in tab
                        </button>
                    </div>

                    <div style="margin-top:2rem;padding:.6rem 1rem;background:rgba(0,0,0,.2);
                                border-radius:6px;font-family:monospace;font-size:.65rem;color:#334155;">
                        Production deployment → MS Office Online viewer auto-enabled
                    </div>
                </div>`;
        }

        // Production: use Microsoft Office Online viewer
        const absoluteUrl = window.location.origin + '/api/preview/' + previewUrl.split('/preview/').pop();
        const viewerUrl   = `https://view.officeapps.live.com/op/embed.aspx?src=${encodeURIComponent(absoluteUrl)}`;

        return `
            <div style="position:relative;width:100%;height:70vh;">
                <div id="office-spinner"
                     style="position:absolute;inset:0;display:flex;align-items:center;
                            justify-content:center;flex-direction:column;gap:1rem;
                            background:#0a0e1a;z-index:1;">
                    <div style="font-size:2.5rem;">${icon}</div>
                    <div style="color:#64748b;font-size:.78rem;font-family:monospace;">
                        Loading ${name}…
                    </div>
                    <div style="width:36px;height:36px;border:3px solid #1e293b;
                                border-top-color:#2a7de1;border-radius:50%;
                                animation:pbspin 1s linear infinite;"></div>
                    <style>@keyframes pbspin{to{transform:rotate(360deg)}}</style>
                </div>

                <iframe src="${viewerUrl}"
                        style="width:100%;height:100%;border:none;display:block;
                               position:relative;z-index:2;"
                        title="${name} Preview"
                        onload="var s=document.getElementById('office-spinner');if(s)s.style.display='none'">
                </iframe>

                <div id="office-error"
                     style="display:none;position:absolute;inset:0;z-index:3;
                            align-items:center;justify-content:center;flex-direction:column;
                            gap:1rem;background:#0a0e1a;text-align:center;padding:2rem;">
                    <div style="font-size:2rem;">⚠️</div>
                    <div style="color:#94a3b8;font-size:.85rem;">Office viewer unavailable</div>
                    <a href="${previewUrl}" download="${filename}"
                       style="padding:.65rem 1.25rem;background:#2a7de1;color:white;
                              border-radius:8px;text-decoration:none;font-size:.85rem;">
                        ⬇ Download instead
                    </a>
                </div>
            </div>`;
    }

    _fallbackCard(previewUrl, filename, message) {
        const ext = (filename || '').split('.').pop().toLowerCase();
        return `
            <div style="display:flex;flex-direction:column;align-items:center;justify-content:center;
                        min-height:420px;padding:2.5rem;text-align:center;gap:1.25rem;">
                <div style="font-size:3.5rem;line-height:1;">${this._fileIcon(ext)}</div>
                <div style="font-size:.88rem;color:#64748b;">${message}</div>
                <div style="display:flex;gap:.75rem;justify-content:center;flex-wrap:wrap;">
                    <a href="${previewUrl}" download="${filename}"
                       style="display:inline-flex;align-items:center;gap:.5rem;padding:.65rem 1.25rem;
                              background:linear-gradient(135deg,#2a7de1,#1a5cb0);color:white;
                              border-radius:10px;text-decoration:none;font-size:.85rem;font-weight:600;">
                        ⬇ Download File
                    </a>
                    <button onclick="window.open('${previewUrl}','_blank')"
                            style="padding:.65rem 1.25rem;background:rgba(255,255,255,.06);
                                   border:1px solid rgba(255,255,255,.1);color:#94a3b8;
                                   border-radius:10px;cursor:pointer;font-size:.85rem;">
                        ↗ Open in tab
                    </button>
                </div>
            </div>`;
    }

    async _loadTextPreview(previewUrl, overlay) {
        try {
            const res = await fetch(previewUrl);
            if (!res.ok) throw new Error(`HTTP ${res.status}`);
            const rawText = await res.text();

            const container = overlay.querySelector('#text-preview-container');
            if (!container) return;

            const ext = previewUrl.split('?')[0].split('.').pop().toLowerCase();
            let display = rawText;

            // Pretty-print JSON
            if (ext === 'json') {
                try { display = JSON.stringify(JSON.parse(rawText), null, 2); } catch(e) {}
            }

            const MAX = 60000;
            const truncated = display.length > MAX;
            const shown = truncated ? display.slice(0, MAX) : display;
            const lines = rawText.split('\n').length;

            container.innerHTML = `
                <div style="display:flex;align-items:center;gap:1rem;margin-bottom:1rem;
                            padding-bottom:.75rem;border-bottom:1px solid #1e293b;
                            font-size:.7rem;font-family:monospace;color:#475569;">
                    <span>${rawText.length.toLocaleString()} chars</span>
                    <span>·</span>
                    <span>${lines.toLocaleString()} lines</span>
                    ${truncated ? '<span>·</span><span style="color:#f59e0b">⚠ truncated at 60 000 chars</span>' : ''}
                </div>
                <pre style="margin:0;color:#cbd5e1;font-size:.78rem;line-height:1.65;
                            white-space:pre-wrap;word-break:break-word;">${this._escapeHtml(shown)}</pre>`;
        } catch(e) {
            const container = overlay.querySelector('#text-preview-container');
            if (container) {
                container.innerHTML = `<div style="padding:2rem;color:#ef4444;font-size:.82rem;">
                    Failed to load text: ${e.message}</div>`;
            }
        }
    }

    _fileIcon(ext) {
        const m = {
            pdf:'📕', doc:'📄', docx:'📄', xls:'📗', xlsx:'📗',
            ppt:'📙', pptx:'📙', png:'🖼', jpg:'🖼', jpeg:'🖼',
            gif:'🖼', webp:'🖼', bmp:'🖼', svg:'🖼',
            txt:'📝', log:'📝', md:'📝', csv:'📊',
            json:'🔧', xml:'🔧', yaml:'🔧', yml:'🔧',
            py:'🐍', js:'📜', ts:'📜', css:'🎨',
            html:'🌐', htm:'🌐', sh:'⚙', bat:'⚙',
            zip:'📦', tar:'📦', gz:'📦',
        };
        return m[ext] || '📎';
    }

    _typeLabel(ext) {
        const m = {
            pdf:'PDF', doc:'Word', docx:'Word', xls:'Excel', xlsx:'Excel',
            ppt:'PowerPoint', pptx:'PowerPoint',
            png:'PNG Image', jpg:'JPEG Image', jpeg:'JPEG Image',
            gif:'GIF', webp:'WebP', svg:'SVG', bmp:'Bitmap',
            txt:'Plain Text', md:'Markdown', csv:'CSV', json:'JSON',
            xml:'XML', yaml:'YAML', yml:'YAML',
            py:'Python', js:'JavaScript', ts:'TypeScript',
            css:'CSS', html:'HTML', htm:'HTML',
        };
        return m[ext] || (ext ? ext.toUpperCase() : 'Binary');
    }

    _escapeHtml(str) {
        return str
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;')
            .replace(/"/g, '&quot;');
    }

    // ── UI Helpers ─────────────────────────────────────────────

    _showDownloadCard(data) {
        const card = document.getElementById('download-ready-card');
        if (!card) return;

        const fnEl   = document.getElementById('dl-filename');
        const sizeEl = document.getElementById('dl-size');
        if (fnEl)   fnEl.textContent   = data.original_filename || data.filename || 'file';
        if (sizeEl) sizeEl.textContent = this._fmtSize(data.file_size);

        card.classList.remove('hidden');

        const btn = document.getElementById('btn-download-final');
        if (btn) {
            btn.disabled = false;
            btn.innerHTML = '<i class="fa-solid fa-download"></i> Download to Device';
            const newBtn = btn.cloneNode(true);
            btn.parentNode.replaceChild(newBtn, btn);
            newBtn.addEventListener('click', () => this.downloadFile());
        }
    }

    _hideDownloadCard() {
        const card = document.getElementById('download-ready-card');
        if (card) card.classList.add('hidden');
    }

    _showProgress(text, pct) {
        const wrap = document.getElementById('download-progress');
        const fill = document.getElementById('progress-fill-download');
        const lbl  = document.querySelector('#download-progress .progress-text');
        if (wrap) wrap.style.display = 'block';
        if (fill) fill.style.width   = `${pct}%`;
        if (lbl)  lbl.textContent    = text;
    }

    _hideProgress() {
        const wrap = document.getElementById('download-progress');
        const fill = document.getElementById('progress-fill-download');
        if (wrap) wrap.style.display = 'none';
        if (fill) fill.style.width   = '0%';
    }

    _resetSteps() {
        ['step-verify','step-fetch','step-combine'].forEach(id => {
            document.getElementById(id)?.classList.remove('active','completed');
        });
    }

    _setStep(id, state) {
        const el = document.getElementById(id);
        if (!el) return;
        el.classList.remove('active','completed');
        if (state === 'active')    el.classList.add('active');
        if (state === 'completed') el.classList.add('completed');
    }

    _showResult(type, html) {
        const el = document.getElementById('download-result');
        if (!el) return;
        el.className = `download-result ${type}`;
        el.innerHTML = `<p>${html}</p>`;
        el.style.display = 'block';
        if (type !== 'error') setTimeout(() => { el.style.display = 'none'; }, 15000);
    }

    _clearResult() {
        const el = document.getElementById('download-result');
        if (el) { el.style.display = 'none'; el.innerHTML = ''; }
    }

    _showToast(msg, type = 'success') {
        const c = document.getElementById('toast-container');
        if (!c) { console.log(`[${type}] ${msg}`); return; }
        const t = document.createElement('div');
        t.className = 'toast';
        const icons  = { success:'fa-circle-check', error:'fa-circle-exclamation', warning:'fa-triangle-exclamation', info:'fa-circle-info' };
        const colors = { success:'var(--success)', error:'var(--danger)', warning:'var(--warning)', info:'var(--primary)' };
        t.innerHTML  = `<i class="fa-solid ${icons[type]||icons.info}" style="color:${colors[type]||colors.info}"></i><span>${msg}</span>`;
        c.appendChild(t);
        setTimeout(() => { t.style.opacity='0'; setTimeout(()=>t.remove(),400); }, 3500);
    }

    _log(msg) {
        const el = document.getElementById('global-log');
        if (!el) return;
        const line = document.createElement('div');
        line.className = 'log-line';
        line.innerHTML = `<span class="ts">[DOWNLOAD]</span> ${msg}`;
        el.prepend(line);
        if (el.children.length > 25) el.lastChild.remove();
    }

    _fmtSize(b) {
        if (!b) return '0 B';
        const k = 1024, s = ['B','KB','MB','GB'];
        const i = Math.floor(Math.log(b) / Math.log(k));
        return parseFloat((b / Math.pow(k, i)).toFixed(2)) + ' ' + s[i];
    }

    _delay(ms) { return new Promise(r => setTimeout(r, ms)); }
}

// ── Global instance ────────────────────────────────────────
const downloader = new FileDownloader();

window.requestDownload = function () {
    const fileId = document.getElementById('file-id-input')?.value?.trim();
    if (!fileId) {
        downloader._showToast('Please enter a File ID', 'error');
        return;
    }
    downloader.requestDownload(fileId);
};

window.previewFile = function (fileIdOverride) {
    downloader.previewFile(fileIdOverride);
};

document.addEventListener('DOMContentLoaded', () => {
    const input = document.getElementById('file-id-input');
    if (input) {
        input.addEventListener('input', () => {
            const newId = input.value.trim();
            if (newId !== downloader._currentFileId) downloader.reset();
        });
        input.addEventListener('keydown', e => {
            if (e.key === 'Enter') window.requestDownload();
        });
    }
    downloader._log('📋 Download system initialized (full preview support)');
});