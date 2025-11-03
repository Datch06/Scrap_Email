#!/usr/bin/env python3
import re
import ssl
import urllib.request
import tempfile
import os

try:
    from pypdf import PdfReader
    PDF_SUPPORT = True
except ImportError:
    PDF_SUPPORT = False
    print('PDF support not available')

DEFAULT_USER_AGENT = 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36'

def build_opener():
    try:
        ssl_context = ssl.create_default_context()
        ssl_context.check_hostname = False
        ssl_context.verify_mode = ssl.CERT_NONE
    except:
        ssl_context = ssl.create_default_context()
    return urllib.request.build_opener(urllib.request.HTTPSHandler(context=ssl_context))

def fetch_page(url, opener):
    try:
        req = urllib.request.Request(url, headers={'User-Agent': DEFAULT_USER_AGENT})
        with opener.open(req, timeout=15) as resp:
            data = resp.read()
            return data.decode('utf-8', errors='replace')
    except Exception as e:
        return None

def fetch_and_extract_pdf(url, opener):
    if not PDF_SUPPORT:
        return None
    try:
        req = urllib.request.Request(url, headers={'User-Agent': DEFAULT_USER_AGENT})
        with opener.open(req, timeout=15) as resp:
            content_type = resp.headers.get('Content-Type', '')
            if 'pdf' not in content_type.lower():
                return None

            with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as tmp:
                tmp.write(resp.read())
                tmp_path = tmp.name

            reader = PdfReader(tmp_path)
            text = ''
            for page in reader.pages:
                text += page.extract_text() + ' '

            os.unlink(tmp_path)
            return text
    except Exception as e:
        print(f'PDF Error: {e}')
        return None

def search_siret_in_text(text):
    SIRET_WORD_PATTERN = re.compile(r'\bSIRET\s*:?\s*([\d\s\t]{14,20})', re.IGNORECASE)
    SIREN_PATTERN = re.compile(r'\bSIREN\s*:?\s*([\d\s\t]{9,15})', re.IGNORECASE)
    RCS_PATTERN = re.compile(r"\bsous le num[eé]ro\s+[A-Z]?\s*([\d\s\t]{9,20})", re.IGNORECASE)

    patterns = [
        (SIRET_WORD_PATTERN, 'SIRET'),
        (SIREN_PATTERN, 'SIREN'),
        (RCS_PATTERN, 'RCS')
    ]

    for pattern, name in patterns:
        match = pattern.search(text)
        if match:
            number = match.group(1).replace(' ', '').replace('\xa0', '').replace('\t', '')
            if len(number) in [9, 14] and number.isdigit():
                return number, name

    return None, None

# Test editions-bordas.fr
domain = 'www.editions-bordas.fr'
opener = build_opener()

print(f'Testing {domain}...\n')

pages = ['/mentions-legales', '/cgv', '/cgu', '/legal']

siret = None
found_type = None

for page_path in pages:
    url = f'https://{domain}{page_path}'
    print(f'Checking {url}...')

    html = fetch_page(url, opener)
    if html:
        # Check for SIRET in HTML
        siret, found_type = search_siret_in_text(html)
        if siret:
            print(f'  ✓ Found {found_type}: {siret}')
            break

        # Check for PDF links
        pdf_pattern = r'href=["\']([^"\']*\.pdf[^"\']*)["\']'

        pdf_matches = re.findall(pdf_pattern, html)
        for pdf_url in pdf_matches[:3]:
            if not pdf_url.startswith('http'):
                pdf_url = f'https://{domain}{pdf_url}'

            print(f'  📄 Found PDF: {pdf_url}')
            pdf_text = fetch_and_extract_pdf(pdf_url, opener)
            if pdf_text:
                siret, found_type = search_siret_in_text(pdf_text)
                if siret:
                    print(f'    ✓ Found {found_type} in PDF: {siret}')
                    break
        if siret:
            break

    if siret:
        break

if not siret:
    print('\n✗ SIRET not found')
else:
    print(f'\n✓ Result: {found_type} = {siret}')
