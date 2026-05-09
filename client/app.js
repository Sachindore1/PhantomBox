// client/app.js - Main Application Controller with Distributed VM Support
const API_URL = (() => {
    const hostname = window.location.hostname;
    const port = '8000';
    return `http://${hostname}:${port}/api`;
})();

// ========== Navigation ==========
// ========== Navigation ==========
function switchView(viewId) {
    // Update active states
    document.querySelectorAll('.view-section').forEach(el => el.classList.remove('active'));
    document.querySelectorAll('.nav-item').forEach(el => el.classList.remove('active'));
    
    const view = document.getElementById(`view-${viewId}`);
    if (view) view.classList.add('active');
    
    // Find and activate nav button
    const navBtn = Array.from(document.querySelectorAll('.nav-item')).find(
        btn => btn.textContent.toLowerCase().includes(viewId)
    );
    if (navBtn) navBtn.classList.add('active');
    
    // Update content based on view
    if (viewId === 'dashboard') updateDashboard();
    if (viewId === 'ledger') updateLedger();
    
    // SIMPLE HISTORY VIEW UPDATE
    if (viewId === 'history') {
        console.log('📋 Switching to history view');
        
        // Try historyManager first
        if (window.historyManager && typeof window.historyManager.updateUploadHistoryUI === 'function') {
            window.historyManager.updateUploadHistoryUI();
            window.historyManager.updateDownloadHistoryUI();
            console.log('✅ History updated via historyManager');
        } 
        // Try window.history second
        else if (window.history && typeof window.history.updateUploadHistoryUI === 'function') {
            window.history.updateUploadHistoryUI();
            window.history.updateDownloadHistoryUI();
            console.log('✅ History updated via window.history');
        }
        else {
            console.warn('⚠️ History functions not available');
        }
    }
    
    // Log view change
    log(`Switched to ${viewId} view`, 'UI');
}

// ========== System Log ==========
function log(message, type = 'SYSTEM') {
    const term = document.getElementById('global-log');
    if (!term) return;
    
    const line = document.createElement('div');
    line.className = 'log-line';
    line.innerHTML = `<span class="ts">[${type}]</span> ${message}`;
    term.prepend(line);
    
    // Keep max 25 lines
    while (term.children.length > 25) {
        term.lastChild.remove();
    }
}

// ========== Format Utilities ==========
function formatFileSize(bytes) {
    if (bytes === 0) return '0 B';
    const k = 1024;
    const sizes = ['B', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
}

function formatTimestamp(timestamp) {
    const date = new Date(timestamp * 1000);
    return date.toLocaleString();
}

// ========== System Status ==========
// ========== System Status ==========
async function checkSystemStatus() {
    const statusElements = {
        genesis: document.getElementById('genesis-status'),
        peer: document.getElementById('peer-status'),
        noiseA: document.getElementById('noiseA-status'),
        noiseB: document.getElementById('noiseB-status'),
        memory: document.getElementById('memory-status')
    };
    
    try {
        // Check PhantomBox health (just for logging, not counted as a node)
        const phantomboxResponse = await fetch(`http://${window.location.hostname}:8000/health`).catch(() => ({ ok: false }));
        log(`System health: ${phantomboxResponse.ok ? '✅' : '❌'}`, 'NET');
        
        let nodesOnline = 0; // Start at 0 - we only count the 4 actual nodes
        let totalNodes = 4;  // Genesis + Peer + NoiseA + NoiseB = 4 total nodes
        
        // Check Genesis Node (port 5001)
        try {
            const genesisRes = await fetch(`http://${window.location.hostname}:5001/status`, { 
                timeout: 2000 
            }).catch(() => null);
            
            if (statusElements.genesis) {
                const isOnline = genesisRes && genesisRes.ok;
                statusElements.genesis.textContent = isOnline ? '🟢 Online' : '🔴 Offline';
                statusElements.genesis.style.color = isOnline ? 'var(--success)' : 'var(--danger)';
                if (isOnline) nodesOnline++;
                console.log(`Genesis Node: ${isOnline ? 'Online' : 'Offline'}`);
            }
        } catch (e) {
            if (statusElements.genesis) {
                statusElements.genesis.textContent = '🔴 Offline';
                statusElements.genesis.style.color = 'var(--danger)';
            }
            console.log('Genesis Node: Offline (error)');
        }
        
        // Check Peer Node (port 5002)
        try {
            const peerRes = await fetch(`http://${window.location.hostname}:5002/status`, { 
                timeout: 2000 
            }).catch(() => null);
            
            if (statusElements.peer) {
                const isOnline = peerRes && peerRes.ok;
                statusElements.peer.textContent = isOnline ? '🟢 Online' : '🔴 Offline';
                statusElements.peer.style.color = isOnline ? 'var(--success)' : 'var(--danger)';
                if (isOnline) nodesOnline++;
                console.log(`Peer Node: ${isOnline ? 'Online' : 'Offline'}`);
            }
        } catch (e) {
            if (statusElements.peer) {
                statusElements.peer.textContent = '🔴 Offline';
                statusElements.peer.style.color = 'var(--danger)';
            }
            console.log('Peer Node: Offline (error)');
        }
        
        // Check Noise Node A (port 9001)
        try {
            const noiseARes = await fetch(`http://${window.location.hostname}:9001/status`, { 
                timeout: 2000 
            }).catch(() => null);
            
            if (statusElements.noiseA) {
                const isOnline = noiseARes && noiseARes.ok;
                statusElements.noiseA.textContent = isOnline ? '🟢 Online' : '🔴 Offline';
                statusElements.noiseA.style.color = isOnline ? 'var(--success)' : 'var(--danger)';
                if (isOnline) nodesOnline++;
                console.log(`Noise Node A: ${isOnline ? 'Online' : 'Offline'}`);
            }
        } catch (e) {
            if (statusElements.noiseA) {
                statusElements.noiseA.textContent = '🔴 Offline';
                statusElements.noiseA.style.color = 'var(--danger)';
            }
            console.log('Noise Node A: Offline (error)');
        }
        
        // Check Noise Node B (port 9002)
        try {
            const noiseBRes = await fetch(`http://${window.location.hostname}:9002/status`, { 
                timeout: 2000 
            }).catch(() => null);
            
            if (statusElements.noiseB) {
                const isOnline = noiseBRes && noiseBRes.ok;
                statusElements.noiseB.textContent = isOnline ? '🟢 Online' : '🔴 Offline';
                statusElements.noiseB.style.color = isOnline ? 'var(--success)' : 'var(--danger)';
                if (isOnline) nodesOnline++;
                console.log(`Noise Node B: ${isOnline ? 'Online' : 'Offline'}`);
            }
        } catch (e) {
            if (statusElements.noiseB) {
                statusElements.noiseB.textContent = '🔴 Offline';
                statusElements.noiseB.style.color = 'var(--danger)';
            }
            console.log('Noise Node B: Offline (error)');
        }
        
        // Update nodes count - ONLY count the 4 infrastructure nodes
        const nodesEl = document.getElementById('stat-nodes');
        if (nodesEl) {
            nodesEl.textContent = `${nodesOnline}/${totalNodes} Nodes`;
            console.log(`Infrastructure nodes online: ${nodesOnline}/${totalNodes}`);
        }
        
        // Check memory stats
        try {
            const memRes = await fetch(`${API_URL}/memory_stats`, { timeout: 2000 });
            if (memRes.ok) {
                const memData = await memRes.json();
                if (statusElements.memory) {
                    statusElements.memory.textContent = formatFileSize(memData.total_memory || 0);
                }
                document.getElementById('stat-memory').textContent = formatFileSize(memData.total_memory || 0);
            }
        } catch (e) {
            console.warn('Memory stats unavailable:', e);
            if (statusElements.memory) {
                statusElements.memory.textContent = '0 B';
            }
        }
        
    } catch (error) {
        console.error('Status check failed:', error);
    }
}

// ========== Dashboard ==========
async function updateDashboard() {
    try {
        // Try to get blockchain data
        let totalBlocks = 0;
        let fileRegistrations = 0;
        
        try {
            const res = await fetch(`http://${window.location.hostname}:5001/chain`).catch(() => null);
            if (res?.ok) {
                const data = await res.json();
                totalBlocks = data.chain?.length || 0;
                
                // Count file registrations
                if (data.chain) {
                    fileRegistrations = data.chain.filter(
                        block => block.data?.type === 'file_registration'
                    ).length;
                }
            }
        } catch (e) {
            console.warn('Blockchain unavailable for dashboard');
        }
        
        // Update with fallback to history if blockchain unavailable
        if (totalBlocks === 0) {
            totalBlocks = 'Sync...';
        }
        
        // FIXED: Use historyManager instead of window.history
        if (fileRegistrations === 0) {
            // Try historyManager first
            if (window.historyManager && window.historyManager.uploads) {
                fileRegistrations = window.historyManager.uploads.length || 0;
                console.log(`📊 Using historyManager uploads: ${fileRegistrations}`);
            } 
            // Fallback to window.history
            else if (window.history && window.history.uploads) {
                fileRegistrations = window.history.uploads.length || 0;
                console.log(`📊 Using window.history uploads: ${fileRegistrations}`);
            }
            // Last resort - check localStorage directly
            else {
                try {
                    const stored = localStorage.getItem('phantombox_uploads');
                    if (stored) {
                        const uploads = JSON.parse(stored);
                        fileRegistrations = uploads.length || 0;
                        console.log(`📊 Using localStorage uploads: ${fileRegistrations}`);
                    }
                } catch (e) {
                    console.warn('Could not read from localStorage');
                }
            }
        }
        
        // Update DOM elements
        const blocksEl = document.getElementById('stat-blocks');
        if (blocksEl) blocksEl.textContent = totalBlocks;
        
        const filesEl = document.getElementById('stat-files');
        if (filesEl) filesEl.textContent = fileRegistrations;
        
    } catch (e) {
        console.error('Dashboard update failed:', e);
    }
}

// ========== Ledger ==========
async function updateLedger() {
    const tbody = document.getElementById('ledger-body');
    if (!tbody) return;
    
    try {
        const res = await fetch(`http://${window.location.hostname}:5001/chain`).catch(() => null);
        
        if (!res?.ok) {
            tbody.innerHTML = `
                <tr>
                    <td colspan="5" class="empty-history">
                        <i class="fa-solid fa-link-slash"></i>
                        <p>Blockchain node not available</p>
                        <small style="color: var(--text-muted);">Check connection to ${window.location.hostname}:5001</small>
                    </td>
                </tr>
            `;
            return;
        }
        
        const data = await res.json();
        const chain = data.chain || [];
        
        if (chain.length === 0) {
            tbody.innerHTML = `
                <tr>
                    <td colspan="5" class="empty-history">
                        <i class="fa-solid fa-link"></i>
                        <p>No blocks in chain</p>
                    </td>
                </tr>
            `;
            return;
        }
        
        tbody.innerHTML = chain.reverse().slice(0, 15).map(block => {
            const blockData = block.data || {};
            const blockType = blockData.type || 'unknown';
            const fileId = blockData.file_id || '-';
            const time = new Date(block.timestamp * 1000).toLocaleString();
            
            return `
                <tr>
                    <td><span style="color: var(--primary); font-weight: 600;">#${block.index}</span></td>
                    <td>
                        <span class="status-badge ${blockType === 'genesis' ? 'status-verified' : 'status-pending'}" 
                              style="background: ${blockType === 'genesis' ? 'rgba(16,185,129,0.15)' : 'rgba(42,125,225,0.15)'};">
                            ${blockType === 'genesis' ? '🎯 GENESIS' : '📄 FILE_REG'}
                        </span>
                    </td>
                    <td style="font-family: var(--font-mono); font-size: 0.8rem; color: var(--text-muted);">
                        ${block.hash?.substring(0, 12)}...${block.hash?.substring(block.hash.length - 8)}
                    </td>
                    <td style="font-family: var(--font-mono); font-size: 0.8rem; color: var(--primary);">
                        ${fileId !== '-' ? fileId.substring(0, 16) + '...' : '-'}
                    </td>
                    <td>${time}</td>
                </tr>
            `;
        }).join('');
        
    } catch (e) {
        console.error('Ledger update failed:', e);
        tbody.innerHTML = `
            <tr>
                <td colspan="5" class="empty-history">
                    <i class="fa-solid fa-triangle-exclamation"></i>
                    <p>Failed to load ledger</p>
                </td>
            </tr>
        `;
    }
}

function refreshLedger() {
    const btn = document.querySelector('.icon-btn i');
    if (btn) btn.classList.add('fa-spin');
    updateLedger().then(() => {
        setTimeout(() => btn?.classList.remove('fa-spin'), 500);
        log('Ledger refreshed', 'CHAIN');
    });
}

// ========== Time Update ==========
setInterval(() => {
    const timeEl = document.getElementById('current-time');
    if (timeEl) {
        timeEl.textContent = new Date().toLocaleTimeString();
    }
}, 1000);

// ========== Initialize ==========
document.addEventListener('DOMContentLoaded', () => {
    log('PhantomBox Distributed System initialized', 'SYSTEM');
    log(`Connected to: ${window.location.hostname}`, 'NET');
    
    // Immediate status check
    setTimeout(() => {
        // Check system status immediately
        checkSystemStatus().then(() => {
            console.log('✅ Initial status check complete');
        });
        
        // Set up intervals
        setInterval(checkSystemStatus, 10000); // Every 10 seconds
        setInterval(updateDashboard, 10000); // Every 10 seconds
        
        // Update dashboard
        updateDashboard();
    }, 500); // Small delay to ensure everything is loaded
});

// Global functions
window.switchView = switchView;
window.refreshLedger = refreshLedger;
window.formatFileSize = formatFileSize;
window.formatTimestamp = formatTimestamp;
window.log = log;
