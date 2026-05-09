// tabs.js - Tab management utilities
class TabManager {
    constructor() {
        this.currentTab = 'dashboard';
        this.tabComponents = {
            'dashboard': {
                init: () => {
                    dashboard.startMonitoring();
                },
                destroy: () => {
                    dashboard.stopMonitoring();
                }
            },
            'upload': {
                init: () => {
                    // Initialize upload tab if needed
                    if (uploader && uploader.updateRecentFilesList) {
                        uploader.updateRecentFilesList();
                    }
                }
            },
            'download': {
                init: () => {
                    // Initialize download tab if needed
                    const fileIdInput = document.getElementById('file-id-input');
                    if (fileIdInput) {
                        fileIdInput.focus();
                    }
                }
            },
            'explorer': {
                init: () => {
                    const container = document.getElementById('explorer-container');
                    if (container) {
                        container.innerHTML = explorer.createUI();
                        explorer.loadData();
                    }
                },
                destroy: () => {
                    // Clean up explorer resources if needed
                }
            },
            'security': {
                init: () => {
                    const metricsContainer = document.getElementById('metrics-container');
                    if (metricsContainer) {
                        metricsContainer.innerHTML = metrics.createUI();
                        metrics.startMonitoring();
                    }
                },
                destroy: () => {
                    metrics.stopMonitoring();
                }
            }
        };
    }

    switchTo(tabName) {
        // Store previous tab
        const previousTab = this.currentTab;
        
        // Destroy previous tab components if needed
        if (previousTab !== tabName && this.tabComponents[previousTab]) {
            const destroyFn = this.tabComponents[previousTab].destroy;
            if (destroyFn && typeof destroyFn === 'function') {
                destroyFn();
            }
        }
        
        // Hide previous tab content
        const previousTabElement = document.getElementById(`${previousTab}-tab`);
        if (previousTabElement) {
            previousTabElement.classList.remove('active');
        }
        
        // Update menu buttons
        document.querySelectorAll('.menu-btn').forEach(btn => {
            btn.classList.remove('active');
            const btnText = btn.textContent.toLowerCase();
            if (btnText.includes(tabName) || 
                (tabName === 'dashboard' && btnText.includes('📊')) ||
                (tabName === 'upload' && btnText.includes('📤')) ||
                (tabName === 'download' && btnText.includes('📥')) ||
                (tabName === 'explorer' && btnText.includes('🔍')) ||
                (tabName === 'security' && btnText.includes('🛡️'))) {
                btn.classList.add('active');
            }
        });
        
        // Show new tab
        const newTab = document.getElementById(`${tabName}-tab`);
        if (newTab) {
            newTab.classList.add('active');
            this.currentTab = tabName;
            
            // Initialize tab if needed
            if (this.tabComponents[tabName]) {
                const initFn = this.tabComponents[tabName].init;
                if (initFn && typeof initFn === 'function') {
                    // Small delay to ensure DOM is ready
                    setTimeout(() => initFn(), 50);
                }
            }
            
            // Update browser URL without reloading
            this.updateUrlHash(tabName);
        }
        
        // Scroll to top for better UX
        window.scrollTo({ top: 0, behavior: 'smooth' });
        
        // Log tab switch for debugging
        console.log(`Tab switched from ${previousTab} to ${tabName}`);
    }

    updateUrlHash(tabName) {
        // Update URL hash for bookmarking
        if (history.pushState) {
            const newUrl = `${window.location.pathname}#${tabName}`;
            window.history.pushState(null, '', newUrl);
        }
    }

    getCurrentTab() {
        return this.currentTab;
    }

    refreshCurrentTab() {
        if (this.tabComponents[this.currentTab]) {
            const initFn = this.tabComponents[this.currentTab].init;
            if (initFn && typeof initFn === 'function') {
                initFn();
            }
        }
    }

    initializeFromUrl() {
        // Initialize tab from URL hash if present
        const hash = window.location.hash.substring(1);
        if (hash && this.tabComponents[hash]) {
            this.switchTo(hash);
        } else {
            // Default to dashboard
            this.switchTo('dashboard');
        }
    }

    // Utility method to check if a tab exists
    hasTab(tabName) {
        return this.tabComponents.hasOwnProperty(tabName);
    }

    // Method to get all available tab names
    getAvailableTabs() {
        return Object.keys(this.tabComponents);
    }
}

// Create global tab manager
window.tabManager = new TabManager();

// Enhanced switchTab function
function switchTab(tabName) {
    if (window.tabManager.hasTab(tabName)) {
        window.tabManager.switchTo(tabName);
    } else {
        console.error(`Tab "${tabName}" does not exist. Available tabs:`, window.tabManager.getAvailableTabs());
        // Fall back to dashboard
        window.tabManager.switchTo('dashboard');
    }
}

// Handle browser back/forward buttons
window.addEventListener('popstate', () => {
    const hash = window.location.hash.substring(1);
    if (hash && window.tabManager.hasTab(hash)) {
        window.tabManager.switchTo(hash);
    }
});

// Initialize tab manager when DOM is ready
document.addEventListener('DOMContentLoaded', () => {
    // Wait a bit for other components to initialize
    setTimeout(() => {
        window.tabManager.initializeFromUrl();
    }, 100);
});

// Export for module systems if needed
if (typeof module !== 'undefined' && module.exports) {
    module.exports = { TabManager, switchTab };
}