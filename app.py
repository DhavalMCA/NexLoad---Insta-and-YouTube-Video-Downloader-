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
import re
import tempfile
import shutil
import logging
from flask import Flask, request, jsonify, send_from_directory, Response, stream_with_context
from flask_cors import CORS
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_caching import Cache
import yt_dlp

# ── App Setup ─────────────────────────────────────────────────────────────────

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

app = Flask(__name__, static_folder=BASE_DIR, template_folder=BASE_DIR)
CORS(app)

# ── Logging ───────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
)

# ── Rate Limiting ─────────────────────────────────────────────────────────────
limiter = Limiter(
    get_remote_address,
    app=app,
    default_limits=['200 per day', '50 per hour'],
    storage_uri='memory://',
)

# ── Caching ───────────────────────────────────────────────────────────────────
cache = Cache(app, config={'CACHE_TYPE': 'SimpleCache', 'CACHE_DEFAULT_TIMEOUT': 600})

# ── Helpers ───────────────────────────────────────────────────────────────────

PLATFORM_HOSTS = {
    'instagram.com': 'Instagram',
    'youtube.com':   'YouTube',
    'youtu.be':      'YouTube',
    'tiktok.com':    'TikTok',
    'facebook.com':  'Facebook',
    'fb.watch':      'Facebook',
    'twitter.com':   'Twitter',
    'x.com':         'Twitter',
    'reddit.com':    'Reddit',
    'redd.it':       'Reddit',
}

SUPPORTED_HEIGHTS = {360, 480, 720, 1080}


def detect_platform(url: str):
    """Return platform name or None based on URL host."""
    for host, name in PLATFORM_HOSTS.items():
        if host in url:
            return name
    return None


_URL_RE = re.compile(r'^https?://.+', re.IGNORECASE)


def validate_url(url: str) -> bool:
    """Return True only if the value looks like a proper http(s) URL."""
    return bool(_URL_RE.match(url))


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


# ── Cached Info Fetcher ──────────────────────────────────────────────────────

INFO_YDL_OPTS = {
    'quiet':              True,
    'no_warnings':        True,
    'skip_download':      True,
    'retries':            10,
    'fragment_retries':   10,
    'geo_bypass':         True,
    'geo_bypass_country': 'IN',
    'extractor_args': {
        'youtube': {
            'player_client': ['android', 'web'],
        },
    },
    'http_headers': {
        'User-Agent': (
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
            'AppleWebKit/537.36 (KHTML, like Gecko) '
            'Chrome/120.0.0.0 Safari/537.36'
        ),
    },
}


@cache.memoize(timeout=600)
def _fetch_info_cached(url: str) -> dict:
    """Extract video metadata with yt-dlp; result is cached for 10 minutes."""
    with yt_dlp.YoutubeDL(INFO_YDL_OPTS) as ydl:
        return ydl.extract_info(url, download=False)


# ── API ───────────────────────────────────────────────────────────────────────

@app.route('/api/download', methods=['POST'])
@limiter.limit('10 per minute')
def api_download():
    """
    POST /api/download
    Body:  { "url": "https://..." }
    Returns:
    {
        "title":       "...",
        "thumbnail":   "https://...",
        "platform":    "Instagram | YouTube | TikTok | Facebook | Twitter | Reddit",
        "resolutions": { "360p": "...", "720p": "...", ... }
    }
    """
    body = request.get_json(silent=True)
    if not body or not body.get('url'):
        return jsonify({'error': 'URL is required.'}), 400

    url = body['url'].strip()

    if not validate_url(url):
        return jsonify({'error': 'Invalid URL. Please provide a valid http(s) link.'}), 400

    platform = detect_platform(url)
    if not platform:
        return jsonify({
            'error': 'Unsupported platform. Supported: Instagram, YouTube, TikTok, Facebook, Twitter, Reddit.'
        }), 400

    try:
        info      = _fetch_info_cached(url)
        title     = info.get('title')     or 'Unknown Title'
        thumbnail = info.get('thumbnail') or ''
        formats   = info.get('formats')   or []

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
            return jsonify({'error': 'No downloadable formats found for this video.'}), 404

        return jsonify({
            'title':       title,
            'thumbnail':   thumbnail,
            'platform':    platform,
            'resolutions': resolutions,
        })

    except yt_dlp.utils.DownloadError as exc:
        msg = str(exc).replace('ERROR: ', '', 1)
        app.logger.warning('DownloadError for %s: %s', url, msg)
        if 'not made this video available in your country' in msg or 'geo' in msg.lower():
            return jsonify({'error': 'This video is geo-restricted. Try a different video.'}), 400
        if 'sign in' in msg.lower() or 'bot' in msg.lower():
            return jsonify({'error': 'YouTube bot detection triggered. Please try again in a moment.'}), 429
        return jsonify({'error': msg}), 400

    except Exception as exc:
        app.logger.error('Unexpected error for %s: %s', url, exc, exc_info=True)
        return jsonify({'error': f'Unexpected error: {exc}'}), 500


# ── Stream (Merge & Download) ────────────────────────────────────────────────

@app.route('/api/stream', methods=['GET'])
@limiter.limit('5 per minute')
def api_stream():
    """
    GET /api/stream?url=<video_url>&quality=<720|480|…>
    Downloads the video server-side with yt-dlp (merging separate video+audio
    streams, which Instagram always uses), then streams the resulting MP4 back
    to the client so the downloaded file always has audio.
    Requires ffmpeg on PATH for stream merging.
    """
    url     = request.args.get('url', '').strip()
    quality = request.args.get('quality', '720').strip().replace('p', '')

    if not url:
        return jsonify({'error': 'URL is required.'}), 400

    if not validate_url(url):
        return jsonify({'error': 'Invalid URL. Please provide a valid http(s) link.'}), 400

    platform = detect_platform(url)
    if not platform:
        return jsonify({'error': 'Unsupported platform.'}), 400

    try:
        height = int(quality)
    except ValueError:
        height = 720

    tmp_dir = tempfile.mkdtemp()
    output_template = os.path.join(tmp_dir, '%(title).60s.%(ext)s')

    ydl_opts = {
        'quiet':               True,
        'no_warnings':         True,
        'outtmpl':             output_template,
        'retries':             10,
        'fragment_retries':    10,
        # Prefer muxed mp4 first; fall back to merging best video + best audio
        'format': (
            f'bestvideo[height<={height}][ext=mp4]+bestaudio[ext=m4a]'
            f'/bestvideo[height<={height}]+bestaudio'
            f'/best[height<={height}]'
            f'/best'
        ),
        'merge_output_format': 'mp4',
        'geo_bypass':          True,
        'geo_bypass_country':  'IN',
        'extractor_args': {
            'youtube': {
                'player_client': ['android', 'web'],
            },
        },
        'http_headers': {
            'User-Agent': (
                'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
                'AppleWebKit/537.36 (KHTML, like Gecko) '
                'Chrome/120.0.0.0 Safari/537.36'
            ),
        },
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)

        files = [
            f for f in os.listdir(tmp_dir)
            if os.path.isfile(os.path.join(tmp_dir, f))
        ]
        if not files:
            shutil.rmtree(tmp_dir, ignore_errors=True)
            return jsonify({'error': 'Download produced no output file.'}), 500

        filepath  = os.path.join(tmp_dir, files[0])
        file_size = os.path.getsize(filepath)

        raw_title  = (info.get('title') if isinstance(info, dict) else None) or 'video'
        safe_title = ''.join(
            c for c in raw_title if c.isalnum() or c in ' -_'
        ).strip()[:60] or 'video'

        def _generate():
            try:
                with open(filepath, 'rb') as fh:
                    while True:
                        chunk = fh.read(65536)
                        if not chunk:
                            break
                        yield chunk
            finally:
                shutil.rmtree(tmp_dir, ignore_errors=True)

        return Response(
            stream_with_context(_generate()),
            mimetype='video/mp4',
            headers={
                'Content-Disposition': f'attachment; filename="{safe_title}.mp4"',
                'Content-Length':      str(file_size),
                'Cache-Control':       'no-cache',
            },
        )

    except yt_dlp.utils.DownloadError as exc:
        shutil.rmtree(tmp_dir, ignore_errors=True)
        msg = str(exc).replace('ERROR: ', '', 1)
        app.logger.warning('Stream DownloadError for %s: %s', url, msg)
        return jsonify({'error': msg}), 400

    except Exception as exc:
        shutil.rmtree(tmp_dir, ignore_errors=True)
        app.logger.error('Stream unexpected error for %s: %s', url, exc, exc_info=True)
        return jsonify({'error': f'Unexpected error: {exc}'}), 500


# ── Health Check ──────────────────────────────────────────────────────────────

@app.route('/health')
def health():
    return jsonify({'status': 'ok'})


# ── Entry Point ───────────────────────────────────────────────────────────────

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(debug=False, host='0.0.0.0', port=port)
