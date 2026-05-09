// client/lifecycle.js
class FileLifecycleTracker {
    constructor() {
        this.container = null;
    }

    showLifecycle(fileId) {
        // Create lifecycle container
        if (!this.container) {
            this.container = document.createElement('div');
            this.container.id = 'lifecycle-container';
            this.container.style.cssText = `
                margin: 20px 0;
                padding: 20px;
                background: #f8f9fa;
                border-radius: 10px;
                border: 1px solid #dee2e6;
            `;
            
            // Insert after dashboard
            const dashboard = document.querySelector('.dashboard-container');
            if (dashboard) {
                dashboard.insertAdjacentElement('afterend', this.container);
            }
        }

        this.container.innerHTML = `
            <h3 style="margin: 0 0 15px 0;">🔄 File Lifecycle: ${fileId.substring(0, 12)}...</h3>
            <div id="lifecycle-timeline" style="margin: 20px 0;"></div>
        `;

        this.updateLifecycle(fileId);
    }

    async updateLifecycle(fileId) {
        try {
            const response = await fetch(`http://localhost:8000/api/file_lifecycle/${fileId}`);
            if (!response.ok) throw new Error('Failed to fetch lifecycle');
            
            const data = await response.json();
            
            const timelineDiv = document.getElementById('lifecycle-timeline');
            timelineDiv.innerHTML = this.createTimelineHTML(data);
            
            // Auto-refresh if file is active
            if (data.status === 'active_in_memory') {
                setTimeout(() => this.updateLifecycle(fileId), 3000);
            }
        } catch (error) {
            console.error('Lifecycle error:', error);
        }
    }

    createTimelineHTML(data) {
        let html = `
            <div style="position: relative; padding-left: 30px;">
                <div style="position: absolute; left: 0; top: 0; bottom: 0; width: 2px; background: #007bff;"></div>
        `;
        
        data.stages.forEach((stage, index) => {
            const time = new Date(stage.timestamp).toLocaleTimeString();
            html += `
                <div style="position: relative; margin-bottom: 20px;">
                    <div style="position: absolute; left: -35px; top: 0; width: 20px; height: 20px; 
                         border-radius: 50%; background: ${this.getStageColor(stage.stage)}; 
                         border: 3px solid white; box-shadow: 0 0 5px rgba(0,0,0,0.2);"></div>
                    <div style="background: white; padding: 15px; border-radius: 8px; box-shadow: 0 2px 5px rgba(0,0,0,0.1);">
                        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 5px;">
                            <strong>${stage.status} ${stage.stage}</strong>
                            <small style="color: #666;">${time}</small>
                        </div>
                        ${stage.details ? `<small style="color: #666;">${stage.details}</small>` : ''}
                    </div>
                </div>
            `;
        });
        
        html += `
                <div style="margin-top: 20px; padding: 10px; background: #e7f5ff; border-radius: 5px; border-left: 4px solid #0066cc;">
                    <strong>Final Status:</strong> ${data.status.toUpperCase().replace('_', ' ')}
                </div>
            </div>
        `;
        
        return html;
    }

    getStageColor(stage) {
        const colors = {
            'UPLOADED': '#28a745',
            'FRAGMENTED': '#17a2b8',
            'NOISE_STORED': '#6610f2',
            'BLOCKCHAIN_REGISTERED': '#fd7e14',
            'RECONSTRUCTED_IN_RAM': '#dc3545',
            'DESTROYED': '#6c757d'
        };
        return colors[stage] || '#6c757d';
    }
}

// Global lifecycle tracker
window.LifecycleTracker = new FileLifecycleTracker();

