// client/explorer.js
class BlockchainExplorer {
    constructor() {
        this.container = null;
    }

    createUI() {
        return `
            <div class="card" style="margin: 20px 0;">
                <h2>🔍 Blockchain Explorer & Audit Trail</h2>
                <p style="color: #666; margin-bottom: 20px;">
                    View blockchain data and file registration history
                </p>
                
                <div class="explorer-tabs" style="margin-bottom: 20px;">
                    <button class="btn btn-outline-primary active" onclick="explorer.showTab('blocks')">
                        📦 Blocks
                    </button>
                    <button class="btn btn-outline-primary" onclick="explorer.showTab('files')">
                        📄 File Registrations
                    </button>
                    <button class="btn btn-outline-primary" onclick="explorer.showTab('chain')">
                        🔗 Chain Info
                    </button>
                </div>
                
                <div id="explorer-content" style="min-height: 300px;">
                    <div class="text-center" style="padding: 50px;">
                        <div class="spinner-border text-primary" role="status">
                            <span class="visually-hidden">Loading...</span>
                        </div>
                        <p>Loading blockchain data...</p>
                    </div>
                </div>
                
                <button class="btn btn-primary" onclick="explorer.loadData()" style="width: 100%; margin-top: 20px;">
                    🔄 Refresh Blockchain Data
                </button>
            </div>
        `;
    }

    async loadData() {
        try {
            const response = await fetch('http://localhost:8000/api/blockchain/explorer');
            if (!response.ok) throw new Error('Failed to load blockchain data');
            
            const data = await response.json();
            this.data = data;
            this.showTab('blocks');
        } catch (error) {
            document.getElementById('explorer-content').innerHTML = `
                <div style="padding: 30px; text-align: center; color: #dc3545;">
                    ❌ Cannot connect to blockchain: ${error.message}
                </div>
            `;
        }
    }

    showTab(tabName) {
        const contentDiv = document.getElementById('explorer-content');
        
        // Update active tab
        document.querySelectorAll('.explorer-tabs .btn').forEach(btn => {
            btn.classList.remove('active');
            btn.classList.add('btn-outline-primary');
        });
        
        const activeBtn = document.querySelector(`.explorer-tabs button[onclick*="${tabName}"]`);
        if (activeBtn) {
            activeBtn.classList.remove('btn-outline-primary');
            activeBtn.classList.add('active');
        }
        
        // Show content
        switch(tabName) {
            case 'blocks':
                contentDiv.innerHTML = this.renderBlocks();
                break;
            case 'files':
                contentDiv.innerHTML = this.renderFiles();
                break;
            case 'chain':
                contentDiv.innerHTML = this.renderChainInfo();
                break;
        }
    }

    renderBlocks() {
        if (!this.data || !this.data.blocks) return '<div>No blocks found</div>';
        
        const blocks = this.data.blocks.reverse(); // Show newest first
        
        let html = `
            <div style="font-size: 0.9em;">
                <div style="display: grid; grid-template-columns: 60px 1fr 150px; gap: 10px; padding: 10px; background: #f8f9fa; border-radius: 5px; margin-bottom: 10px; font-weight: bold;">
                    <div>#</div>
                    <div>Type / Data</div>
                    <div>Timestamp</div>
                </div>
        `;
        
        blocks.forEach(block => {
            const time = new Date(block.timestamp * 1000).toLocaleTimeString();
            const date = new Date(block.timestamp * 1000).toLocaleDateString();
            
            html += `
                <div style="display: grid; grid-template-columns: 60px 1fr 150px; gap: 10px; padding: 10px; border-bottom: 1px solid #dee2e6; align-items: center;">
                    <div style="font-family: monospace; font-weight: bold;">${block.index}</div>
                    <div>
                        <div style="font-weight: bold; color: ${block.type === 'genesis' ? '#28a745' : '#007bff'}">
                            ${block.type === 'genesis' ? '🎯 GENESIS' : '📄 FILE_REG'}
                        </div>
                        ${block.type === 'file_registration' ? 
                          `<small>File: ${block.data.file_id?.substring(0, 16)}...</small>` : 
                          `<small>${block.data.message || 'Block data'}</small>`}
                    </div>
                    <div>
                        <div>${time}</div>
                        <small style="color: #666;">${date}</small>
                    </div>
                </div>
            `;
        });
        
        html += `</div>`;
        return html;
    }

    renderFiles() {
        if (!this.data || !this.data.files) return '<div>No files registered</div>';
        
        const files = this.data.files.reverse();
        
        let html = `
            <div style="font-size: 0.9em;">
                <div style="display: grid; grid-template-columns: 1fr 100px 80px 120px; gap: 10px; padding: 10px; background: #f8f9fa; border-radius: 5px; margin-bottom: 10px; font-weight: bold;">
                    <div>File ID</div>
                    <div>Fragments</div>
                    <div>Block</div>
                    <div>Registered</div>
                </div>
        `;
        
        files.forEach(file => {
            const time = new Date(file.timestamp * 1000).toLocaleTimeString();
            
            html += `
                <div style="display: grid; grid-template-columns: 1fr 100px 80px 120px; gap: 10px; padding: 10px; border-bottom: 1px solid #dee2e6; align-items: center;">
                    <div style="font-family: monospace; font-size: 0.85em;">
                        ${file.file_id?.substring(0, 24)}...
                    </div>
                    <div>
                        <span class="badge" style="background: #17a2b8; color: white; padding: 2px 8px; border-radius: 10px;">
                            ${file.fragment_count || 0}
                        </span>
                    </div>
                    <div style="font-family: monospace;">#${file.block_index}</div>
                    <div>
                        <div>${time}</div>
                        <small style="color: #666;">${Math.floor((Date.now()/1000 - file.timestamp)/60)} min ago</small>
                    </div>
                </div>
            `;
        });
        
        html += `</div>`;
        return html;
    }

    renderChainInfo() {
        if (!this.data) return '<div>No chain data</div>';
        
        return `
            <div style="display: grid; grid-template-columns: repeat(2, 1fr); gap: 20px;">
                <div style="padding: 20px; background: #f8f9fa; border-radius: 8px;">
                    <h4>📊 Chain Statistics</h4>
                    <div style="margin-top: 15px;">
                        <div class="metric-item">
                            <span>Total Blocks:</span>
                            <span style="font-weight: bold;">${this.data.total_blocks}</span>
                        </div>
                        <div class="metric-item">
                            <span>File Registrations:</span>
                            <span style="font-weight: bold;">${this.data.file_registrations}</span>
                        </div>
                        <div class="metric-item">
                            <span>Consensus:</span>
                            <span style="color: ${this.data.consensus === 'in_sync' ? '#28a745' : '#dc3545'}; font-weight: bold;">
                                ${this.data.consensus === 'in_sync' ? '✅ IN SYNC' : '⚠️ OUT OF SYNC'}
                            </span>
                        </div>
                    </div>
                </div>
                
                <div style="padding: 20px; background: #f8f9fa; border-radius: 8px;">
                    <h4>🔐 Audit Trail Purpose</h4>
                    <ul style="margin: 15px 0; padding-left: 20px;">
                        <li>Immutable record of file metadata</li>
                        <li>Tamper-proof fragment distribution log</li>
                        <li>Access rule enforcement ledger</li>
                        <li>Forensic evidence of data lifecycle</li>
                    </ul>
                    <div style="margin-top: 15px; padding: 10px; background: #e7f5ff; border-radius: 5px;">
                        <strong>Key Viva Point:</strong> Blockchain is used as an <em>audit ledger</em>, not as storage.
                    </div>
                </div>
            </div>
        `;
    }
}

// Global explorer
window.explorer = new BlockchainExplorer();

