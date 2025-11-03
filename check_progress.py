#!/usr/bin/env python3
"""
Script pour vérifier la progression du retry
"""
import json
import re

RESULTS_FILE = 'feuille2_results.json'

# Charger les résultats
with open(RESULTS_FILE, 'r', encoding='utf-8') as f:
    results = json.load(f)

# Statistiques
total = len(results)
siret_valide = sum(1 for v in results.values() if v.get('siret') not in ['NON TROUVÉ', '', None])
siret_non_trouve = sum(1 for v in results.values() if v.get('siret') == 'NON TROUVÉ')
dirigeants_trouve = sum(1 for v in results.values() if v.get('dirigeants') and v.get('dirigeants').strip() and v.get('dirigeants') != 'NON TROUVÉ')

print("=" * 70)
print("PROGRESSION DU SCRAPING")
print("=" * 70)
print(f"Total domaines: {total}")
print(f"SIRET valides trouvés: {siret_valide} ({siret_valide*100/total:.1f}%)")
print(f"SIRET non trouvés: {siret_non_trouve} ({siret_non_trouve*100/total:.1f}%)")
print(f"Dirigeants trouvés: {dirigeants_trouve} ({dirigeants_trouve*100/total:.1f}%)")
print("=" * 70)

# Vérifier le log
try:
    with open('retry_failed.log', 'r') as f:
        log_content = f.read()

    # Trouver la dernière ligne de progression
    matches = re.findall(r'\[(\d+)/(\d+)\]', log_content)
    if matches:
        current, total_retry = matches[-1]
        print(f"\nProgression du retry: {current}/{total_retry}")

        # Compter les nouveaux trouvés dans le log
        new_found = log_content.count('✓ SIRET:') + log_content.count('✓ SIREN:')
        print(f"Nouveaux SIRET trouvés dans ce run: {new_found}")
except FileNotFoundError:
    print("\nAucun retry en cours")
