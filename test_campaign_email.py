#!/usr/bin/env python3
"""
Script de test pour envoyer des emails de test de campagne
"""

import requests
from requests.auth import HTTPBasicAuth
import json

# Configuration
API_URL = 'http://127.0.0.1:5002'
AUTH = HTTPBasicAuth('Datch', '0000cn')

def test_campaign_email():
    """Test d'envoi d'email de campagne"""

    print("=" * 70)
    print("TEST D'ENVOI D'EMAIL DE CAMPAGNE")
    print("=" * 70)

    # 1. Lister les campagnes existantes
    print("\n[1/3] Récupération des campagnes...")
    resp = requests.get(f'{API_URL}/api/campaigns', auth=AUTH, timeout=10)

    if resp.status_code != 200:
        print(f"❌ Erreur: {resp.status_code}")
        return

    campaigns = resp.json()

    if not campaigns:
        print("❌ Aucune campagne trouvée. Créez d'abord une campagne.")
        print("\nPour créer une campagne, utilisez l'interface web:")
        print("  https://admin.perfect-cocon-seo.fr/campaigns")
        return

    print(f"✓ {len(campaigns)} campagne(s) trouvée(s)")

    # Afficher les campagnes
    print("\nCampagnes disponibles:")
    for idx, campaign in enumerate(campaigns, 1):
        print(f"  {idx}. ID {campaign['id']}: {campaign['name']}")
        print(f"     Statut: {campaign.get('status', 'N/A')}")
        print(f"     Sujet: {campaign.get('subject', 'N/A')}")

    # 2. Demander quelle campagne tester
    campaign_id = None

    if len(campaigns) == 1:
        campaign_id = campaigns[0]['id']
        print(f"\n✓ Utilisation de la campagne ID {campaign_id}")
    else:
        try:
            choice = int(input("\nChoisissez le numéro de campagne à tester: "))
            if 1 <= choice <= len(campaigns):
                campaign_id = campaigns[choice - 1]['id']
            else:
                print("❌ Numéro invalide")
                return
        except (ValueError, KeyboardInterrupt):
            print("\n❌ Annulé")
            return

    # 3. Demander les emails de test
    print("\n[2/3] Configuration des emails de test...")
    print("Entrez les adresses email de test (séparées par des virgules):")
    print("Exemple: votre.email@example.com, autre@example.com")

    try:
        email_input = input("Emails: ").strip()
        test_emails = [e.strip() for e in email_input.split(',') if e.strip()]

        if not test_emails:
            print("❌ Aucune adresse email fournie")
            return

        print(f"✓ {len(test_emails)} email(s) de test configuré(s)")

    except KeyboardInterrupt:
        print("\n❌ Annulé")
        return

    # 4. Envoyer les emails de test
    print(f"\n[3/3] Envoi des emails de test...")

    payload = {
        'test_emails': test_emails,
        'test_domain': 'site-test-exemple.fr'
    }

    resp = requests.post(
        f'{API_URL}/api/campaigns/{campaign_id}/test',
        auth=AUTH,
        json=payload,
        timeout=30
    )

    if resp.status_code != 200:
        print(f"❌ Erreur: {resp.status_code}")
        print(f"   {resp.text}")
        return

    results = resp.json()

    # Afficher les résultats
    print("\n" + "=" * 70)
    print("RÉSULTATS D'ENVOI")
    print("=" * 70)
    print(f"Campagne: {results['campaign_name']}")
    print(f"Envoyés: {results['total_sent']}")
    print(f"Échoués: {results['total_failed']}")

    if results['sent']:
        print(f"\n✅ Emails envoyés avec succès:")
        for email in results['sent']:
            print(f"   - {email}")

    if results['failed']:
        print(f"\n❌ Emails échoués:")
        for item in results['failed']:
            if isinstance(item, dict):
                print(f"   - {item['email']}: {item['error']}")
            else:
                print(f"   - {item}")

    print("\n✓ Test terminé!")
    print("\nVérifiez votre boîte de réception (incluant spam/promotions)")
    print("Le sujet de l'email commence par [TEST]")
    print("=" * 70)


if __name__ == '__main__':
    try:
        test_campaign_email()
    except Exception as e:
        print(f"\n❌ Erreur: {e}")
