// Global state
let apps = [];
let autoCheckInterval = null;

// Initialize on page load
document.addEventListener('DOMContentLoaded', () => {
    loadApps();
    setupEventListeners();
    startAutoCheck();
});

// Setup event listeners
function setupEventListeners() {
    // Refresh button
    document.getElementById('refresh-btn').addEventListener('click', loadApps);

    // Add app button and modal
    document.getElementById('add-app-btn').addEventListener('click', () => {
        showModal('add-app-modal');
    });

    document.getElementById('cancel-add-btn').addEventListener('click', () => {
        hideModal('add-app-modal');
    });

    document.getElementById('add-app-form').addEventListener('submit', handleAddApp);

    // Edit workspace modal
    document.getElementById('cancel-edit-btn').addEventListener('click', () => {
        hideModal('edit-workspace-modal');
    });

    document.getElementById('edit-workspace-form').addEventListener('submit', handleEditWorkspace);

    // Logs modal
    document.getElementById('close-logs-btn').addEventListener('click', () => {
        hideModal('logs-modal');
    });

    // Close modals on X click
    document.querySelectorAll('.modal .close').forEach(closeBtn => {
        closeBtn.addEventListener('click', (e) => {
            const modal = e.target.closest('.modal');
            hideModal(modal.id);
        });
    });

    // Close modals on outside click
    document.querySelectorAll('.modal').forEach(modal => {
        modal.addEventListener('click', (e) => {
            if (e.target === modal) {
                hideModal(modal.id);
            }
        });
    });

    // Close all dropdowns when clicking outside
    document.addEventListener('click', (e) => {
        if (!e.target.closest('.more-menu-wrapper')) {
            document.querySelectorAll('.more-menu-dropdown.open').forEach(d => d.classList.remove('open'));
        }
    });

    // Action buttons inside app cards (event delegation)
    const appsContainer = document.getElementById('apps-container');
    appsContainer.addEventListener('click', (e) => {
        const src = (e.target instanceof Element) ? e.target : null;
        if (!src) return;

        const actionBtn = src.closest('[data-action]');
        if (!actionBtn) return;

        const action = actionBtn.getAttribute('data-action');
        const appId = actionBtn.getAttribute('data-app-id');
        if (!action || !appId) return;

        if (action === 'launch') {
            e.preventDefault();
            e.stopPropagation();
            console.log('[Launcher] Launch clicked:', appId);
            launchApp(appId);
        }
    });
}

// Load applications
async function loadApps() {
    try {
        const response = await fetch('/api/apps');
        const data = await response.json();
        apps = data.apps;
        renderApps();
    } catch (error) {
        console.error('Error loading apps:', error);
        showToast('Failed to load applications', 'error');
    }
}

// Render applications
function renderApps() {
    const container = document.getElementById('apps-container');

    if (apps.length === 0) {
        container.innerHTML = '<div class="loading">No applications configured. Click "Add App" to get started.</div>';
        return;
    }

    const appsGrid = document.createElement('div');
    appsGrid.className = 'apps-grid';

    apps.forEach(app => {
        const card = createAppCard(app);
        appsGrid.appendChild(card);
    });

    container.innerHTML = '';
    container.appendChild(appsGrid);
}

// Create app card
function createAppCard(app) {
    const card = document.createElement('div');
    card.className = 'app-card';

    const statusClass = `status-${app.status.toLowerCase()}`;
    const isStarting = app.status === 'Starting';
    const isStopped = app.status === 'Stopped';

    card.innerHTML = `
        <div class="app-header">
            <div class="app-title">
                <h3>${escapeHtml(app.name)}</h3>
                <div class="app-id">${escapeHtml(app.id)}</div>
            </div>
            <div class="app-header-right">
                <span class="status-badge ${statusClass}">${app.status}</span>
                <div class="more-menu-wrapper">
                    <button class="btn-more" onclick="toggleMoreMenu('more-${escapeHtml(app.id)}')" title="More options">⋯</button>
                    <div class="more-menu-dropdown" id="more-${escapeHtml(app.id)}">
                        <button class="more-menu-item" onclick="editWorkspace('${app.id}', '${escapeHtml(app.workspace)}'); closeMoreMenu('more-${escapeHtml(app.id)}')">
                            ✏️ Edit Workspace
                        </button>
                        <button class="more-menu-item more-menu-danger" onclick="deleteApp('${app.id}', '${escapeHtml(app.name)}'); closeMoreMenu('more-${escapeHtml(app.id)}')">
                            🗑️ Delete
                        </button>
                    </div>
                </div>
            </div>
        </div>

        <div class="app-info">
            <div class="info-row">
                <span class="info-label">Workspace:</span>
                <span class="info-value workspace">${escapeHtml(app.workspace)}</span>
            </div>
            ${app.message ? `
            <div class="info-row">
                <span class="info-label">Status:</span>
                <span class="info-value message">${escapeHtml(app.message)}</span>
            </div>
            ` : ''}
            ${app.ports.length > 0 ? `
            <div class="info-row">
                <span class="info-label">Ports:</span>
                <div class="info-value">
                    <div class="ports">
                        ${app.ports.map(port => `<span class="port-tag">${port}</span>`).join('')}
                    </div>
                </div>
            </div>
            ` : ''}
            ${app.last_check ? `
            <div class="info-row">
                <span class="info-label">Last Check:</span>
                <span class="info-value">${formatDateTime(app.last_check)}</span>
            </div>
            ` : ''}
        </div>

        <div class="app-actions">
            <button class="btn btn-success" data-action="launch" data-app-id="${escapeHtml(app.id)}" ${isStarting ? 'disabled' : ''}>
                🚀 Launch
            </button>
            <button class="btn btn-danger" onclick="stopApp('${app.id}')" ${isStopped ? 'disabled' : ''}>
                ⏹ Stop
            </button>
            <button class="btn btn-info" onclick="showLogs('${app.id}', '${escapeHtml(app.name)}')">
                📋 Logs
            </button>
        </div>
    `;

    return card;
}

// Toggle more menu dropdown
function toggleMoreMenu(menuId) {
    const menu = document.getElementById(menuId);
    if (!menu) return;
    // Close all other open menus first
    document.querySelectorAll('.more-menu-dropdown.open').forEach(d => {
        if (d.id !== menuId) d.classList.remove('open');
    });
    menu.classList.toggle('open');
}

function closeMoreMenu(menuId) {
    const menu = document.getElementById(menuId);
    if (menu) menu.classList.remove('open');
}

// Launch app (health check → start if needed → open URLs)
async function launchApp(appId) {
    console.log('[Launcher] Sending launch request:', appId);
    // Open placeholder tabs immediately on user click to avoid popup blocking
    // (window.open after async await is often blocked by browsers).
    const app = apps.find(a => a.id === appId);
    const expectedTabs = Math.max(1, Array.isArray(app?.open_urls) ? app.open_urls.length : 0);
    const preOpenedTabs = [];
    let blockedCount = 0;

    const writeLaunchingPage = (tab, appName) => {
        try {
            if (!tab || tab.closed) return;
            tab.document.open();
            tab.document.write(`<!doctype html><html><head><meta charset="utf-8"><title>Launching ${escapeHtml(appName || appId)}...</title></head><body style="font-family:system-ui,Segoe UI,Arial,sans-serif;padding:24px;line-height:1.6"><h2>Launching ${escapeHtml(appName || appId)}...</h2><p>Please wait while health check/startup completes.</p><p>If this screen does not change, check <b>Logs</b> in Nexus Web Launcher.</p></body></html>`);
            tab.document.close();
        } catch (_) {
            // Ignore cross-window write errors.
        }
    };

    for (let i = 0; i < expectedTabs; i++) {
        const w = window.open('about:blank', '_blank');
        if (w) {
            writeLaunchingPage(w, app?.name);
            preOpenedTabs.push(w);
        } else {
            blockedCount += 1;
        }
    }

    showToast('Launching... waiting for health check/startup', 'info');

    try {
        const response = await fetch('/api/apps/launch', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ app_id: appId })
        });

        const result = await response.json();

        if (result.status === 'success') {
            showToast(result.message, 'success');
            const targetUrls = (result.open_urls && Array.isArray(result.open_urls) && result.open_urls.length > 0)
                ? result.open_urls
                : (Array.isArray(app?.open_urls) ? app.open_urls : []);

            if (targetUrls.length > 0) {
                targetUrls.forEach((url, index) => {
                    const tab = preOpenedTabs[index];
                    if (tab && !tab.closed) {
                        tab.location.href = url;
                    } else {
                        const newTab = window.open(url, '_blank');
                        if (!newTab) blockedCount += 1;
                    }
                });

                // Close any extra placeholder tabs
                if (preOpenedTabs.length > targetUrls.length) {
                    preOpenedTabs.slice(targetUrls.length).forEach(tab => {
                        try { if (tab && !tab.closed) tab.close(); } catch (_) { /* ignore */ }
                    });
                }

                if (blockedCount > 0) {
                    showToast('Popup was blocked by browser. Please allow popups for this site.', 'error');
                }
            } else {
                showToast('Launch succeeded, but no open URL is configured.', 'error');
            }
        } else {
            preOpenedTabs.forEach(tab => {
                try { if (tab && !tab.closed) tab.close(); } catch (_) { /* ignore */ }
            });
            showToast(result.message, 'error');
        }

        loadApps();
    } catch (error) {
        preOpenedTabs.forEach(tab => {
            try { if (tab && !tab.closed) tab.close(); } catch (_) { /* ignore */ }
        });
        console.error('Error launching app:', error);
        showToast('Failed to launch application', 'error');
    }
}

// Stop app
async function stopApp(appId) {
    try {
        const response = await fetch('/api/apps/stop', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ app_id: appId })
        });

        const result = await response.json();

        if (result.status === 'success') {
            showToast(result.message, 'success');
        } else {
            showToast(result.message, 'error');
        }

        loadApps();
    } catch (error) {
        console.error('Error stopping app:', error);
        showToast('Failed to stop application', 'error');
    }
}

// Edit workspace
function editWorkspace(appId, currentWorkspace) {
    document.getElementById('edit-app-id').value = appId;
    document.getElementById('edit-workspace').value = currentWorkspace;
    showModal('edit-workspace-modal');
}

// Handle edit workspace
async function handleEditWorkspace(e) {
    e.preventDefault();

    const appId = document.getElementById('edit-app-id').value;
    const workspace = document.getElementById('edit-workspace').value;

    try {
        const response = await fetch('/api/apps/update-workspace', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                app_id: appId,
                workspace: workspace
            })
        });

        const result = await response.json();

        if (result.status === 'success') {
            showToast(result.message, 'success');
            hideModal('edit-workspace-modal');
            loadApps();
        } else {
            showToast(result.message, 'error');
        }
    } catch (error) {
        console.error('Error updating workspace:', error);
        showToast('Failed to update workspace', 'error');
    }
}

// Show logs
async function showLogs(appId, appName) {
    document.getElementById('logs-app-name').textContent = appName;
    document.getElementById('logs-content').textContent = 'Loading logs...';
    showModal('logs-modal');

    try {
        const response = await fetch(`/api/apps/${appId}/logs`);
        const data = await response.json();
        const logsEl = document.getElementById('logs-content');
        logsEl.textContent = data.logs || '(No logs yet)';
        // Scroll to bottom
        logsEl.scrollTop = logsEl.scrollHeight;
    } catch (error) {
        console.error('Error loading logs:', error);
        document.getElementById('logs-content').textContent = 'Error loading logs: ' + error.message;
    }
}

// Delete app
async function deleteApp(appId, appName) {
    if (!confirm(`Are you sure you want to delete "${appName}"?`)) {
        return;
    }

    try {
        const response = await fetch(`/api/apps/${appId}`, {
            method: 'DELETE'
        });

        const result = await response.json();

        if (result.status === 'success') {
            showToast(result.message, 'success');
            loadApps();
        } else {
            showToast(result.message, 'error');
        }
    } catch (error) {
        console.error('Error deleting app:', error);
        showToast('Failed to delete application', 'error');
    }
}

// Handle add app
async function handleAddApp(e) {
    e.preventDefault();

    const id = document.getElementById('app-id').value.trim();
    const name = document.getElementById('app-name').value.trim();
    const workspace = document.getElementById('app-workspace').value.trim();
    const portsStr = document.getElementById('app-ports').value.trim();
    const healthUrl = document.getElementById('app-health-url').value.trim();
    const healthTimeout = parseInt(document.getElementById('app-health-timeout').value);
    const openUrlsStr = document.getElementById('app-open-urls').value.trim();
    const startCmd = document.getElementById('app-start-cmd').value.trim();
    const startShell = document.getElementById('app-start-shell').value;

    // Parse ports
    const ports = portsStr ? portsStr.split(',').map(p => parseInt(p.trim())).filter(p => !isNaN(p)) : [];

    // Parse open URLs
    const openUrls = openUrlsStr.split('\n').map(u => u.trim()).filter(u => u);

    // Build request
    const request = {
        id: id,
        name: name,
        workspace: workspace,
        ports: ports,
        start_commands: [{
            cmd: startCmd,
            shell: startShell,
            cwd: '{workspace}'
        }],
        health_checks: [{
            url: healthUrl,
            timeout_sec: healthTimeout
        }],
        open_urls: openUrls
    };

    try {
        const response = await fetch('/api/apps/add', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(request)
        });

        if (response.ok) {
            const result = await response.json();
            showToast(result.message, 'success');
            hideModal('add-app-modal');
            document.getElementById('add-app-form').reset();
            loadApps();
        } else {
            const error = await response.json();
            showToast(error.detail || 'Failed to add application', 'error');
        }
    } catch (error) {
        console.error('Error adding app:', error);
        showToast('Failed to add application', 'error');
    }
}

// Auto-check (refresh states every 10 seconds)
function startAutoCheck() {
    if (autoCheckInterval) {
        clearInterval(autoCheckInterval);
    }

    autoCheckInterval = setInterval(() => {
        loadApps();
    }, 10000);
}

// Modal functions
function showModal(modalId) {
    document.getElementById(modalId).classList.add('show');
}

function hideModal(modalId) {
    document.getElementById(modalId).classList.remove('show');
}

// Utility functions
function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

function formatDateTime(isoString) {
    try {
        const date = new Date(isoString);
        return date.toLocaleString();
    } catch {
        return isoString;
    }
}

// Toast notification
function showToast(message, type = 'info') {
    const container = document.getElementById('toast-container');
    const toast = document.createElement('div');
    toast.className = `toast toast-${type}`;

    const icon = type === 'success' ? '✅' : type === 'error' ? '❌' : 'ℹ️';
    toast.textContent = `${icon} ${message}`;

    container.appendChild(toast);

    // Trigger animation
    requestAnimationFrame(() => {
        toast.classList.add('show');
    });

    // Auto-remove after 3.5 seconds
    setTimeout(() => {
        toast.classList.remove('show');
        setTimeout(() => toast.remove(), 400);
    }, 3500);
}

// Keep inline onclick handlers working when this file is loaded as an ES module.
window.launchApp = launchApp;
window.stopApp = stopApp;
window.editWorkspace = editWorkspace;
window.showLogs = showLogs;
window.deleteApp = deleteApp;
window.toggleMoreMenu = toggleMoreMenu;
window.closeMoreMenu = closeMoreMenu;
