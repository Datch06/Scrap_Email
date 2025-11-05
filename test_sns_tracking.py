#!/usr/bin/env python3
"""
Test du système de tracking SNS avec SES Mailbox Simulator
"""

from ses_manager import SESManager
import time
import sys

def test_tracking():
    """Tester tous les types de notifications"""

    print("=" * 70)
    print("🧪 TEST DU SYSTÈME DE TRACKING SNS")
    print("=" * 70)
    print()

    ses = SESManager()

    # Vérifier les quotas
    print("📊 Vérification des quotas...")
    quota = ses.get_send_quota()
    print()

    if quota['remaining_24h'] < 5:
        print("❌ Pas assez de quota restant pour les tests")
        sys.exit(1)

    tests = [
        {
            'name': '✅ Succès (Delivery + potentiellement Open/Click)',
            'email': 'success@simulator.amazonses.com',
            'subject': 'Test Success - Tracking SNS',
            'expected': 'Delivery notification dans ~5-30 secondes'
        },
        {
            'name': '📫 Bounce (Hard Bounce)',
            'email': 'bounce@simulator.amazonses.com',
            'subject': 'Test Bounce - Tracking SNS',
            'expected': 'Bounce notification dans ~5-30 secondes'
        },
        {
            'name': '⚠️ Complaint (Plainte spam)',
            'email': 'complaint@simulator.amazonses.com',
            'subject': 'Test Complaint - Tracking SNS',
            'expected': 'Complaint notification dans ~5-30 secondes'
        },
        {
            'name': '📤 Out of Office (Soft Bounce)',
            'email': 'ooto@simulator.amazonses.com',
            'subject': 'Test Out of Office - Tracking SNS',
            'expected': 'Bounce temporaire dans ~5-30 secondes'
        }
    ]

    sent_emails = []

    print("📧 Envoi des emails de test...")
    print()

    for i, test in enumerate(tests, 1):
        print(f"{i}. {test['name']}")
        print(f"   Destinataire: {test['email']}")

        html_body = f"""
        <html>
        <body>
            <h2>Test de Tracking SNS</h2>
            <p>Cet email teste le système de notifications AWS SNS.</p>
            <p><strong>Type de test:</strong> {test['name']}</p>
            <p><strong>Timestamp:</strong> {time.strftime('%Y-%m-%d %H:%M:%S')}</p>
            <hr>
            <p><small>Email envoyé via SES avec Configuration Set pour tracking</small></p>
        </body>
        </html>
        """

        result = ses.send_email(
            to_email=test['email'],
            subject=test['subject'],
            html_body=html_body
        )

        if result['success']:
            message_id = result['message_id']
            print(f"   ✅ Envoyé - Message ID: {message_id}")
            print(f"   ⏳ Attendu: {test['expected']}")
            sent_emails.append({
                'test': test['name'],
                'message_id': message_id,
                'email': test['email']
            })
        else:
            print(f"   ❌ Erreur: {result.get('error')}")

        print()

        # Pause entre les emails
        if i < len(tests):
            time.sleep(2)

    print("=" * 70)
    print("📊 RÉSUMÉ DES TESTS")
    print("=" * 70)
    print()
    print(f"✅ {len(sent_emails)}/{len(tests)} emails envoyés avec succès")
    print()

    if sent_emails:
        print("📋 Messages envoyés:")
        for email_info in sent_emails:
            print(f"   • {email_info['test']}")
            print(f"     Message ID: {email_info['message_id']}")
        print()

        print("⏰ Les notifications SNS devraient arriver dans 5-30 secondes")
        print()
        print("📝 Pour voir les notifications en temps réel:")
        print("   tail -f /tmp/api_server.log | grep -E 'Bounce|Complaint|Delivery|Open|Click'")
        print()
        print("🌐 Ou consultez l'interface admin:")
        print("   https://admin.perfect-cocon-seo.fr/campaigns")

    print()
    print("=" * 70)

    return sent_emails

if __name__ == '__main__':
    try:
        sent_emails = test_tracking()

        print()
        print("✅ Tests lancés avec succès!")
        print()
        print("🔍 Surveillance des logs pendant 60 secondes...")
        print("   (Appuyez sur Ctrl+C pour arrêter)")
        print()

        # Surveiller les logs pendant 60 secondes
        import subprocess
        try:
            subprocess.run(
                ['timeout', '60', 'tail', '-f', '/tmp/api_server.log'],
                timeout=65
            )
        except (subprocess.TimeoutExpired, KeyboardInterrupt):
            print()
            print("👋 Surveillance arrêtée")

    except KeyboardInterrupt:
        print()
        print("👋 Tests interrompus")
    except Exception as e:
        print(f"❌ Erreur: {e}")
        sys.exit(1)
