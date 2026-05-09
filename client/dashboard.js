// client/dashboard.js
class SystemDashboard {
    constructor() {
        this.nodes = {
            genesis: 'http://localhost:5001',
            peer: 'http://localhost:5002',
            noiseA: 'http://localhost:9001',
            noiseB: 'http://localhost:9002',
            phantombox: 'http://localhost:8000'
        };
        this.status = {};
        this.interval = null;
        this.dashboardInitialized = false;
    }

    startMonitoring() {
        // Check if dashboard container exists
        const dashboardContainer = document.getElementById('dashboard-container');
        if (!dashboardContainer) {
            console.log("Dashboard container not found, will initialize when tab is active");
            return;
        }
        
        // Create dashboard HTML only if it doesn't exist
        if (!this.dashboardInitialized) {
            const dashboardHTML = `
                <div class="dashboard-grid" style="display: grid; grid-template-columns: repeat(3, 1fr); gap: 15px; margin: 20px 0;">
                    <div class="dashboard-card" id="blockchain-card" style="padding: 15px; background: white; border-radius: 8px; border-left: 4px solid #007bff;">
                        <h4 style="margin: 0 0 10px 0;">🔗 Blockchain Network</h4>
                        <div id="blockchain-status-detail"></div>
                    </div>
                    <div class="dashboard-card" id="storage-card" style="padding: 15px; background: white; border-radius: 8px; border-left: 4px solid #28a745;">
                        <h4 style="margin: 0 0 10px 0;">💾 Noise Storage</h4>
                        <div id="storage-status-detail"></div>
                    </div>
                    <div class="dashboard-card" id="memory-card" style="padding: 15px; background: white; border-radius: 8px; border-left: 4px solid #ffc107;">
                        <h4 style="margin: 0 0 10px 0;">🧠 Memory Usage</h4>
                        <div id="memory-status-detail"></div>
                    </div>
                </div>
                <div class="visualization-area" id="visualization-area" style="margin: 20px 0;"></div>
            `;
            
            dashboardContainer.innerHTML = dashboardHTML;
            this.dashboardInitialized = true;
        }
        
        // Start monitoring only if dashboard is visible
        if (document.getElementById('dashboard-tab')?.classList.contains('active')) {
            this.startInterval();
        }
    }

    startInterval() {
        // Clear any existing interval
        if (this.interval) {
            clearInterval(this.interval);
        }
        
        // Start new interval
        this.interval = setInterval(() => this.updateDashboard(), 5000);
        this.updateDashboard();
    }

    stopMonitoring() {
        if (this.interval) {
            clearInterval(this.interval);
            this.interval = null;
        }
    }

    async updateDashboard() {
        // Only update if dashboard tab is active
        if (!document.getElementById('dashboard-tab')?.classList.contains('active')) {
            return;
        }
        
        try {
            await this.checkBlockchainStatus();
            await this.checkStorageStatus();
            await this.checkMemoryStatus();
            this.updateVisualization();
            this.updateStatusPanel();
        } catch (error) {
            console.error('Dashboard update failed:', error);
        }
    }

    async checkBlockchainStatus() {
        const statusDiv = document.getElementById('blockchain-status-detail');
        const topStatusDiv = document.getElementById('blockchain-status');
        const results = {};
        
        if (!statusDiv && !topStatusDiv) return;
        
        try {
            // Check Genesis Node
            const genesisRes = await fetch(`${this.nodes.genesis}/status`);
            results.genesis = genesisRes.ok ? '✅ Online' : '❌ Offline';
            
            // Check Peer Node
            const peerRes = await fetch(`${this.nodes.peer}/status`);
            results.peer = peerRes.ok ? '✅ Online' : '❌ Offline';
            
            // Get chain length if available
            const chainRes = await fetch(`${this.nodes.genesis}/chain`);
            if (chainRes.ok) {
                const data = await chainRes.json();
                results.blocks = data.length || 0;
            }
        } catch (e) {
            results.genesis = '❌ Offline';
            results.peer = '❌ Offline';
            results.blocks = 0;
        }
        
        // Update detailed status in dashboard
        if (statusDiv) {
            statusDiv.innerHTML = `
                <div>Genesis: ${results.genesis}</div>
                <div>Peer: ${results.peer}</div>
                <div>Blocks: ${results.blocks || 0}</div>
                <small>${new Date().toLocaleTimeString()}</small>
            `;
        }
        
        // Update top status panel
        if (topStatusDiv) {
            topStatusDiv.textContent = results.genesis === '✅ Online' ? '🟢 Online' : '🔴 Offline';
        }
    }

    async checkStorageStatus() {
        const statusDiv = document.getElementById('storage-status-detail');
        const topStatusDiv = document.getElementById('noise-nodes-status');
        const results = {};
        
        if (!statusDiv && !topStatusDiv) return;
        
        try {
            // Check Noise Node A
            const nodeARes = await fetch(`${this.nodes.noiseA}/status`);
            if (nodeARes.ok) {
                const data = await nodeARes.json();
                results.nodeA = `✅ ${data.fragment_count || 0} fragments`;
                results.nodeAOk = true;
            } else {
                results.nodeA = '❌ Offline';
                results.nodeAOk = false;
            }
            
            // Check Noise Node B
            const nodeBRes = await fetch(`${this.nodes.noiseB}/status`);
            if (nodeBRes.ok) {
                const data = await nodeBRes.json();
                results.nodeB = `✅ ${data.fragment_count || 0} fragments`;
                results.nodeBOk = true;
            } else {
                results.nodeB = '❌ Offline';
                results.nodeBOk = false;
            }
        } catch (e) {
            results.nodeA = '❌ Offline';
            results.nodeB = '❌ Offline';
            results.nodeAOk = false;
            results.nodeBOk = false;
        }
        
        // Update detailed status in dashboard
        if (statusDiv) {
            statusDiv.innerHTML = `
                <div>Node A: ${results.nodeA}</div>
                <div>Node B: ${results.nodeB}</div>
                <div>Total: ${(parseInt(results.nodeA?.match(/\d+/)) || 0) + (parseInt(results.nodeB?.match(/\d+/)) || 0)} fragments</div>
                <small>${new Date().toLocaleTimeString()}</small>
            `;
        }
        
        // Update top status panel
        if (topStatusDiv) {
            if (results.nodeAOk && results.nodeBOk) {
                topStatusDiv.textContent = '🟢 2/2 Online';
            } else if (results.nodeAOk || results.nodeBOk) {
                topStatusDiv.textContent = '🟡 1/2 Online';
            } else {
                topStatusDiv.textContent = '🔴 Offline';
            }
        }
    }

    async checkMemoryStatus() {
        const statusDiv = document.getElementById('memory-status-detail');
        const topStatusDiv = document.getElementById('memory-status');
        const filesInMemoryDiv = document.getElementById('files-in-memory');
        
        if (!statusDiv && !topStatusDiv) return;
        
        try {
            const res = await fetch(`${this.nodes.phantombox}/api/memory_stats`);
            if (res.ok) {
                const data = await res.json();
                
                // Update detailed status in dashboard
                if (statusDiv) {
                    statusDiv.innerHTML = `
                        <div>Files in RAM: ${data.total_files || 0}</div>
                        <div>Memory Used: ${this.formatBytes(data.total_memory || 0)}</div>
                        <div>Auto-wipe: ${data.total_files > 0 ? '⏰ Active' : '✅ Clean'}</div>
                        <small>${new Date().toLocaleTimeString()}</small>
                    `;
                }
                
                // Update top status panel
                if (topStatusDiv) {
                    topStatusDiv.textContent = `${this.formatBytes(data.total_memory || 0)}`;
                }
                
                // Update files in memory count
                if (filesInMemoryDiv) {
                    filesInMemoryDiv.textContent = data.total_files || 0;
                }
            }
        } catch (e) {
            if (statusDiv) {
                statusDiv.innerHTML = `❌ Cannot fetch memory stats`;
            }
        }
    }

    updateVisualization() {
        const visArea = document.getElementById('visualization-area');
        if (!visArea) return;
        
        // Simple ASCII visualization
        const visualization = `
            <div style="font-family: monospace; background: #1a1a1a; color: #00ff00; padding: 15px; border-radius: 5px;">
                <div style="margin-bottom: 10px;">🎯 System Topology:</div>
                <div style="margin-left: 20px;">
                    [PhantomBox] - Port 8000<br>
                    ├── [Blockchain Genesis] - Port 5001<br>
                    ├── [Blockchain Peer] - Port 5002<br>
                    ├── [Noise Node A] - Port 9001<br>
                    └── [Noise Node B] - Port 9002<br>
                </div>
                <div style="margin-top: 10px; color: #ffcc00;">
                    📈 Status: ${this.getAllStatus()}
                </div>
            </div>
        `;
        
        visArea.innerHTML = visualization;
    }

    updateStatusPanel() {
        // Update the files in memory count
        const filesInMemory = document.getElementById('files-in-memory');
        if (filesInMemory) {
            const memoryStats = document.getElementById('memory-status-detail');
            if (memoryStats) {
                const text = memoryStats.textContent || '';
                const match = text.match(/Files in RAM: (\d+)/);
                if (match) {
                    filesInMemory.textContent = match[1];
                }
            }
        }
    }

    getAllStatus() {
        const blockchainDiv = document.getElementById('blockchain-status-detail');
        const storageDiv = document.getElementById('storage-status-detail');
        const memoryDiv = document.getElementById('memory-status-detail');
        
        const genesisStatus = blockchainDiv?.textContent?.includes('✅') ? 'OK' : 'FAIL';
        const storageStatus = storageDiv?.textContent?.includes('✅') ? 'OK' : 'FAIL';
        const memoryStatus = memoryDiv?.textContent?.includes('❌') ? 'FAIL' : 'OK';
        
        return `Blockchain: ${genesisStatus} | Storage: ${storageStatus} | Memory: ${memoryStatus}`;
    }

    formatBytes(bytes) {
        if (bytes === 0) return '0 Bytes';
        const k = 1024;
        const sizes = ['Bytes', 'KB', 'MB', 'GB'];
        const i = Math.floor(Math.log(bytes) / Math.log(k));
        return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
    }

    // Method to call when tab is switched to dashboard
    onDashboardTabActivated() {
        if (!this.dashboardInitialized) {
            this.startMonitoring();
        } else {
            this.startInterval();
        }
    }

    // Method to call when tab is switched away from dashboard
    onDashboardTabDeactivated() {
        this.stopMonitoring();
    }
}

// Initialize dashboard
const dashboard = new SystemDashboard();

// Export for use in other files
window.SystemDashboard = dashboard;