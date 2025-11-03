#!/usr/bin/env python3
"""
Module de détection de CMS (Content Management System)
Détecte WordPress, Joomla, Drupal, PrestaShop, Shopify, Wix, etc.
"""

import requests
import re
from bs4 import BeautifulSoup
from urllib.parse import urljoin
import time


class CMSDetector:
    """Détecteur de CMS pour sites web"""

    def __init__(self, timeout=10, user_agent=None):
        self.timeout = timeout
        self.user_agent = user_agent or 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        self.session = requests.Session()
        self.session.headers.update({'User-Agent': self.user_agent})

    def detect(self, domain):
        """
        Détecte le CMS utilisé par un domaine

        Args:
            domain: Nom de domaine (sans http://)

        Returns:
            dict: {'cms': 'WordPress', 'version': '6.4', 'confidence': 'high'}
        """
        # Normaliser le domaine
        if not domain.startswith('http'):
            urls = [f'https://{domain}', f'http://{domain}']
        else:
            urls = [domain]

        html = None
        headers = None
        final_url = None

        # Essayer de récupérer la page
        for url in urls:
            try:
                response = self.session.get(url, timeout=self.timeout, allow_redirects=True)
                if response.status_code == 200:
                    html = response.text
                    headers = response.headers
                    final_url = response.url
                    break
            except:
                continue

        if not html:
            return {'cms': None, 'version': None, 'confidence': 'none'}

        # Détection par ordre de popularité
        detectors = [
            self._detect_wordpress,
            self._detect_shopify,
            self._detect_wix,
            self._detect_prestashop,
            self._detect_joomla,
            self._detect_drupal,
            self._detect_squarespace,
            self._detect_magento,
            self._detect_spip,
            self._detect_typo3,
            self._detect_dotclear,
            self._detect_webflow,
        ]

        for detector in detectors:
            result = detector(html, headers, final_url)
            if result['cms']:
                return result

        # Aucun CMS détecté
        return {'cms': 'Custom/Unknown', 'version': None, 'confidence': 'low'}

    def _detect_wordpress(self, html, headers, url):
        """Détecte WordPress"""
        confidence = 'none'
        version = None

        # Signatures WordPress
        wp_signs = [
            'wp-content',
            'wp-includes',
            'wp-json',
            '/wp-admin/',
            'wordpress',
        ]

        matches = sum(1 for sign in wp_signs if sign.lower() in html.lower())

        if matches >= 2:
            confidence = 'high'

            # Essayer de détecter la version
            # Meta generator
            match = re.search(r'<meta name="generator" content="WordPress ([0-9.]+)"', html, re.IGNORECASE)
            if match:
                version = match.group(1)

            # Version dans le code source
            if not version:
                match = re.search(r'wp-includes/.*ver=([0-9.]+)', html)
                if match:
                    version = match.group(1)

        if confidence != 'none':
            return {'cms': 'WordPress', 'version': version, 'confidence': confidence}

        return {'cms': None, 'version': None, 'confidence': 'none'}

    def _detect_joomla(self, html, headers, url):
        """Détecte Joomla"""
        confidence = 'none'
        version = None

        joomla_signs = [
            '/components/com_',
            '/modules/mod_',
            'joomla',
            'com_content',
            'option=com_',
        ]

        matches = sum(1 for sign in joomla_signs if sign.lower() in html.lower())

        if matches >= 2:
            confidence = 'high'

            # Version
            match = re.search(r'<meta name="generator" content="Joomla! - Open Source Content Management - Version ([0-9.]+)"', html, re.IGNORECASE)
            if match:
                version = match.group(1)

        if confidence != 'none':
            return {'cms': 'Joomla', 'version': version, 'confidence': confidence}

        return {'cms': None, 'version': None, 'confidence': 'none'}

    def _detect_drupal(self, html, headers, url):
        """Détecte Drupal"""
        confidence = 'none'
        version = None

        drupal_signs = [
            'Drupal.settings',
            'sites/all/modules',
            'sites/all/themes',
            '/misc/drupal.js',
            'X-Generator' in headers and 'Drupal' in headers.get('X-Generator', ''),
        ]

        matches = sum(1 for sign in drupal_signs if (isinstance(sign, str) and sign.lower() in html.lower()) or sign is True)

        if matches >= 2:
            confidence = 'high'

            # Version
            match = re.search(r'Drupal ([0-9.]+)', html, re.IGNORECASE)
            if match:
                version = match.group(1)

        if confidence != 'none':
            return {'cms': 'Drupal', 'version': version, 'confidence': confidence}

        return {'cms': None, 'version': None, 'confidence': 'none'}

    def _detect_prestashop(self, html, headers, url):
        """Détecte PrestaShop"""
        confidence = 'none'
        version = None

        prestashop_signs = [
            'prestashop',
            '/modules/ps_',
            'var prestashop',
            'content="PrestaShop"',
        ]

        matches = sum(1 for sign in prestashop_signs if sign.lower() in html.lower())

        if matches >= 2:
            confidence = 'high'

        if confidence != 'none':
            return {'cms': 'PrestaShop', 'version': version, 'confidence': confidence}

        return {'cms': None, 'version': None, 'confidence': 'none'}

    def _detect_shopify(self, html, headers, url):
        """Détecte Shopify"""
        confidence = 'none'

        shopify_signs = [
            'cdn.shopify.com',
            'Shopify.theme',
            'shopify-section',
            'myshopify.com',
        ]

        matches = sum(1 for sign in shopify_signs if sign.lower() in html.lower())

        if matches >= 1:
            confidence = 'high'
            return {'cms': 'Shopify', 'version': None, 'confidence': confidence}

        return {'cms': None, 'version': None, 'confidence': 'none'}

    def _detect_wix(self, html, headers, url):
        """Détecte Wix"""
        confidence = 'none'

        wix_signs = [
            'wix.com',
            'wixstatic.com',
            'X-Wix-',
        ]

        matches = sum(1 for sign in wix_signs if sign.lower() in html.lower() or sign in str(headers))

        if matches >= 1:
            confidence = 'high'
            return {'cms': 'Wix', 'version': None, 'confidence': confidence}

        return {'cms': None, 'version': None, 'confidence': 'none'}

    def _detect_squarespace(self, html, headers, url):
        """Détecte Squarespace"""
        confidence = 'none'

        if 'squarespace' in html.lower() or 'squarespace' in str(headers).lower():
            confidence = 'high'
            return {'cms': 'Squarespace', 'version': None, 'confidence': confidence}

        return {'cms': None, 'version': None, 'confidence': 'none'}

    def _detect_magento(self, html, headers, url):
        """Détecte Magento"""
        confidence = 'none'
        version = None

        magento_signs = [
            'Mage.Cookies',
            'skin/frontend/',
            'magento',
            '/mage/',
        ]

        matches = sum(1 for sign in magento_signs if sign.lower() in html.lower())

        if matches >= 2:
            confidence = 'high'

        if confidence != 'none':
            return {'cms': 'Magento', 'version': version, 'confidence': confidence}

        return {'cms': None, 'version': None, 'confidence': 'none'}

    def _detect_spip(self, html, headers, url):
        """Détecte SPIP"""
        confidence = 'none'
        version = None

        spip_signs = [
            'spip.php',
            'squelettes/',
            'X-Spip-Cache' in headers,
            'composed by SPIP',
        ]

        matches = sum(1 for sign in spip_signs if (isinstance(sign, str) and sign.lower() in html.lower()) or sign is True)

        if matches >= 1:
            confidence = 'high'

            match = re.search(r'SPIP ([0-9.]+)', html, re.IGNORECASE)
            if match:
                version = match.group(1)

        if confidence != 'none':
            return {'cms': 'SPIP', 'version': version, 'confidence': confidence}

        return {'cms': None, 'version': None, 'confidence': 'none'}

    def _detect_typo3(self, html, headers, url):
        """Détecte TYPO3"""
        confidence = 'none'

        if 'typo3' in html.lower() or 'typo3' in str(headers).lower():
            confidence = 'high'
            return {'cms': 'TYPO3', 'version': None, 'confidence': confidence}

        return {'cms': None, 'version': None, 'confidence': 'none'}

    def _detect_dotclear(self, html, headers, url):
        """Détecte Dotclear"""
        confidence = 'none'

        if 'dotclear' in html.lower():
            confidence = 'high'
            return {'cms': 'Dotclear', 'version': None, 'confidence': confidence}

        return {'cms': None, 'version': None, 'confidence': 'none'}

    def _detect_webflow(self, html, headers, url):
        """Détecte Webflow"""
        confidence = 'none'

        if 'webflow' in html.lower() or 'assets.website-files.com' in html.lower():
            confidence = 'high'
            return {'cms': 'Webflow', 'version': None, 'confidence': confidence}

        return {'cms': None, 'version': None, 'confidence': 'none'}


if __name__ == '__main__':
    # Test
    detector = CMSDetector()

    test_sites = [
        'wordpress.org',
        'joomla.org',
        'drupal.org',
    ]

    for site in test_sites:
        print(f"\nTest: {site}")
        result = detector.detect(site)
        print(f"  CMS: {result['cms']}")
        print(f"  Version: {result['version']}")
        print(f"  Confiance: {result['confidence']}")
