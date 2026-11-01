"""Serve the built website locally and exercise it in Chromium."""
import functools
from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler
from pathlib import Path
import subprocess
import threading
from html.parser import HTMLParser
from urllib.parse import unquote, urlsplit

ROOT = Path(__file__).resolve().parents[1]


class PageLinks(HTMLParser):
    def __init__(self):
        super().__init__()
        self.links = []
        self.ids = set()

    def handle_starttag(self, tag, attrs):
        attributes = dict(attrs)
        if 'id' in attributes:
            self.ids.add(attributes['id'])
        self.links.extend(attributes[key] for key in ('href', 'src') if key in attributes)


def check_links():
    site = (ROOT/'site').resolve()
    pages = {}
    for path in site.rglob('*.html'):
        page = PageLinks()
        page.feed(path.read_text(encoding='utf-8'))
        pages[path] = page
    count = 0
    for path, page in pages.items():
        for link in page.links:
            uri = urlsplit(link)
            if uri.scheme or link.startswith('//'):
                continue
            target = site/unquote(uri.path).lstrip('/') if uri.path.startswith('/') else (path.parent/unquote(uri.path) if uri.path else path)
            target = target.resolve()
            if target.is_dir():
                target /= 'index.html'
            assert target.is_relative_to(site), f'Link outside site: {link}'
            assert target.exists(), f'{path.name}: missing {link}'
            if uri.fragment and target in pages:
                assert unquote(uri.fragment) in pages[target].ids, f'{path.name}: missing anchor {link}'
            count += 1
    print(f'PASS: {len(pages)} website pages, {count} local links and assets')


if __name__ == '__main__':
    check_links()
    output = ROOT/'build'/'qa'
    output.mkdir(parents=True, exist_ok=True)
    server = ThreadingHTTPServer(('127.0.0.1', 0), functools.partial(SimpleHTTPRequestHandler, directory=str(ROOT/'site')))
    threading.Thread(target=server.serve_forever, daemon=True).start()
    try:
        subprocess.run(['node', 'scripts/browser.mjs', 'check-site', f'http://127.0.0.1:{server.server_port}/', str(output)], cwd=ROOT, check=True)
    finally:
        server.shutdown()
