"""
NexLoad — Social Video Downloader
app.py — Flask backend using yt-dlp

Run:
    pip install -r requirements.txt
    python app.py

Endpoints:
    GET  /              → serve frontend (Index.html)
    POST /api/download  → extract video metadata + direct MP4 download URLs
"""

import os
from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
import yt_dlp

# ── App Setup ─────────────────────────────────────────────────────────────────

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

app = Flask(__name__, static_folder=BASE_DIR, template_folder=BASE_DIR)
CORS(app)   # Allow requests from any origin (needed if frontend is served separately)

# ── Helpers ───────────────────────────────────────────────────────────────────

PLATFORM_HOSTS = {
    'instagram.com': 'Instagram',
    'youtube.com':   'YouTube',
    'youtu.be':      'YouTube',
}

SUPPORTED_HEIGHTS = {360, 480, 720, 1080}


def detect_platform(url: str):
    """Return 'Instagram' | 'YouTube' | None based on URL host."""
    for host, name in PLATFORM_HOSTS.items():
        if host in url:
            return name
    return None


def extract_resolutions(formats: list) -> dict:
    """
    Walk yt-dlp format list and return a dict mapping
    '360p', '480p', '720p', '1080p' → direct MP4 stream URL.

    Prefers muxed (video + audio) streams over video-only.
    """
    best: dict[str, dict] = {}   # height_str → {'url', 'has_audio'}

    for fmt in formats:
        if fmt.get('ext') != 'mp4':
            continue
        url = fmt.get('url')
        if not url:
            continue
        height = fmt.get('height')
        if not height or height not in SUPPORTED_HEIGHTS:
            continue

        has_audio = fmt.get('acodec', 'none') != 'none'
        has_video = fmt.get('vcodec', 'none') != 'none'
        if not has_video:
            continue

        key = str(height)
        existing = best.get(key)
        # Prefer muxed stream; if equal, keep first found
        if existing is None or (has_audio and not existing['has_audio']):
            best[key] = {'url': url, 'has_audio': has_audio}

    return {f'{h}p': v['url'] for h, v in best.items()}


# ── Static Routes ─────────────────────────────────────────────────────────────

@app.route('/')
def index():
    return send_from_directory(BASE_DIR, 'index.html')


@app.route('/style.css')
def serve_css():
    return send_from_directory(BASE_DIR, 'style.css')


@app.route('/script.js')
def serve_js():
    return send_from_directory(BASE_DIR, 'script.js')


# ── API ───────────────────────────────────────────────────────────────────────

@app.route('/api/download', methods=['POST'])
def api_download():
    """
    POST /api/download
    Body:  { "url": "https://..." }
    Returns:
    {
        "title":       "...",
        "thumbnail":   "https://...",
        "platform":    "YouTube | Instagram",
        "resolutions": { "360p": "...", "720p": "...", ... }
    }
    """
    body = request.get_json(silent=True)
    if not body or not body.get('url'):
        return jsonify({'error': 'URL is required.'}), 400

    url      = body['url'].strip()
    platform = detect_platform(url)

    if not platform:
        return jsonify({
            'error': 'Unsupported platform. Please use an Instagram or YouTube link.'
        }), 400

    ydl_opts = {
        'quiet':        True,
        'no_warnings':  True,
        'skip_download': True,
        'geo_bypass':   True,
        # Uncomment to use your browser cookies for age-gated / private content:
        # 'cookiesfrombrowser': ('chrome',),
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)

        title       = info.get('title')     or 'Unknown Title'
        thumbnail   = info.get('thumbnail') or ''
        formats     = info.get('formats')   or []

        resolutions = extract_resolutions(formats)

        # Fallback: include any MP4 heights that weren't in the standard set
        if not resolutions:
            for fmt in formats:
                if fmt.get('ext') == 'mp4' and fmt.get('url') and fmt.get('height'):
                    h = fmt['height']
                    resolutions.setdefault(f'{h}p', fmt['url'])

        if not resolutions:
            return jsonify({'error': 'No downloadable MP4 formats found for this video.'}), 404

        return jsonify({
            'title':       title,
            'thumbnail':   thumbnail,
            'platform':    platform,
            'resolutions': resolutions,
        })

    except yt_dlp.utils.DownloadError as exc:
        # Strip yt-dlp's verbose prefix for a cleaner user-facing message
        msg = str(exc).replace('ERROR: ', '', 1)
        return jsonify({'error': msg}), 400

    except Exception as exc:
        return jsonify({'error': f'Unexpected error: {exc}'}), 500


# ── Entry Point ───────────────────────────────────────────────────────────────

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(debug=False, host='0.0.0.0', port=port)
