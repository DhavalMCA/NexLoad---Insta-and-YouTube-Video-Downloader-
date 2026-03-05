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


def snap_height(h: int) -> int:
    """Round a raw pixel height to the nearest standard label."""
    standards = sorted(SUPPORTED_HEIGHTS)
    return min(standards, key=lambda s: abs(s - h))


def extract_resolutions(formats: list) -> dict:
    """
    Walk yt-dlp format list and return a dict mapping
    '360p', '480p', '720p', '1080p' → direct stream URL.

    Accepts mp4 and webm.  Prefers muxed (video+audio) over video-only.
    Any height is snapped to the nearest standard label.
    """
    best: dict[str, dict] = {}   # height_str → {'url', 'has_audio'}

    for fmt in formats:
        ext = fmt.get('ext', '')
        if ext not in ('mp4', 'webm'):
            continue
        url = fmt.get('url')
        if not url:
            continue
        height = fmt.get('height')
        if not height or height < 100:
            continue

        has_audio = fmt.get('acodec', 'none') != 'none'
        has_video = fmt.get('vcodec', 'none') != 'none'
        if not has_video:
            continue

        key = str(snap_height(height))
        existing = best.get(key)
        # Prefer muxed stream; if equal, keep highest bitrate
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
        'quiet':              True,
        'no_warnings':        True,
        'skip_download':      True,
        'geo_bypass':         True,
        'geo_bypass_country': 'IN',
        'extractor_args': {
            'youtube': {
                'player_client': ['android', 'web'],
            },
        },
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

        # Fallback: include any video format regardless of container/height
        if not resolutions:
            for fmt in formats:
                url_f = fmt.get('url')
                h     = fmt.get('height')
                if not url_f or not h or h < 100:
                    continue
                if fmt.get('vcodec', 'none') == 'none':
                    continue
                resolutions.setdefault(f'{h}p', url_f)

        if not resolutions:
            return jsonify({'error': 'No downloadable MP4 formats found for this video.'}), 404

        return jsonify({
            'title':       title,
            'thumbnail':   thumbnail,
            'platform':    platform,
            'resolutions': resolutions,
        })

    except yt_dlp.utils.DownloadError as exc:
        msg = str(exc).replace('ERROR: ', '', 1)
        if 'not made this video available in your country' in msg or 'geo' in msg.lower():
            return jsonify({'error': 'This video is geo-restricted and not available in the server\'s region. Try a different video.'}), 400
        return jsonify({'error': msg}), 400

    except Exception as exc:
        return jsonify({'error': f'Unexpected error: {exc}'}), 500


# ── Entry Point ───────────────────────────────────────────────────────────────

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(debug=False, host='0.0.0.0', port=port)
