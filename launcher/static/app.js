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
        showError('Failed to load applications');
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

    card.innerHTML = `
        <div class="app-header">
            <div class="app-title">
                <h3>${escapeHtml(app.name)}</h3>
                <div class="app-id">${escapeHtml(app.id)}</div>
            </div>
            <span class="status-badge ${statusClass}">${app.status}</span>
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
            <button class="btn btn-primary" onclick="openApp('${app.id}')" ${app.open_urls && app.open_urls.length > 0 ? '' : 'disabled'}>
                🌐 Open
            </button>
            <button class="btn btn-success" onclick="launchApp('${app.id}')" ${app.status === 'Starting' ? 'disabled' : ''}>
                🚀 Launch
            </button>
            <button class="btn btn-danger" onclick="stopApp('${app.id}')" ${app.status === 'Stopped' ? 'disabled' : ''}>
                ⏹️ Stop
            </button>
            <button class="btn btn-warning" onclick="editWorkspace('${app.id}', '${escapeHtml(app.workspace)}')">
                ✏️ Edit
            </button>
            <button class="btn btn-info" onclick="showLogs('${app.id}', '${escapeHtml(app.name)}')">
                📋 Logs
            </button>
            <button class="btn btn-secondary" onclick="deleteApp('${app.id}', '${escapeHtml(app.name)}')">
                🗑️ Delete
            </button>
        </div>
    `;

    return card;
}

// Open app URLs
function openApp(appId) {
    const app = apps.find(a => a.id === appId);
    if (app && app.open_urls) {
        app.open_urls.forEach(url => {
            window.open(url, '_blank');
        });
    }
}

// Launch app
async function launchApp(appId) {
    try {
        const response = await fetch('/api/apps/launch', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ app_id: appId })
        });

        const result = await response.json();

        if (result.status === 'success') {
            showSuccess(result.message);
            // Open URLs only after the backend confirmed the app is (or became) healthy.
            if (result.open_urls && Array.isArray(result.open_urls)) {
                result.open_urls.forEach(url => window.open(url, '_blank'));
            }
        } else {
            showError(result.message);
        }

        // Reload apps to update status
        loadApps();
    } catch (error) {
        console.error('Error launching app:', error);
        showError('Failed to launch application');
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
            showSuccess(result.message);
        } else {
            showError(result.message);
        }

        loadApps();
    } catch (error) {
        console.error('Error stopping app:', error);
        showError('Failed to stop application');
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
            showSuccess(result.message);
            hideModal('edit-workspace-modal');
            loadApps();
        } else {
            showError(result.message);
        }
    } catch (error) {
        console.error('Error updating workspace:', error);
        showError('Failed to update workspace');
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
        document.getElementById('logs-content').textContent = data.logs;
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
            showSuccess(result.message);
            loadApps();
        } else {
            showError(result.message);
        }
    } catch (error) {
        console.error('Error deleting app:', error);
        showError('Failed to delete application');
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
            showSuccess(result.message);
            hideModal('add-app-modal');
            document.getElementById('add-app-form').reset();
            loadApps();
        } else {
            const error = await response.json();
            showError(error.detail || 'Failed to add application');
        }
    } catch (error) {
        console.error('Error adding app:', error);
        showError('Failed to add application');
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

function showSuccess(message) {
    alert('✅ ' + message);
}

function showError(message) {
    alert('❌ ' + message);
}
