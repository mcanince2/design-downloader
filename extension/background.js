/**
 * Design Downloader - Background Service Worker
 * Handles context menu and background tasks
 */

const DEFAULT_SERVER_URL = 'http://localhost:5200';

// Platform detection patterns
const PLATFORMS = {
  behance: /behance\.net\/gallery\/(\d+)/i,
  dribbble: /dribbble\.com\/shots\/(\d+)/i,
  pinterest: /pinterest\.(com|co\.\w+)\/(pin\/\d+|[^\/]+\/[^\/]+)/i
};

// Create context menu on install
chrome.runtime.onInstalled.addListener(() => {
  chrome.contextMenus.create({
    id: 'downloadDesign',
    title: 'Download with Design Downloader',
    contexts: ['page', 'link'],
    documentUrlPatterns: [
      '*://*.behance.net/*',
      '*://*.dribbble.com/*',
      '*://*.pinterest.com/*',
      '*://*.pinterest.co.uk/*'
    ]
  });
});

// Handle context menu clicks
chrome.contextMenus.onClicked.addListener(async (info, tab) => {
  if (info.menuItemId === 'downloadDesign') {
    const url = info.linkUrl || info.pageUrl;

    if (url && isSupportedUrl(url)) {
      await addToDownload(url);
    }
  }
});

// Check if URL is supported
function isSupportedUrl(url) {
  return Object.values(PLATFORMS).some(pattern => pattern.test(url));
}

// Add URL to download queue
async function addToDownload(url) {
  const stored = await chrome.storage.local.get(['serverUrl']);
  const serverUrl = stored.serverUrl || DEFAULT_SERVER_URL;

  try {
    const response = await fetch(`${serverUrl}/api/download`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ url })
    });

    if (response.ok) {
      // Show notification
      chrome.notifications.create({
        type: 'basic',
        iconUrl: 'icons/icon128.png',
        title: 'Design Downloader',
        message: 'Download added to queue'
      });
    } else {
      chrome.notifications.create({
        type: 'basic',
        iconUrl: 'icons/icon128.png',
        title: 'Design Downloader',
        message: 'Failed to add download'
      });
    }
  } catch (error) {
    chrome.notifications.create({
      type: 'basic',
      iconUrl: 'icons/icon128.png',
      title: 'Design Downloader',
      message: 'Server not running'
    });
  }
}

// Listen for messages from popup
chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
  if (request.action === 'checkServer') {
    checkServerStatus().then(sendResponse);
    return true;
  }
});

async function checkServerStatus() {
  const stored = await chrome.storage.local.get(['serverUrl']);
  const serverUrl = stored.serverUrl || DEFAULT_SERVER_URL;

  try {
    const response = await fetch(`${serverUrl}/api/status`);
    return response.ok;
  } catch {
    return false;
  }
}
