/**
 * Design Downloader - Chrome Extension Popup
 * Cyberpunk Neon Theme
 */

// ═══════════════════════════════════════════════════════════════
// CONFIGURATION
// ═══════════════════════════════════════════════════════════════

const DEFAULT_SERVER_URL = 'http://localhost:5200';
let serverUrl = DEFAULT_SERVER_URL;

// Platform detection patterns
const PLATFORMS = {
  behance: {
    pattern: /behance\.net\/gallery\/(\d+)/i,
    icon: 'B',
    name: 'Behance',
    color: '#1769ff'
  },
  dribbble: {
    pattern: /dribbble\.com\/shots\/(\d+)/i,
    icon: 'D',
    name: 'Dribbble',
    color: '#ea4c89'
  },
  pinterest: {
    pattern: /pinterest\.(com|co\.\w+)\/(pin\/\d+|[^\/]+\/[^\/]+)/i,
    icon: 'P',
    name: 'Pinterest',
    color: '#e60023'
  }
};

// ═══════════════════════════════════════════════════════════════
// DOM ELEMENTS
// ═══════════════════════════════════════════════════════════════

const elements = {
  serverStatus: document.getElementById('serverStatus'),
  urlInput: document.getElementById('urlInput'),
  pasteBtn: document.getElementById('pasteBtn'),
  platformDetect: document.getElementById('platformDetect'),
  downloadBtn: document.getElementById('downloadBtn'),
  currentPageBtn: document.getElementById('currentPageBtn'),
  queueList: document.getElementById('queueList'),
  queueCount: document.getElementById('queueCount'),
  settingsBtn: document.getElementById('settingsBtn'),
  clearBtn: document.getElementById('clearBtn'),
  settingsPanel: document.getElementById('settingsPanel'),
  closeSettings: document.getElementById('closeSettings'),
  downloadFolder: document.getElementById('downloadFolder'),
  serverUrlInput: document.getElementById('serverUrl'),
  saveFolderBtn: document.getElementById('saveFolderBtn'),
  toastContainer: document.getElementById('toastContainer'),
  // Folder elements
  folderSelect: document.getElementById('folderSelect'),
  addFolderBtn: document.getElementById('addFolderBtn'),
  folderModal: document.getElementById('folderModal'),
  closeFolderModal: document.getElementById('closeFolderModal'),
  modalFolderName: document.getElementById('modalFolderName'),
  cancelFolderBtn: document.getElementById('cancelFolderBtn'),
  confirmFolderBtn: document.getElementById('confirmFolderBtn'),
  foldersList: document.getElementById('foldersList'),
  newFolderInput: document.getElementById('newFolderInput'),
  createFolderBtn: document.getElementById('createFolderBtn'),
  // Accordion
  bulkContent: document.getElementById('bulkContent'),
  // Bulk downloader
  freeBadge: document.getElementById('freeBadge'),
  usageInfo: document.getElementById('usageInfo'),
  usageFill: document.getElementById('usageFill'),
  usageText: document.getElementById('usageText'),
  bulkInputSection: document.getElementById('bulkInputSection'),
  bulkUrls: document.getElementById('bulkUrls'),
  bulkStartBtn: document.getElementById('bulkStartBtn'),
  // PRO section
  proSection: document.getElementById('proSection'),
  upgradeBtn: document.getElementById('upgradeBtn')
};

// ═══════════════════════════════════════════════════════════════
// STATE
// ═══════════════════════════════════════════════════════════════

let downloads = [];
let folders = [];
let statusCheckInterval = null;
let bulkUsageRemaining = 1; // 1 free bulk download

// ═══════════════════════════════════════════════════════════════
// API FUNCTIONS
// ═══════════════════════════════════════════════════════════════

async function checkServerStatus() {
  try {
    const response = await fetch(`${serverUrl}/api/status`, {
      method: 'GET',
      headers: { 'Content-Type': 'application/json' }
    });

    if (response.ok) {
      elements.serverStatus.classList.add('online');
      elements.serverStatus.title = 'Server Online';
      return true;
    }
  } catch (error) {
    console.log('Server offline:', error);
  }

  elements.serverStatus.classList.remove('online');
  elements.serverStatus.title = 'Server Offline';
  return false;
}

async function addDownload(url, folderName = '') {
  try {
    const response = await fetch(`${serverUrl}/api/download`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        url,
        folder_name: folderName,
        download_folder: elements.downloadFolder.value || undefined
      })
    });

    if (response.ok) {
      const data = await response.json();
      showToast('success', `Added: ${data.message || 'Download queued'}`);
      refreshDownloads();
      return data;
    } else {
      const error = await response.json();
      showToast('error', error.error || 'Failed to add download');
    }
  } catch (error) {
    showToast('error', 'Server connection failed');
    console.error('Download error:', error);
  }
  return null;
}

async function fetchDownloads() {
  try {
    const response = await fetch(`${serverUrl}/api/downloads`, {
      method: 'GET',
      headers: { 'Content-Type': 'application/json' }
    });

    if (response.ok) {
      downloads = await response.json();
      renderQueue();
    }
  } catch (error) {
    console.error('Fetch downloads error:', error);
  }
}

async function clearCompleted() {
  try {
    const response = await fetch(`${serverUrl}/api/clear`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' }
    });

    if (response.ok) {
      const data = await response.json();
      showToast('info', `Cleared ${data.cleared} items`);
      refreshDownloads();
    }
  } catch (error) {
    console.error('Clear error:', error);
  }
}

async function updateSettings() {
  try {
    const response = await fetch(`${serverUrl}/api/settings`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        download_folder: elements.downloadFolder.value
      })
    });

    if (response.ok) {
      showToast('success', 'Settings saved');
    }
  } catch (error) {
    showToast('error', 'Failed to save settings');
  }
}

async function loadSettings() {
  try {
    const response = await fetch(`${serverUrl}/api/settings`, {
      method: 'GET',
      headers: { 'Content-Type': 'application/json' }
    });

    if (response.ok) {
      const data = await response.json();
      if (data.download_folder) {
        elements.downloadFolder.value = data.download_folder;
      }
    }
  } catch (error) {
    console.log('Could not load settings');
  }
}

// ═══════════════════════════════════════════════════════════════
// FOLDER MANAGEMENT
// ═══════════════════════════════════════════════════════════════

async function loadFolders() {
  const stored = await chrome.storage.local.get(['folders']);
  folders = stored.folders || [];
  renderFolderSelect();
  renderFoldersList();
}

async function saveFolders() {
  await chrome.storage.local.set({ folders });
  renderFolderSelect();
  renderFoldersList();
}

function addFolder(name) {
  if (!name || folders.includes(name)) return false;
  folders.push(name);
  saveFolders();
  return true;
}

function removeFolder(name) {
  folders = folders.filter(f => f !== name);
  saveFolders();
}

// ═══════════════════════════════════════════════════════════════
// BULK DOWNLOAD MANAGEMENT
// ═══════════════════════════════════════════════════════════════

async function loadBulkUsage() {
  const stored = await chrome.storage.local.get(['bulkUsageRemaining']);
  bulkUsageRemaining = stored.bulkUsageRemaining ?? 1;
  updateBulkUI();
}

async function saveBulkUsage() {
  await chrome.storage.local.set({ bulkUsageRemaining });
  updateBulkUI();
}

function updateBulkUI() {
  const hasUsage = bulkUsageRemaining > 0;

  // Update badge
  if (elements.freeBadge) {
    if (hasUsage) {
      elements.freeBadge.textContent = '1 FREE';
      elements.freeBadge.classList.remove('used');
    } else {
      elements.freeBadge.textContent = 'PRO';
      elements.freeBadge.classList.add('used');
    }
  }

  // Update usage info
  if (elements.usageInfo) {
    if (hasUsage) {
      elements.usageInfo.classList.remove('depleted');
    } else {
      elements.usageInfo.classList.add('depleted');
    }
  }

  // Update usage bar
  if (elements.usageFill) {
    elements.usageFill.style.width = hasUsage ? '100%' : '0%';
  }

  // Update usage text
  if (elements.usageText) {
    elements.usageText.textContent = hasUsage
      ? '1 free bulk download remaining'
      : 'Free bulk download used';
  }

  // Show/hide sections
  if (elements.bulkInputSection && elements.proSection) {
    if (hasUsage) {
      elements.bulkInputSection.classList.remove('hidden');
      elements.proSection.classList.add('hidden');
    } else {
      elements.bulkInputSection.classList.add('hidden');
      elements.proSection.classList.remove('hidden');
    }
  }
}

async function handleBulkDownload() {
  if (bulkUsageRemaining <= 0) {
    showToast('info', 'Upgrade to PRO for unlimited bulk downloads');
    return;
  }

  const urlsText = elements.bulkUrls.value.trim();
  if (!urlsText) {
    showToast('error', 'Please enter URLs');
    return;
  }

  // Parse URLs (one per line)
  const urls = urlsText
    .split('\n')
    .map(url => url.trim())
    .filter(url => url && detectPlatformLocally(url));

  if (urls.length === 0) {
    showToast('error', 'No valid URLs found');
    return;
  }

  // Disable button during processing
  elements.bulkStartBtn.disabled = true;
  showToast('info', `Processing ${urls.length} URLs...`);

  const selectedFolder = elements.folderSelect.value;
  let successCount = 0;

  // Add each URL to the download queue
  for (const url of urls) {
    try {
      const result = await addDownload(url, selectedFolder);
      if (result) successCount++;
    } catch (error) {
      console.error('Bulk download error:', error);
    }
  }

  // Use up the free bulk download
  bulkUsageRemaining = 0;
  await saveBulkUsage();

  // Clear textarea and re-enable button
  elements.bulkUrls.value = '';
  elements.bulkStartBtn.disabled = false;

  showToast('success', `Added ${successCount}/${urls.length} downloads`);
}

function renderFolderSelect() {
  elements.folderSelect.innerHTML = '<option value="">Default folder</option>';
  folders.forEach(folder => {
    const option = document.createElement('option');
    option.value = folder;
    option.textContent = folder;
    elements.folderSelect.appendChild(option);
  });
}

function renderFoldersList() {
  if (!folders.length) {
    elements.foldersList.innerHTML = '<div style="color: var(--text-dim); font-size: 9px; padding: 8px;">No custom folders</div>';
    return;
  }

  elements.foldersList.innerHTML = folders.map(folder => `
    <div class="folder-item">
      <span class="folder-item-name">${folder}</span>
      <button class="folder-item-delete" data-folder="${folder}">
        <svg viewBox="0 0 24 24" fill="none" width="12" height="12">
          <path d="M18 6L6 18M6 6L18 18" stroke="currentColor" stroke-width="2" stroke-linecap="round"/>
        </svg>
      </button>
    </div>
  `).join('');

  // Add delete handlers
  elements.foldersList.querySelectorAll('.folder-item-delete').forEach(btn => {
    btn.addEventListener('click', () => {
      removeFolder(btn.dataset.folder);
    });
  });
}

// ═══════════════════════════════════════════════════════════════
// UI FUNCTIONS
// ═══════════════════════════════════════════════════════════════

function detectPlatformLocally(url) {
  for (const [key, platform] of Object.entries(PLATFORMS)) {
    if (platform.pattern.test(url)) {
      return { key, ...platform };
    }
  }
  return null;
}

function updatePlatformDisplay(url) {
  const platform = detectPlatformLocally(url);
  const platformIcon = elements.platformDetect.querySelector('.platform-icon');
  const platformName = elements.platformDetect.querySelector('.platform-name');

  elements.platformDetect.className = 'platform-detect';

  if (platform) {
    elements.platformDetect.classList.add(platform.key);
    platformIcon.textContent = platform.icon;
    platformIcon.style.background = platform.color;
    platformIcon.style.color = '#fff';
    platformName.textContent = platform.name + ' detected';
  } else {
    platformIcon.textContent = '';
    platformIcon.style.background = '';
    platformName.textContent = url ? 'Unknown platform' : 'Auto-detect platform';
  }
}

function renderQueue() {
  elements.queueCount.textContent = downloads.length;

  if (downloads.length === 0) {
    elements.queueList.innerHTML = `
      <div class="queue-empty">
        <svg viewBox="0 0 24 24" fill="none">
          <path d="M20 7L12 3L4 7M20 7L12 11M20 7V17L12 21M12 11L4 7M12 11V21M4 7V17L12 21" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/>
        </svg>
        <span>No downloads in queue</span>
      </div>
    `;
    return;
  }

  const html = downloads.map(item => {
    const platform = detectPlatformLocally(item.url);
    const platformKey = platform?.key || 'unknown';
    const platformIcon = platform?.icon || '?';

    let statusClass = '';
    let statusText = item.status;

    switch (item.status) {
      case 'scanning':
        statusClass = 'scanning';
        statusText = 'Scanning...';
        break;
      case 'downloading':
        statusClass = 'downloading';
        statusText = `Downloading ${item.images_downloaded}/${item.images_found}`;
        break;
      case 'completed':
        statusClass = 'completed';
        statusText = `Done (${item.images_downloaded} images)`;
        break;
      case 'error':
        statusClass = 'error';
        statusText = item.error || 'Error';
        break;
      case 'queued':
        statusText = 'Queued';
        break;
    }

    return `
      <div class="queue-item" data-id="${item.id}">
        <div class="queue-item-icon ${platformKey}">${platformIcon}</div>
        <div class="queue-item-info">
          <div class="queue-item-name">${item.name || 'Unknown'}</div>
          <div class="queue-item-status ${statusClass}">${statusText}</div>
          ${item.progress > 0 && item.status !== 'completed' ? `
            <div class="queue-item-progress">
              <div class="queue-item-progress-bar" style="width: ${item.progress}%"></div>
            </div>
          ` : ''}
        </div>
      </div>
    `;
  }).join('');

  elements.queueList.innerHTML = html;
}

function showToast(type, message) {
  const icons = {
    success: '<svg viewBox="0 0 24 24" fill="none"><path d="M20 6L9 17L4 12" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/></svg>',
    error: '<svg viewBox="0 0 24 24" fill="none"><circle cx="12" cy="12" r="10" stroke="currentColor" stroke-width="2"/><path d="M15 9L9 15M9 9L15 15" stroke="currentColor" stroke-width="2" stroke-linecap="round"/></svg>',
    info: '<svg viewBox="0 0 24 24" fill="none"><circle cx="12" cy="12" r="10" stroke="currentColor" stroke-width="2"/><path d="M12 16V12M12 8H12.01" stroke="currentColor" stroke-width="2" stroke-linecap="round"/></svg>'
  };

  const toast = document.createElement('div');
  toast.className = `toast ${type}`;
  toast.innerHTML = `
    <span class="toast-icon">${icons[type]}</span>
    <span class="toast-message">${message}</span>
  `;

  elements.toastContainer.appendChild(toast);

  setTimeout(() => {
    toast.classList.add('removing');
    setTimeout(() => toast.remove(), 300);
  }, 3000);
}

function refreshDownloads() {
  fetchDownloads();
}

// ═══════════════════════════════════════════════════════════════
// ACCORDION FUNCTIONALITY
// ═══════════════════════════════════════════════════════════════

function initAccordions() {
  document.querySelectorAll('.accordion-header').forEach(header => {
    header.addEventListener('click', () => {
      const item = header.closest('.accordion-item');
      const isOpen = item.classList.contains('open');

      // Close all accordions
      document.querySelectorAll('.accordion-item').forEach(acc => {
        acc.classList.remove('open');
      });

      // Open clicked one if it was closed
      if (!isOpen) {
        item.classList.add('open');
      }
    });
  });
}

// ═══════════════════════════════════════════════════════════════
// EVENT HANDLERS
// ═══════════════════════════════════════════════════════════════

// URL Input
elements.urlInput.addEventListener('input', (e) => {
  updatePlatformDisplay(e.target.value);
});

elements.urlInput.addEventListener('keypress', (e) => {
  if (e.key === 'Enter') {
    handleDownload();
  }
});

// Paste button
elements.pasteBtn.addEventListener('click', async () => {
  try {
    const text = await navigator.clipboard.readText();
    elements.urlInput.value = text;
    updatePlatformDisplay(text);
  } catch (error) {
    showToast('error', 'Could not access clipboard');
  }
});

// Download button
elements.downloadBtn.addEventListener('click', handleDownload);

async function handleDownload() {
  const url = elements.urlInput.value.trim();
  if (!url) {
    showToast('error', 'Please enter a URL');
    return;
  }

  const platform = detectPlatformLocally(url);
  if (!platform) {
    showToast('error', 'Unsupported platform');
    return;
  }

  const selectedFolder = elements.folderSelect.value;
  const result = await addDownload(url, selectedFolder);
  if (result) {
    elements.urlInput.value = '';
    updatePlatformDisplay('');
  }
}

// Current page button
elements.currentPageBtn.addEventListener('click', async () => {
  try {
    const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
    if (tab?.url) {
      elements.urlInput.value = tab.url;
      updatePlatformDisplay(tab.url);
    }
  } catch (error) {
    showToast('error', 'Could not get current page URL');
  }
});

// Settings
elements.settingsBtn.addEventListener('click', () => {
  elements.settingsPanel.classList.add('open');
});

elements.closeSettings.addEventListener('click', () => {
  elements.settingsPanel.classList.remove('open');
});

elements.saveFolderBtn.addEventListener('click', () => {
  updateSettings();
});

elements.serverUrlInput.addEventListener('change', (e) => {
  serverUrl = e.target.value || DEFAULT_SERVER_URL;
  chrome.storage.local.set({ serverUrl });
  checkServerStatus();
});

// Clear button
elements.clearBtn.addEventListener('click', () => {
  clearCompleted();
});

// Folder modal
elements.addFolderBtn.addEventListener('click', () => {
  elements.folderModal.classList.add('open');
  elements.modalFolderName.value = '';
  elements.modalFolderName.focus();
});

elements.closeFolderModal.addEventListener('click', () => {
  elements.folderModal.classList.remove('open');
});

elements.cancelFolderBtn.addEventListener('click', () => {
  elements.folderModal.classList.remove('open');
});

elements.confirmFolderBtn.addEventListener('click', () => {
  const name = elements.modalFolderName.value.trim();
  if (name) {
    if (addFolder(name)) {
      showToast('success', `Folder "${name}" created`);
      elements.folderModal.classList.remove('open');
    } else {
      showToast('error', 'Folder already exists');
    }
  }
});

elements.modalFolderName.addEventListener('keypress', (e) => {
  if (e.key === 'Enter') {
    elements.confirmFolderBtn.click();
  }
});

// Settings folder management
elements.createFolderBtn.addEventListener('click', () => {
  const name = elements.newFolderInput.value.trim();
  if (name) {
    if (addFolder(name)) {
      showToast('success', `Folder "${name}" created`);
      elements.newFolderInput.value = '';
    } else {
      showToast('error', 'Folder already exists');
    }
  }
});

// Bulk download
elements.bulkStartBtn.addEventListener('click', () => {
  handleBulkDownload();
});

// Premium upgrade
elements.upgradeBtn.addEventListener('click', () => {
  showToast('info', 'PRO upgrade coming soon!');
});

// ═══════════════════════════════════════════════════════════════
// INITIALIZATION
// ═══════════════════════════════════════════════════════════════

async function init() {
  // Load saved server URL
  const stored = await chrome.storage.local.get(['serverUrl']);
  if (stored.serverUrl) {
    serverUrl = stored.serverUrl;
    elements.serverUrlInput.value = serverUrl;
  }

  // Initialize accordions
  initAccordions();

  // Load folders
  await loadFolders();

  // Load bulk usage
  await loadBulkUsage();

  // Check server status
  await checkServerStatus();
  await loadSettings();
  await fetchDownloads();

  // Start polling for updates
  statusCheckInterval = setInterval(async () => {
    await checkServerStatus();
    await fetchDownloads();
  }, 2000);

  // Try to get current tab URL
  try {
    const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
    if (tab?.url) {
      const platform = detectPlatformLocally(tab.url);
      if (platform) {
        elements.urlInput.value = tab.url;
        updatePlatformDisplay(tab.url);
      }
    }
  } catch (error) {
    console.log('Could not get current tab');
  }
}

// Cleanup on close
window.addEventListener('unload', () => {
  if (statusCheckInterval) {
    clearInterval(statusCheckInterval);
  }
});

// Initialize
init();
