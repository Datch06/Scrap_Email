#!/usr/bin/env python3
from playwright.sync_api import sync_playwright
import time

with sync_playwright() as p:
    browser = p.chromium.launch(headless=False)  # Mode visible
    context = browser.new_context(
        user_agent='Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'
    )
    page = context.new_page()

    try:
        print('Chargement de pappers.fr...')
        page.goto('https://www.pappers.fr/entreprise/amazon-france-services-sas-440272675', timeout=30000)

        # Attendre que la page charge
        time.sleep(10)

        text = page.inner_text('body')

        print(f'\nLongueur du texte: {len(text)} caractères')

        if 'just a moment' in text.lower():
            print('✗ Protection Cloudflare détectée')
        elif 'amazon' in text.lower():
            print('✓ Page chargée correctement')

            # Chercher dirigeants
            if 'dirigeant' in text.lower():
                print('\n✓ Section dirigeants trouvée:')
                lines = text.split('\n')
                for i, line in enumerate(lines):
                    if 'dirigeant' in line.lower() and i < len(lines) - 5:
                        for j in range(5):
                            print(f'  {lines[i+j].strip()}')
                        break
        else:
            print('✗ Contenu inattendu')
            print(text[:500])

    except Exception as e:
        print(f'✗ Erreur: {e}')
    finally:
        input('Appuyez sur Entrée pour fermer...')
        browser.close()
