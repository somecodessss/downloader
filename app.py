import os
from flask import Flask, request, Response, abort
import requests
from urllib.parse import urlparse, unquote
import posixpath

app = Flask(__name__)

BLOCKED_DOMAINS = {
    'youtube.com','youtu.be','spotify.com','spotifycdn.com','soundcloud.com',
    'music.apple.com','apple.com','tiktok.com','tiktokcdn.com','bandcamp.com'
}
MAX_BYTES = int(os.getenv('MAX_BYTES', str(52428800)))
TIMEOUT = (5, 20)
CHUNK = 65536

def filename_from_url(u):
    p = urlparse(u).path
    name = posixpath.basename(p) or 'download'
    return unquote(name)

def host_blocked(host):
    for d in BLOCKED_DOMAINS:
        if host == d or host.endswith('.' + d):
            return True
    return False

def validate_url(u):
    pr = urlparse(u)
    if pr.scheme not in ('http', 'https'):
        abort(400)
    host = pr.hostname or ''
    if host_blocked(host):
        abort(403)

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
        ct = (head.headers.get('Content-Type') or '').lower()
        cl = head.headers.get('Content-Length')
        if cl:
            try:
                if int(cl) > MAX_BYTES:
                    abort(413)
            except ValueError:
                pass
    except requests.RequestException:
        ct = ''
    
    try:
        r = requests.get(u, stream=True, allow_redirects=True, timeout=TIMEOUT)
    except requests.RequestException:
        abort(502)

    cd = r.headers.get('Content-Disposition') or ''
    if 'filename=' in cd:
        fname = cd.split('filename=')[-1].strip('"; ')
    else:
        fname = filename_from_url(r.url)

    def generate():
        total = 0
        for chunk in r.iter_content(CHUNK):
            if chunk:
                total += len(chunk)
                if total > MAX_BYTES:
                    abort(413)
                yield chunk

    headers = {
        'Content-Type': (r.headers.get('Content-Type') or ct or 'application/octet-stream'),
        'Content-Disposition': f'attachment; filename="{fname}"'
    }
    return Response(generate(), headers=headers)
