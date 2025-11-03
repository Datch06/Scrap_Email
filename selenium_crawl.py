#!/usr/bin/env python3
"""Crawl sites avec Selenium + undetected_chromedriver pour récupérer les backlinks externes.

Exemple d'exécution :

    pip install selenium undetected-chromedriver
    python selenium_crawl.py \
        --start https://www.lepetitjournal.com/ \
        --max-pages 150 --max-depth 3 --delay 2.0 \
        --profile /Users/vous/Library/Application\ Support/Google/Chrome \
        --output externals_lepetitjournal.txt --per-site

Notes importantes :
- L'utilisation d'un profil Chrome réel (option --profile) est fortement recommandée pour
  réduire les blocages anti-bot. Fournissez le chemin vers le dossier de profil (et
  éventuellement --profile-name si vous utilisez plusieurs profils).
- Gardez le navigateur ouvert et évitez d'utiliser la souris/clavier pendant le crawl.
- Certains sites peuvent nécessiter une résolution de Captcha ou une authentification :
  laissez le script en pause (Ctrl+C pour arrêter) et relancez quand vous êtes prêt.
"""

from __future__ import annotations

import argparse
import os
import sys
import time
from collections import deque
from pathlib import Path
from typing import Iterable, Set, Tuple
from urllib.parse import urlparse

import certifi
import undetected_chromedriver as uc
from selenium.common.exceptions import WebDriverException, TimeoutException
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.by import By

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


def build_driver(headless: bool, ua: str | None, profile_dir: str | None,
                 profile_name: str | None, chrome_binary: str | None) -> uc.Chrome:
    # Garantit une chaîne de certificats valide pour les téléchargements du patcher
    os.environ.setdefault("SSL_CERT_FILE", certifi.where())
    os.environ.setdefault("REQUESTS_CA_BUNDLE", certifi.where())

    options = Options()
    if headless:
        options.add_argument("--headless=new")
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_argument("--disable-gpu")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--window-size=1365,768")
    if ua:
        options.add_argument(f"--user-agent={ua}")
    if profile_dir:
        options.add_argument(f"--user-data-dir={profile_dir}")
        if profile_name:
            options.add_argument(f"--profile-directory={profile_name}")
    # Réduit les logs bruyants
    options.add_argument("--log-level=3")

    driver = uc.Chrome(options=options, browser_executable_path=chrome_binary)
    driver.set_page_load_timeout(60)
    return driver


def collect_links(driver: uc.Chrome) -> Tuple[Set[str], Set[str]]:
    # Script JS pour récupérer des URLs absolues, en filtrant quelques schémas.
    script = """
        const anchors = Array.from(document.querySelectorAll('a[href]'));
        const origin = window.location.origin;
        const results = [];
        for (const a of anchors) {
            const href = a.getAttribute('href');
            if (!href) continue;
            if (href.startsWith('mailto:') || href.startsWith('tel:') || href.startsWith('javascript:')) continue;
            let absolute;
            try {
                absolute = new URL(href, window.location.href).href;
            } catch (e) {
                continue;
            }
            results.push(absolute);
        }
        return results;
    """
    urls = driver.execute_script(script) or []
    base_host = hostname(driver.current_url)
    internal: Set[str] = set()
    external: Set[str] = set()
    for url in urls:
        if not url:
            continue
        if is_same_site(url, base_host):
            internal.add(url)
        else:
            if not is_social(url):
                external.add(url)
    return internal, external


def crawl(start_urls: Iterable[str], max_pages: int, max_depth: int, delay: float,
          timeout: float, output: Path, per_site_output: bool, headless: bool,
          profile_dir: str | None, profile_name: str | None,
          chrome_binary: str | None) -> None:
    start_urls = list(start_urls)
    if not start_urls:
        print("[ERROR] Aucun URL de départ fourni.", file=sys.stderr)
        return

    driver = build_driver(headless=headless, ua=DEFAULT_USER_AGENT,
                          profile_dir=profile_dir, profile_name=profile_name,
                          chrome_binary=chrome_binary)

    combined_external: Set[str] = set()

    try:
        for start_url in start_urls:
            queue = deque([(start_url, 0)])
            visited: Set[str] = set()
            site_external: Set[str] = set()
            root_host = hostname(start_url)
            print(f"[INFO] Démarrage crawl {start_url} (host={root_host})")

            while queue and len(visited) < max_pages:
                url, depth = queue.popleft()
                if url in visited or depth > max_depth:
                    continue
                try:
                    driver.get(url)
                    # Attendre que le DOM soit prêt
                    WebDriverWait(driver, timeout).until(
                        EC.presence_of_element_located((By.TAG_NAME, "body"))
                    )
                except (WebDriverException, TimeoutException) as exc:
                    print(f"  [WARN] Impossible de charger {url}: {exc}")
                    continue

                visited.add(url)
                try:
                    internal_links, external_links = collect_links(driver)
                except WebDriverException as exc:
                    print(f"  [WARN] Extraction échouée sur {url}: {exc}")
                    internal_links, external_links = set(), set()

                for link in external_links:
                    if link not in combined_external:
                        print(f"    [EXT] {link}")
                        combined_external.add(link)
                        site_external.add(link)

                for link in internal_links:
                    if link not in visited:
                        queue.append((link, depth + 1))

                if delay:
                    time.sleep(delay)

            if per_site_output:
                site_file = output.parent / f"externals_{root_host.replace('.', '_')}.txt"
                with site_file.open("w", encoding="utf-8") as f:
                    for link in sorted(site_external):
                        f.write(link + "\n")
                print(f"  [INFO] Écriture {len(site_external)} liens → {site_file}")

    finally:
        driver.quit()

    with output.open("w", encoding="utf-8") as f:
        for link in sorted(combined_external):
            f.write(link + "\n")
    print(f"[INFO] Total liens externes uniques: {len(combined_external)} (fichier: {output})")


def parse_args(argv: Iterable[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Crawl Selenium pour backlinks externes")
    parser.add_argument("--start", nargs="+", required=True,
                        help="URL(s) de départ, ex: https://www.lepetitjournal.com/")
    parser.add_argument("--max-pages", type=int, default=200,
                        help="Nombre maxi de pages par site (défaut: 200)")
    parser.add_argument("--max-depth", type=int, default=3,
                        help="Profondeur maxi (défaut: 3)")
    parser.add_argument("--delay", type=float, default=1.0,
                        help="Pause en secondes entre pages (défaut: 1.0)")
    parser.add_argument("--timeout", type=float, default=20.0,
                        help="Délai max d'attente pour le chargement (défaut: 20s)")
    parser.add_argument("--output", type=Path, default=Path("external_links.txt"),
                        help="Fichier de sortie global (défaut: external_links.txt)")
    parser.add_argument("--per-site", action="store_true",
                        help="Écrit aussi un fichier par site")
    parser.add_argument("--headless", action="store_true",
                        help="Force le mode headless (défaut: fenêtre visible)")
    parser.add_argument("--profile", help="Chemin vers le dossier user-data Chrome")
    parser.add_argument("--profile-name", help="Nom du profil Chrome (ex: 'Profile 1')")
    parser.add_argument("--chrome-binary", help="Chemin vers l'exécutable Chrome")
    return parser.parse_args(argv)


def main(argv: Iterable[str]) -> None:
    args = parse_args(argv)
    crawl(start_urls=args.start,
          max_pages=args.max_pages,
          max_depth=args.max_depth,
          delay=args.delay,
          timeout=args.timeout,
          output=args.output,
          per_site_output=args.per_site,
          headless=args.headless,
          profile_dir=args.profile,
          profile_name=args.profile_name,
          chrome_binary=args.chrome_binary)


if __name__ == "__main__":
    main(sys.argv[1:])
