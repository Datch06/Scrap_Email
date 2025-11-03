#!/usr/bin/env python3
"""Headless crawler using Playwright to collect external backlinks.

Usage example:
    pip install playwright
    playwright install chromium
    python playwright_crawl.py --start https://dzen.ru/ https://www.msn.com/ https://rakuten.co.jp/ \
        --max-pages 500 --max-depth 3 --output externals.txt

The script will browse each provided URL, follow in-domain links up to the
specified depth/page limits, extract all anchors, filter out social networks,
and write the deduplicated list of external URLs to the chosen output file.

NOTE: High limits can take a long time and may trigger anti-bot protections.
Adjust throttling parameters if needed.
"""

from __future__ import annotations

import argparse
import asyncio
import sys
import time
from collections import deque
from typing import Iterable, Set, Tuple
from urllib.parse import urljoin, urlparse, urlunparse

from playwright.async_api import async_playwright, Browser, Page

SOCIAL_DOMAINS = {
    "facebook.com",
    "fb.com",
    "twitter.com",
    "x.com",
    "instagram.com",
    "linkedin.com",
    "youtube.com",
    "youtu.be",
    "tiktok.com",
    "pinterest.com",
    "snapchat.com",
    "reddit.com",
    "vk.com",
    "ok.ru",
    "telegram.org",
    "telegram.me",
    "wa.me",
    "whatsapp.com",
    "messenger.com",
    "discord.gg",
    "discord.com",
    "weibo.com",
    "line.me",
    "medium.com",
}

DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0 Safari/537.36"
)


def normalize_url(base: str, href: str) -> str | None:
    href = (href or "").strip()
    if not href:
        return None
    if href.startswith("mailto:") or href.startswith("tel:") or href.startswith("javascript:"):
        return None
    if href.startswith("#"):
        return None
    parsed = urlparse(href)
    if parsed.scheme in ("http", "https"):
        cleaned = parsed._replace(fragment="", params="")
        return urlunparse(cleaned)
    # Relative URL
    joined = urljoin(base, href)
    cleaned = urlparse(joined)._replace(fragment="", params="")
    return urlunparse(cleaned)


def hostname(url: str) -> str:
    return urlparse(url).hostname or ""


def is_same_site(url: str, root_host: str) -> bool:
    host = hostname(url).lower()
    root = root_host.lower()
    return host == root or host.endswith("." + root)


def is_social(url: str) -> bool:
    host = hostname(url).lower()
    for domain in SOCIAL_DOMAINS:
        if host == domain or host.endswith("." + domain):
            return True
    return False


async def extract_links(page: Page, url: str) -> Tuple[Set[str], Set[str]]:
    await page.goto(url, wait_until="networkidle")
    anchors = await page.eval_on_selector_all(
        "a[href]",
        "elements => elements.map(el => el.getAttribute('href'))"
    )
    internal: Set[str] = set()
    external: Set[str] = set()
    base_host = hostname(url)
    for raw in anchors:
        normalized = normalize_url(url, raw)
        if not normalized:
            continue
        if is_same_site(normalized, base_host):
            internal.add(normalized)
        else:
            if not is_social(normalized):
                external.add(normalized)
    return internal, external


async def crawl(start_urls: Iterable[str], max_pages: int, max_depth: int, delay: float,
                timeout: float, output: str, per_site_output: bool, headless: bool) -> None:
    seen_external: Set[str] = set()

    async with async_playwright() as p:
        browser: Browser = await p.chromium.launch(
            headless=headless,
            args=["--disable-blink-features=AutomationControlled"]
        )

        for start_url in start_urls:
            context = await browser.new_context(user_agent=DEFAULT_USER_AGENT)
            queue = deque([(start_url, 0)])
            visited: Set[str] = set()
            site_external: Set[str] = set()
            start_host = hostname(start_url)

            print(f"[INFO] Crawling {start_url} (host={start_host})")
            while queue and len(visited) < max_pages:
                current, depth = queue.popleft()
                if current in visited or depth > max_depth:
                    continue

                try:
                    page = await context.new_page()
                except Exception as exc:
                    print(f"  [WARN] Unable to open new page for {current}: {exc}")
                    try:
                        await context.close()
                    except Exception:
                        pass
                    context = await browser.new_context(user_agent=DEFAULT_USER_AGENT)
                    queue.appendleft((current, depth))
                    continue

                try:
                    await page.goto(current, wait_until="networkidle", timeout=timeout * 1000)
                except Exception as exc:
                    print(f"  [WARN] Failed to load {current}: {exc}")
                    await page.close()
                    continue

                try:
                    internal_links, external_links = await extract_links(page, current)
                except Exception as exc:
                    print(f"  [WARN] Failed to extract links from {current}: {exc}")
                    internal_links, external_links = set(), set()
                visited.add(current)
                await page.close()

                for link in external_links:
                    if link not in seen_external:
                        print(f"    [EXT] {link}")
                        seen_external.add(link)
                        site_external.add(link)

                for link in internal_links:
                    if link not in visited:
                        queue.append((link, depth + 1))

                if delay:
                    await asyncio.sleep(delay)

            if per_site_output:
                site_file = f"externals_{start_host.replace('.', '_')}.txt"
                with open(site_file, "w", encoding="utf-8") as f:
                    for link in sorted(site_external):
                        f.write(link + "\n")
                print(f"  [INFO] Wrote {len(site_external)} links to {site_file}")

            await context.close()

        await browser.close()

    with open(output, "w", encoding="utf-8") as f:
        for link in sorted(seen_external):
            f.write(link + "\n")
    print(f"[INFO] Wrote {len(seen_external)} unique external links to {output}")


def parse_args(argv: Iterable[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Crawl pages with Playwright and extract external links")
    parser.add_argument("--start", nargs="+", required=True,
                        help="One or more starting URLs (include the https://)")
    parser.add_argument("--max-pages", type=int, default=200,
                        help="Maximum pages per start URL (default: 200)")
    parser.add_argument("--max-depth", type=int, default=3,
                        help="Maximum depth from each start URL (default: 3)")
    parser.add_argument("--delay", type=float, default=1.0,
                        help="Delay in seconds between page visits (default: 1.0)")
    parser.add_argument("--timeout", type=float, default=20.0,
                        help="Navigation timeout in seconds (default: 20)")
    parser.add_argument("--output", default="external_links.txt",
                        help="Path to the combined output file (default: external_links.txt)")
    parser.add_argument("--per-site", action="store_true",
                        help="Also write one file per start host")
    parser.add_argument("--headed", action="store_true",
                        help="Run the browser with a visible window (disables headless mode)")
    return parser.parse_args(argv)


def main(argv: Iterable[str]) -> None:
    args = parse_args(argv)
    start_urls = args.start
    if not all(urlparse(url).scheme for url in start_urls):
        print("[ERROR] All start URLs must include the scheme, e.g. https://example.com", file=sys.stderr)
        sys.exit(1)

    try:
        asyncio.run(
            crawl(
                start_urls=start_urls,
                max_pages=args.max_pages,
                max_depth=args.max_depth,
                delay=args.delay,
                timeout=args.timeout,
                output=args.output,
                per_site_output=args.per_site,
                headless=not args.headed,
            )
        )
    except KeyboardInterrupt:
        print("[INFO] Interrupted by user")


if __name__ == "__main__":
    main(sys.argv[1:])
