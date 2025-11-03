import collections
import ssl
import sys
import time
import urllib.parse
import urllib.request
from html.parser import HTMLParser

SOCIAL_DOMAINS = {
    'facebook.com', 'fb.com', 'twitter.com', 'x.com', 'instagram.com', 'linkedin.com',
    'youtube.com', 'youtu.be', 'tiktok.com', 'pinterest.com', 'snapchat.com',
    'reddit.com', 'vk.com', 'ok.ru', 'telegram.org', 'telegram.me', 'wa.me',
    'whatsapp.com', 'messenger.com', 'discord.gg', 'discord.com', 'weibo.com',
    'line.me', 'medium.com'
}

DEFAULT_USER_AGENT = (
    'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 '
    '(KHTML, like Gecko) Chrome/124.0 Safari/537.36'
)

MAX_PAGES_PER_SITE = 2000
MAX_DEPTH = 4
REQUEST_TIMEOUT = 15
PAUSE_SECONDS = 0.2

class LinkExtractor(HTMLParser):
    def __init__(self):
        super().__init__()
        self.links = []
    def handle_starttag(self, tag, attrs):
        if tag.lower() != 'a':
            return
        href = dict(attrs).get('href')
        if href:
            self.links.append(href)

def normalize_url(base, url):
    url = url.strip()
    if not url:
        return None
    parsed = urllib.parse.urlparse(url)
    if parsed.scheme in ('http', 'https'):
        return urllib.parse.urlunparse(parsed._replace(fragment=''))
    if parsed.scheme in ('mailto', 'javascript', 'tel', 'data'):
        return None
    if url.startswith('#'):
        return None
    return urllib.parse.urljoin(base, url)

def domain_from_url(url):
    return urllib.parse.urlparse(url).hostname or ''

def is_same_site(url, root_netloc):
    host = domain_from_url(url)
    return host == root_netloc or host.endswith('.' + root_netloc)

def is_social(url):
    host = domain_from_url(url).lower()
    for social in SOCIAL_DOMAINS:
        if host == social or host.endswith('.' + social):
            return True
    return False

def fetch(url, opener):
    req = urllib.request.Request(url, headers={'User-Agent': DEFAULT_USER_AGENT})
    with opener.open(req, timeout=REQUEST_TIMEOUT) as resp:
        ctype = resp.headers.get('Content-Type', '')
        if 'text/html' not in ctype:
            return ''
        data = resp.read()
        try:
            return data.decode('utf-8', errors='replace')
        except Exception:
            return data.decode('latin-1', errors='replace')

def crawl_site(start_url, opener):
    root_netloc = urllib.parse.urlparse(start_url).hostname
    if not root_netloc:
        return set(), 0, []
    queue = collections.deque([(start_url, 0)])
    visited = set()
    enqueued = {start_url}
    externals = set()
    errors = []
    while queue:
        url, depth = queue.popleft()
        if url in visited:
            continue
        visited.add(url)
        if len(visited) > MAX_PAGES_PER_SITE:
            break
        try:
            html_text = fetch(url, opener)
        except Exception as exc:
            errors.append((url, str(exc)))
            continue
        extractor = LinkExtractor()
        try:
            extractor.feed(html_text)
        except Exception:
            pass
        for raw_link in extractor.links:
            resolved = normalize_url(url, raw_link)
            if not resolved:
                continue
            netloc = domain_from_url(resolved)
            if not netloc:
                continue
            if is_same_site(resolved, root_netloc):
                if depth + 1 <= MAX_DEPTH and resolved not in visited and resolved not in enqueued:
                    queue.append((resolved, depth + 1))
                    enqueued.add(resolved)
            else:
                if not is_social(resolved):
                    externals.add(resolved)
        if PAUSE_SECONDS:
            time.sleep(PAUSE_SECONDS)
    return externals, len(visited), errors

def build_opener():
    try:
        ssl_context = ssl.create_default_context(cafile='/etc/ssl/cert.pem')
    except Exception:
        ssl_context = ssl.create_default_context()
    https_handler = urllib.request.HTTPSHandler(context=ssl_context)
    opener = urllib.request.build_opener(https_handler)
    return opener

def main():
    try:
        with open('site_urls.txt', encoding='utf-8') as f:
            seeds = [line.strip() for line in f if line.strip()][:1]
    except FileNotFoundError:
        print('site_urls.txt missing', file=sys.stderr)
        sys.exit(1)
    opener = build_opener()
    all_externals = set()
    per_site = {}
    reports = {}
    for seed in seeds:
        externals, visited_count, errors = crawl_site(seed, opener)
        per_site[seed] = externals
        all_externals.update(externals)
        reports[seed] = {
            'pages_visited': visited_count,
            'external_links': len(externals),
            'errors': errors,
        }
    with open('external_links_dedup.txt', 'w', encoding='utf-8') as f:
        for link in sorted(all_externals):
            f.write(link + '\n')
    for seed, links in per_site.items():
        hostname = urllib.parse.urlparse(seed).hostname or 'site'
        filename = f"external_links_{hostname}.txt"
        with open(filename, 'w', encoding='utf-8') as f:
            for link in sorted(links):
                f.write(link + '\n')
    with open('external_links_report.txt', 'w', encoding='utf-8') as f:
        for seed, info in reports.items():
            f.write(f"Site: {seed}\n")
            f.write(f"  Pages visited: {info['pages_visited']}\n")
            f.write(f"  External links (non-social): {info['external_links']}\n")
            if info['errors']:
                f.write("  Errors:\n")
                for url, err in info['errors']:
                    f.write(f"    {url}: {err}\n")
            f.write('\n')

if __name__ == '__main__':
    main()
