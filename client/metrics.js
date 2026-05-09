// client/metrics.js
class SecurityMetrics {
    constructor() {
        this.container = null;
        this.interval = null;
    }

    createUI() {
        return `
            <div class="card" style="margin: 20px 0;">
                <h2>📊 Security Metrics & Evaluation</h2>
                <p style="color: #666; margin-bottom: 20px;">
                    Measurable security outcomes and system evaluation
                </p>
                
                <div class="metrics-grid" style="display: grid; grid-template-columns: repeat(2, 1fr); gap: 15px; margin-bottom: 20px;">
                    <div id="overall-score" style="grid-column: span 2; padding: 20px; background: linear-gradient(135deg, #667eea, #764ba2); color: white; border-radius: 10px; text-align: center;">
                        <h3 style="margin: 0 0 10px 0;">Overall Security Score</h3>
                        <div style="font-size: 3em; font-weight: bold;" id="score-value">--</div>
                        <div id="security-level">Loading...</div>
                    </div>
                    
                    <div class="metric-card" id="system-health">
                        <h4>🖥️ System Health</h4>
                        <div class="metric-content"></div>
                    </div>
                    
                    <div class="metric-card" id="fragment-security">
                        <h4>🧩 Fragment Security</h4>
                        <div class="metric-content"></div>
                    </div>
                    
                    <div class="metric-card" id="blockchain-security">
                        <h4>🔗 Blockchain Security</h4>
                        <div class="metric-content"></div>
                    </div>
                    
                    <div class="metric-card" id="memory-security">
                        <h4>🧠 Memory Security</h4>
                        <div class="metric-content"></div>
                    </div>
                </div>
                
                <button class="btn btn-primary" onclick="metrics.updateMetrics()" style="width: 100%;">
                    🔄 Refresh Metrics
                </button>
            </div>
        `;
    }

    startMonitoring() {
        // Insert after threat simulation
        const threatsSection = document.querySelector('.threat-buttons')?.closest('.card');
        if (threatsSection) {
            threatsSection.insertAdjacentHTML('afterend', this.createUI());
        }
        
        // Add CSS
        this.addStyles();
        
        // Start periodic updates
        this.updateMetrics();
        this.interval = setInterval(() => this.updateMetrics(), 30000);
    }

    addStyles() {
        const style = document.createElement('style');
        style.textContent = `
            .metric-card {
                padding: 15px;
                background: white;
                border-radius: 8px;
                border: 1px solid #dee2e6;
            }
            
            .metric-card h4 {
                margin: 0 0 10px 0;
                color: #495057;
                display: flex;
                align-items: center;
                gap: 8px;
            }
            
            .metric-content {
                font-size: 0.9em;
                color: #666;
            }
            
            .metric-item {
                display: flex;
                justify-content: space-between;
                margin: 5px 0;
                padding: 3px 0;
                border-bottom: 1px solid #f8f9fa;
            }
            
            .progress-bar-metric {
                height: 6px;
                background: #e9ecef;
                border-radius: 3px;
                margin: 5px 0;
                overflow: hidden;
            }
            
            .progress-fill-metric {
                height: 100%;
                border-radius: 3px;
                transition: width 0.5s;
            }
        `;
        document.head.appendChild(style);
    }

    async updateMetrics() {
        try {
            const response = await fetch('http://localhost:8000/api/security_metrics');
            if (!response.ok) throw new Error('Failed to fetch metrics');
            
            const data = await response.json();
            this.displayMetrics(data);
        } catch (error) {
            console.error('Metrics error:', error);
        }
    }

    displayMetrics(data) {
        // Overall Score
        document.getElementById('score-value').textContent = Math.round(data.overall_score);
        document.getElementById('security-level').textContent = data.security_level || '--';
        
        // System Health
        this.updateMetricCard('system-health', data.system_health, '#28a745');
        
        // Fragment Security
        this.updateMetricCard('fragment-security', data.fragment_security, '#17a2b8');
        
        // Blockchain Security
        this.updateMetricCard('blockchain-security', data.blockchain_security, '#fd7e14');
        
        // Memory Security
        this.updateMetricCard('memory-security', data.memory_security, '#dc3545');
    }

    updateMetricCard(cardId, data, color) {
        const card = document.getElementById(cardId);
        if (!card || !data) return;
        
        let html = '<div>';
        
        for (const [key, value] of Object.entries(data)) {
            if (key === 'error') {
                html += `<div style="color: #dc3545;">❌ ${value}</div>`;
            } else if (typeof value === 'number' && key.includes('percentage') || key.includes('score')) {
                html += `
                    <div class="metric-item">
                        <span>${this.formatKey(key)}:</span>
                        <span>${Math.round(value)}%</span>
                    </div>
                    <div class="progress-bar-metric">
                        <div class="progress-fill-metric" style="width: ${value}%; background: ${color};"></div>
                    </div>
                `;
            } else if (typeof value === 'number') {
                html += `
                    <div class="metric-item">
                        <span>${this.formatKey(key)}:</span>
                        <span>${value.toLocaleString()}</span>
                    </div>
                `;
            } else if (typeof value === 'boolean') {
                html += `
                    <div class="metric-item">
                        <span>${this.formatKey(key)}:</span>
                        <span>${value ? '✅ Yes' : '❌ No'}</span>
                    </div>
                `;
            } else {
                html += `
                    <div class="metric-item">
                        <span>${this.formatKey(key)}:</span>
                        <span>${value}</span>
                    </div>
                `;
            }
        }
        
        html += '</div>';
        card.querySelector('.metric-content').innerHTML = html;
    }

    formatKey(key) {
        return key.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase());
    }
}

// Global metrics monitor
window.metrics = new SecurityMetrics();
