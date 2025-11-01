import os
from flask import Flask, request, Response, abort
import requests
from urllib.parse import urlparse, unquote
import posixpath

app = Flask(__name__)

ALLOWED_EXTS = {'.mp3', '.wav', '.flac', '.m4a', '.aac', '.ogg', '.opus'}
BLOCKED_DOMAINS = {'youtube.com','youtu.be','spotify.com','spotifycdn.com','soundcloud.com','music.apple.com','apple.com','tiktok.com','tiktokcdn.com','bandcamp.com'}
MAX_BYTES = int(os.getenv('MAX_BYTES', str(52428800)))
TIMEOUT = (5, 20)
CHUNK = 65536

def ext_allowed(path):
    return posixpath.splitext(path)[1].lower() in ALLOWED_EXTS

def filename_from_url(u):
    p = urlparse(u).path
    name = posixpath.basename(p) or 'audio'
    return unquote(name)

def host_blocked(host):
    for d in BLOCKED_DOMAINS:
        if host == d or host.endswith('.'+d):
            return True
    return False

def validate_url(u):
    pr = urlparse(u)
    if pr.scheme not in ('http','https'):
        abort(400)
    host = pr.hostname or ''
    if host_blocked(host):
        abort(403)
    if not ext_allowed(pr.path):
        abort(415)

@app.get('/')
def root():
    return 'OK', 200

@app.get('/fetch')
def fetch():
    u = (request.args.get('url') or '').strip()
    if not u:
        abort(400)
    validate_url(u)
    try:
        head = requests.head(u, allow_redirects=True, timeout=TIMEOUT)
    except requests.RequestException:
        abort(502)
    ct = (head.headers.get('Content-Type') or '').lower()
    if 'audio' not in ct:
        abort(415)
    cl = head.headers.get('Content-Length')
    if cl:
        try:
            if int(cl) > MAX_BYTES:
                abort(413)
        except ValueError:
            pass
    try:
        r = requests.get(u, stream=True, allow_redirects=True, timeout=TIMEOUT)
    except requests.RequestException:
        abort(502)
    fname = filename_from_url(r.url)
    def generate():
        for chunk in r.iter_content(CHUNK):
            if chunk:
                yield chunk
    headers = {
        'Content-Type': r.headers.get('Content-Type', ct or 'application/octet-stream'),
        'Content-Disposition': f'attachment; filename="{fname}"'
    }
    return Response(generate(), headers=headers)
