/**
 * NexLoad — Social Video Downloader
 * script.js
 *
 * Handles:
 *  - URL input + platform detection
 *  - API call to POST /api/download
 *  - UI state management (idle / loading / success / error)
 *  - Resolution selection + download trigger
 *  - Responsive & accessible interactions
 */

'use strict';

/* ══════════════════════════════════════════════════
   CONSTANTS & CONFIG
══════════════════════════════════════════════════ */

const API_ENDPOINT = '/api/download';

/** Loading sub-text messages cycled during fetch */
const LOADING_MESSAGES = [
  'Connecting to platform API…',
  'Fetching video metadata…',
  'Processing resolutions…',
  'Almost there…',
];

/** Platform definitions — detection regex, icon classes, colors */
const PLATFORMS = {
  instagram: {
    name: 'Instagram',
    regex: /instagram\.com/i,
    iconCard: 'fa-brands fa-instagram',
    iconTag: 'fa-brands fa-instagram',
    cardClass: 'ig-mode',
    focusClass: 'ig-focus',
    tagClass: 'ig-tag',
    badgeColor: '#ff2d78',
    statusColor: 'var(--magenta)',
  },
  youtube: {
    name: 'YouTube',
    regex: /youtube\.com|youtu\.be/i,
    iconCard: 'fa-brands fa-youtube',
    iconTag: 'fa-brands fa-youtube',
    cardClass: 'yt-mode',
    focusClass: 'yt-focus',
    tagClass: 'yt-tag',
    badgeColor: '#ff0000',
    statusColor: '#ff4444',
  },
};

/** Resolutions in display order */
const RESOLUTION_LABELS = ['1080p', '720p', '480p', '360p'];

/* ══════════════════════════════════════════════════
   DOM REFERENCES
══════════════════════════════════════════════════ */

const urlInput         = document.getElementById('url-input');
const inputWrap        = document.getElementById('input-wrap');
const clearBtn         = document.getElementById('clear-btn');
const extractBtn       = document.getElementById('extract-btn');
const errorBanner      = document.getElementById('error-banner');
const errorText        = document.getElementById('error-text');
const loadingZone      = document.getElementById('loading-zone');
const loadingSub       = document.getElementById('loading-sub');
const resultSection    = document.getElementById('result-section');

// Card header
const platformIndicator = document.getElementById('platform-indicator');
const platformIcon      = document.getElementById('platform-icon');
const platformLabel     = document.getElementById('platform-label');
const statusDot         = document.getElementById('status-dot');
const statusText        = document.getElementById('status-text');

// Result elements
const resultThumbnail     = document.getElementById('result-thumbnail');
const resultTitle         = document.getElementById('result-title');
const resolutionSelect    = document.getElementById('resolution-select');
const downloadBtn         = document.getElementById('download-btn');
const resultPlatformBadge = document.getElementById('result-platform-badge');
const resultPlatformIcon  = document.getElementById('result-platform-icon');
const resultPlatformName  = document.getElementById('result-platform-name');
const videoPlatformTag    = document.getElementById('video-platform-tag');
const videoTagIcon        = document.getElementById('video-tag-icon');
const videoTagText        = document.getElementById('video-tag-text');

/* ══════════════════════════════════════════════════
   STATE
══════════════════════════════════════════════════ */

let state = {
  status: 'idle',         // idle | loading | success | error
  platform: null,         // null | 'instagram' | 'youtube'
  currentResolutions: {}, // { '360p': url, '720p': url, ... }
  loadingTimer: null,
  loadingMsgIndex: 0,
};

/* ══════════════════════════════════════════════════
   UTILITY FUNCTIONS
══════════════════════════════════════════════════ */

/**
 * Detect platform from URL string.
 * @param {string} url
 * @returns {'instagram'|'youtube'|null}
 */
function detectPlatform(url) {
  if (!url) return null;
  for (const [key, cfg] of Object.entries(PLATFORMS)) {
    if (cfg.regex.test(url)) return key;
  }
  return null;
}

/**
 * Validate that a string looks like a URL.
 * @param {string} url
 * @returns {boolean}
 */
function isValidUrl(url) {
  try {
    const u = new URL(url.trim());
    return u.protocol === 'http:' || u.protocol === 'https:';
  } catch {
    return false;
  }
}

/**
 * Cycle loading sub-text messages.
 */
function startLoadingMessages() {
  state.loadingMsgIndex = 0;
  loadingSub.textContent = LOADING_MESSAGES[0];
  state.loadingTimer = setInterval(() => {
    state.loadingMsgIndex = (state.loadingMsgIndex + 1) % LOADING_MESSAGES.length;
    loadingSub.textContent = LOADING_MESSAGES[state.loadingMsgIndex];
  }, 1800);
}

function stopLoadingMessages() {
  if (state.loadingTimer) {
    clearInterval(state.loadingTimer);
    state.loadingTimer = null;
  }
}

/* ══════════════════════════════════════════════════
   UI STATE MANAGEMENT
══════════════════════════════════════════════════ */

/**
 * Set the card to idle state.
 */
function setIdle() {
  state.status = 'idle';
  setStatus('idle', 'IDLE');
  extractBtn.disabled = false;
  hide(loadingZone);
  hide(errorBanner);
}

/**
 * Set the card to loading state.
 */
function setLoading() {
  state.status = 'loading';
  setStatus('active', 'PROCESSING');
  extractBtn.disabled = true;
  hide(errorBanner);
  hide(resultSection);
  show(loadingZone);
  startLoadingMessages();
}

/**
 * Set the card to success state, populating result data.
 * @param {object} data - API response
 */
function setSuccess(data) {
  state.status = 'success';
  stopLoadingMessages();
  hide(loadingZone);
  setStatus('success', 'READY');
  extractBtn.disabled = false;
  populateResult(data);
  show(resultSection);
}

/**
 * Set the card to error state with a message.
 * @param {string} message
 */
function setError(message) {
  state.status = 'error';
  stopLoadingMessages();
  hide(loadingZone);
  hide(resultSection);
  setStatus('error', 'ERROR');
  extractBtn.disabled = false;
  errorText.textContent = message;
  show(errorBanner);
}

/**
 * Update the status indicator dot + label.
 * @param {'idle'|'active'|'success'|'error'} type
 * @param {string} label
 */
function setStatus(type, label) {
  statusDot.className = 'status-dot';
  if (type !== 'idle') statusDot.classList.add(type);
  statusText.textContent = label;
}

/** Show a DOM element (flex/block). */
function show(el) { el.style.display = ''; }
/** Hide a DOM element. */
function hide(el) { el.style.display = 'none'; }

/* ══════════════════════════════════════════════════
   PLATFORM INDICATOR
══════════════════════════════════════════════════ */

/**
 * Update card header platform icon + label based on detected platform.
 * @param {'instagram'|'youtube'|null} platform
 */
function updatePlatformIndicator(platform) {
  // Reset classes
  platformIndicator.className = 'card-icon-wrap';
  inputWrap.className = 'input-wrap';

  if (!platform) {
    platformIcon.className = 'fa-solid fa-link';
    platformLabel.textContent = 'Awaiting URL input…';
    return;
  }

  const cfg = PLATFORMS[platform];
  platformIcon.className = cfg.iconCard;
  platformLabel.textContent = `${cfg.name} detected`;
  platformIndicator.classList.add(cfg.cardClass);
  inputWrap.classList.add(cfg.focusClass);
}

/* ══════════════════════════════════════════════════
   RESULT POPULATION
══════════════════════════════════════════════════ */

/**
 * Populate the result section with API data.
 * @param {object} data
 * @param {string} data.title
 * @param {string} data.thumbnail
 * @param {string} data.platform
 * @param {object} data.resolutions  { '360p': url, ... }
 */
function populateResult(data) {
  const { title, thumbnail, platform, resolutions } = data;

  // Title
  resultTitle.textContent = title || 'Untitled Video';

  // Thumbnail
  if (thumbnail) {
    resultThumbnail.src = thumbnail;
    resultThumbnail.alt = `Thumbnail for: ${title}`;
  } else {
    resultThumbnail.src = 'data:image/svg+xml,' + encodeURIComponent(
      `<svg xmlns="http://www.w3.org/2000/svg" width="320" height="180" viewBox="0 0 320 180">
        <rect width="320" height="180" fill="#12121e"/>
        <text x="50%" y="50%" font-size="14" fill="#4a5168" text-anchor="middle" dy=".3em" font-family="monospace">No Thumbnail</text>
      </svg>`
    );
  }

  // Platform badge
  const normalised = (platform || '').toLowerCase();
  const isIG = normalised === 'instagram';
  const isYT = normalised === 'youtube';

  const iconCls = isIG ? 'fa-brands fa-instagram' :
                  isYT ? 'fa-brands fa-youtube' :
                         'fa-solid fa-video';

  resultPlatformIcon.className = iconCls;
  resultPlatformName.textContent = platform || 'Unknown';

  videoTagIcon.className = iconCls;
  videoTagText.textContent = ' ' + (platform || 'Unknown');
  videoPlatformTag.className = `video-platform-tag ${isIG ? 'ig-tag' : isYT ? 'yt-tag' : ''}`;

  // Resolution dropdown
  state.currentResolutions = resolutions || {};
  resolutionSelect.innerHTML = '';

  const available = RESOLUTION_LABELS.filter(r => resolutions && resolutions[r]);

  if (available.length === 0) {
    // Fallback if no known labels
    Object.keys(resolutions || {}).forEach(key => {
      const opt = document.createElement('option');
      opt.value = key;
      opt.textContent = key;
      resolutionSelect.appendChild(opt);
    });
  } else {
    available.forEach(res => {
      const opt = document.createElement('option');
      opt.value = res;
      opt.textContent = res;
      resolutionSelect.appendChild(opt);
    });
  }
}

/* ══════════════════════════════════════════════════
   API CALL
══════════════════════════════════════════════════ */

/**
 * Fetch video metadata.
 * 1. Tries real Flask backend (POST /api/download) — returns actual MP4 URLs.
 * 2. Falls back to YouTube oEmbed + client-side Invidious/cobalt resolution
 *    when the backend is not running (404 / 405 / network error).
 * @param {string} url
 */
async function fetchVideoInfo(url) {
  setLoading();

  const platform = detectPlatform(url);

  try {
    const res = await fetch(API_ENDPOINT, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ url: url.trim() }),
    });

    if (res.ok) {
      const data = await res.json();
      if (!data.title || !data.resolutions) throw new Error('Invalid response from server.');
      setSuccess(data);
      return;
    }

    // Backend endpoint not wired up yet → fall back to client-side resolution
    if (res.status === 404 || res.status === 405) {
      await fetchVideoInfoFallback(url, platform);
      return;
    }

    // Real error returned by backend
    const errData = await res.json().catch(() => ({}));
    throw new Error(errData.error || errData.message || `Server error (${res.status})`);

  } catch (err) {
    if (err instanceof TypeError) {
      // Network error — backend not running, use client-side fallback
      await fetchVideoInfoFallback(url, platform);
    } else {
      setError(err.message || 'Failed to fetch video. Please try again.');
    }
  }
}

/**
 * Client-side fallback used when the Flask backend is not running.
 * Gets title + thumbnail from YouTube oEmbed; download URLs are resolved
 * on demand (via Invidious / cobalt) when the user clicks Download.
 * @param {string} url
 * @param {string|null} platform
 */
async function fetchVideoInfoFallback(url, platform) {
  try {
    let title = 'Video';
    let thumbnail = '';

    if (platform === 'youtube') {
      const oembedRes = await fetch(
        `https://www.youtube.com/oembed?url=${encodeURIComponent(url)}&format=json`
      );
      if (oembedRes.ok) {
        const meta = await oembedRes.json();
        title     = meta.title         || 'YouTube Video';
        thumbnail = meta.thumbnail_url || '';
      } else {
        title = 'YouTube Video';
      }
    } else if (platform === 'instagram') {
      title = 'Instagram Video';
    }

    // Store quality labels (not real URLs) — resolved by resolveDownloadUrl later
    setSuccess({
      title,
      thumbnail,
      platform: platform === 'youtube' ? 'YouTube' : 'Instagram',
      resolutions: { '1080p': '1080', '720p': '720', '480p': '480', '360p': '360' },
    });
  } catch {
    setError('Failed to load video info. Please check the URL and try again.');
  }
}



/* ══════════════════════════════════════════════════
   EVENT HANDLERS
══════════════════════════════════════════════════ */

/** Handle URL input changes — detect platform, show/hide clear btn */
function handleInput() {
  const url = urlInput.value.trim();
  const platform = detectPlatform(url);

  // Update state
  state.platform = platform;

  // Update platform indicator
  updatePlatformIndicator(platform);

  // Show/hide clear button
  clearBtn.style.display = url.length > 0 ? 'flex' : 'none';

  // Hide previous error on new input
  if (state.status === 'error') {
    hide(errorBanner);
    setStatus('idle', 'IDLE');
    state.status = 'idle';
  }
}

/** Handle Extract button click */
async function handleExtract() {
  const url = urlInput.value.trim();

  // Validation: empty
  if (!url) {
    setError('Please paste a video URL to get started.');
    urlInput.focus();
    return;
  }

  // Validation: not a URL
  if (!isValidUrl(url)) {
    setError('That doesn\'t look like a valid URL. Please check and try again.');
    urlInput.focus();
    return;
  }

  // Validation: unsupported platform
  const platform = detectPlatform(url);
  if (!platform) {
    setError('Unsupported platform. Please use an Instagram or YouTube link.');
    urlInput.focus();
    return;
  }

  hide(resultSection);
  await fetchVideoInfo(url);
}

/* ══════════════════════════════════════════════════
   DOWNLOAD RESOLUTION
   - YouTube  → Invidious public API (CORS-enabled, no key)
   - Instagram → cobalt public instances
══════════════════════════════════════════════════ */

/**
 * Public Invidious instances.
 * These expose CORS headers (Access-Control-Allow-Origin: *) so browser
 * fetch() works, and they proxy the stream URLs through themselves so
 * the resulting download link is also fetcha/openable directly.
 */
const INVIDIOUS_INSTANCES = [
  'https://yewtu.be',
  'https://inv.nadeko.net',
  'https://invidious.nerdvpn.de',
  'https://invidious.fdn.fr',
  'https://invidious.flokinet.to',
];

/** Public cobalt instances for Instagram (and non-YouTube) URLs */
const COBALT_INSTANCES = [
  'https://api.cobalt.tools/api/json',
  'https://co.wuk.sh/api/json',
  'https://cobalt.imput.net/api/json',
];

/**
 * Extract the 11-character YouTube video ID from any YouTube URL format
 * including /watch, /shorts/, youtu.be, /embed/.
 * @param {string} url
 * @returns {string|null}
 */
function extractYouTubeId(url) {
  const regExp =
    /(?:youtube\.com\/(?:watch\?v=|shorts\/|embed\/)|youtu\.be\/)([a-zA-Z0-9_-]{11})/;
  const match = url.match(regExp);
  return match ? match[1] : null;
}

/**
 * Convert YouTube Shorts URL to standard watch URL.
 * @param {string} url
 * @returns {string}
 */
function normaliseVideoUrl(url) {
  const m = url.match(/youtube\.com\/shorts\/([a-zA-Z0-9_-]+)/);
  return m ? `https://www.youtube.com/watch?v=${m[1]}` : url;
}

/**
 * Resolve a YouTube download URL using Invidious public API.
 * Returns a proxied MP4 stream URL (video + audio) at the best available
 * quality at or below the requested height.
 * @param {string} url  canonical YouTube watch URL
 * @param {string} quality  '1080', '720', '480', '360'
 * @returns {Promise<string>}
 */
async function resolveYouTubeDownloadUrl(url, quality) {
  const videoId = extractYouTubeId(url);
  if (!videoId) throw new Error('Could not extract YouTube video ID.');

  const wantedHeight = parseInt(quality, 10);

  for (const instance of INVIDIOUS_INSTANCES) {
    try {
      const res = await fetch(
        `${instance}/api/v1/videos/${videoId}?fields=formatStreams`,
        { signal: AbortSignal.timeout(20000) }
      );
      if (!res.ok) continue;

      const { formatStreams = [] } = await res.json();

      // formatStreams are muxed (video+audio) MP4 — ready to download
      const mp4 = formatStreams
        .filter(s => (s.type || '').includes('video/mp4'))
        .map(s => ({
          url: s.url,
          height: parseInt((s.qualityLabel || s.quality || '0').replace('p', ''), 10),
        }))
        .filter(s => s.url && s.height > 0)
        .sort((a, b) => b.height - a.height);

      if (!mp4.length) continue;

      // Best quality at or below request, else cheapest available
      const pick = mp4.find(s => s.height <= wantedHeight) ?? mp4[mp4.length - 1];
      if (pick?.url) return pick.url;
    } catch {
      continue;
    }
  }

  // All Invidious instances failed
  throw new Error('Unable to fetch video stream. This video may not allow direct downloading.');
}

/**
 * Resolve an Instagram (or other) download URL via public cobalt instances.
 * @param {string} url
 * @param {string} quality
 * @returns {Promise<string>}
 */
async function resolveCobaltDownloadUrl(url, quality) {
  for (const instance of COBALT_INSTANCES) {
    try {
      const res = await fetch(instance, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ url, vQuality: quality }),
        signal: AbortSignal.timeout(20000),
      });
      if (!res.ok) continue;

      const data = await res.json();
      if (data.status === 'error') continue;

      const dlUrl =
        data.url ||
        (data.stream && data.stream.url) ||
        (data.picker && data.picker[0] && data.picker[0].url);
      if (dlUrl) return dlUrl;
    } catch {
      continue;
    }
  }
  throw new Error('Download servers are busy right now. Please try again in a few seconds.');
}

/**
 * Route download resolution to the correct service based on platform.
 * @param {string} videoUrl
 * @param {string} quality  e.g. '1080'
 * @returns {Promise<string>}
 */
async function resolveDownloadUrl(videoUrl, quality) {
  const normUrl = normaliseVideoUrl(videoUrl);
  const platform = detectPlatform(normUrl);
  const resolve = () => platform === 'youtube'
    ? resolveYouTubeDownloadUrl(normUrl, quality)
    : resolveCobaltDownloadUrl(normUrl, quality);

  for (let attempt = 0; attempt < 3; attempt++) {
    try {
      return await resolve();
    } catch (e) {
      if (attempt < 2) {
        console.log(`Retrying download server… (attempt ${attempt + 2}/3)`);
      } else {
        throw e;
      }
    }
  }
}

/** Handle Download button click */
async function handleDownload() {
  const selectedResolution = resolutionSelect.value;
  const resValue = state.currentResolutions[selectedResolution];

  const btnSpan = downloadBtn.querySelector('span');
  downloadBtn.disabled = true;
  if (btnSpan) btnSpan.textContent = 'Preparing…';

  try {
    let downloadUrl;

    // Backend mode: resValue is a real HTTPS URL returned by Flask/yt-dlp
    if (resValue && (resValue.startsWith('http://') || resValue.startsWith('https://'))) {
      downloadUrl = resValue;
    } else {
      // Fallback mode: resValue is a quality string ('1080') — resolve via Invidious/cobalt
      const quality = selectedResolution.replace('p', '');
      const url = urlInput.value.trim();
      downloadUrl = await resolveDownloadUrl(url, quality);
    }

    const link = document.createElement('a');
    link.href = downloadUrl;
    link.target = '_blank';
    link.rel = 'noopener';
    document.body.appendChild(link);
    link.click();
    link.remove();

  } catch (err) {
    errorText.innerHTML = err.message || 'Download failed. Please try again.';
    errorBanner.style.display = '';
    setStatus('error', 'ERROR');
    state.status = 'error';
  } finally {
    downloadBtn.disabled = false;
    if (btnSpan) btnSpan.textContent = 'Download';
  }
}

/** Handle clear button click */
function handleClear() {
  urlInput.value = '';
  clearBtn.style.display = 'none';
  state.platform = null;
  updatePlatformIndicator(null);
  hide(errorBanner);
  hide(resultSection);
  setStatus('idle', 'IDLE');
  state.status = 'idle';
  urlInput.focus();
}

/** Handle Enter key in input field */
function handleInputKeydown(e) {
  if (e.key === 'Enter') {
    e.preventDefault();
    handleExtract();
  }
}

/** Handle paste event — auto-trigger extraction */
function handlePaste(e) {
  // Use setTimeout to allow the paste to populate the input first
  setTimeout(() => {
    handleInput();
    // Auto-trigger extraction on paste if URL is valid and platform detected
    const url = urlInput.value.trim();
    if (isValidUrl(url) && detectPlatform(url)) {
      handleExtract();
    }
  }, 50);
}

/* ══════════════════════════════════════════════════
   EVENT LISTENERS
══════════════════════════════════════════════════ */

urlInput.addEventListener('input', handleInput);
urlInput.addEventListener('keydown', handleInputKeydown);
urlInput.addEventListener('paste', handlePaste);
clearBtn.addEventListener('click', handleClear);
extractBtn.addEventListener('click', handleExtract);
downloadBtn.addEventListener('click', handleDownload);

/* ══════════════════════════════════════════════════
   INITIALISATION
══════════════════════════════════════════════════ */

function init() {
  // Ensure initial state
  setIdle();
  hide(loadingZone);
  hide(resultSection);
  hide(errorBanner);
  clearBtn.style.display = 'none';
  updatePlatformIndicator(null);

  // Focus input on load (desktop only)
  if (window.innerWidth >= 769) {
    urlInput.focus();
  }
}

// Run after DOM is ready
if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', init);
} else {
  init();
}
