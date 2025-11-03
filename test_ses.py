#!/usr/bin/env python3
"""
Script de test pour Amazon SES
"""

from ses_manager import SESManager
import sys

def test_simple_email():
    """Test d'envoi d'un email simple"""
    print("=" * 70)
    print("🧪 TEST D'ENVOI D'EMAIL AVEC AMAZON SES")
    print("=" * 70)
    print()

    # Demander l'email de test
    print("📧 Entrez l'adresse email pour le test:")
    print("   (en sandbox mode, cet email doit être vérifié dans SES)")
    test_email = input("   > ").strip()

    if not test_email or '@' not in test_email:
        print("❌ Email invalide")
        return

    # Créer le manager
    try:
        manager = SESManager()
    except ValueError as e:
        print(f"❌ {e}")
        print("\n📝 Configurez d'abord aws_config.py avec vos credentials")
        return

    # Vérifier les quotas
    print("\n1️⃣ Vérification des quotas...")
    quota = manager.get_send_quota()

    if quota.get('remaining_24h', 0) == 0:
        print("❌ Quota quotidien atteint!")
        return

    # Vérifier le statut de l'email de test
    print(f"\n2️⃣ Vérification de {test_email}...")
    status = manager.check_verification_status(test_email)

    if status not in ['Success', 'NotFound']:
        print(f"⏳ Email en attente de vérification")
        print("   Vérifiez votre boîte mail et cliquez sur le lien de vérification")
        return
    elif status == 'NotFound':
        print(f"❌ Email {test_email} non vérifié")
        print("   En mode sandbox, vous devez vérifier cet email d'abord")
        print("\nVoulez-vous envoyer une demande de vérification? (o/n)")
        response = input("   > ")
        if response.lower() == 'o':
            manager.verify_email(test_email)
            print("\n✅ Email de vérification envoyé!")
            print("   Vérifiez votre boîte mail et relancez ce test")
        return

    # Préparer l'email de test
    print(f"\n3️⃣ Envoi de l'email de test à {test_email}...")

    subject = "🧪 Test Amazon SES - Scrap Email Manager"

    html_body = """
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <style>
            body { font-family: Arial, sans-serif; line-height: 1.6; color: #333; }
            .container { max-width: 600px; margin: 0 auto; padding: 20px; }
            .header { background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 30px; text-align: center; border-radius: 10px 10px 0 0; }
            .content { background: #f9f9f9; padding: 30px; border-radius: 0 0 10px 10px; }
            .success { background: #d4edda; border-left: 4px solid #28a745; padding: 15px; margin: 20px 0; }
            .footer { text-align: center; margin-top: 30px; color: #666; font-size: 12px; }
            .button { display: inline-block; padding: 12px 30px; background: #667eea; color: white; text-decoration: none; border-radius: 5px; margin-top: 20px; }
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1>✅ Test Amazon SES Réussi!</h1>
            </div>
            <div class="content">
                <div class="success">
                    <strong>🎉 Félicitations!</strong><br>
                    Votre configuration Amazon SES fonctionne correctement.
                </div>

                <h2>📊 Informations</h2>
                <ul>
                    <li><strong>Service:</strong> Amazon Simple Email Service (SES)</li>
                    <li><strong>Région:</strong> """ + manager.region + """</li>
                    <li><strong>Expéditeur:</strong> """ + manager.sender_email + """</li>
                    <li><strong>Date:</strong> """ + str(manager.client.meta.config.__dict__.get('user_agent', 'N/A')) + """</li>
                </ul>

                <h2>🚀 Prochaines étapes</h2>
                <ol>
                    <li>Demander la sortie du sandbox mode (si nécessaire)</li>
                    <li>Configurer le tracking des emails</li>
                    <li>Créer vos premières campagnes</li>
                    <li>Envoyer des emails à vos prospects</li>
                </ol>

                <p style="text-align: center;">
                    <a href="https://admin.perfect-cocon-seo.fr" class="button">
                        Accéder au Dashboard
                    </a>
                </p>
            </div>
            <div class="footer">
                <p>Email envoyé par Scrap Email Manager</p>
                <p>Propulsé par Amazon SES</p>
            </div>
        </div>
    </body>
    </html>
    """

    text_body = """
    ✅ Test Amazon SES Réussi!

    🎉 Félicitations! Votre configuration Amazon SES fonctionne correctement.

    📊 Informations:
    - Service: Amazon Simple Email Service (SES)
    - Région: """ + manager.region + """
    - Expéditeur: """ + manager.sender_email + """

    🚀 Prochaines étapes:
    1. Demander la sortie du sandbox mode (si nécessaire)
    2. Configurer le tracking des emails
    3. Créer vos premières campagnes
    4. Envoyer des emails à vos prospects

    ---
    Email envoyé par Scrap Email Manager
    Propulsé par Amazon SES
    """

    # Envoyer
    success = manager.send_email(
        to_email=test_email,
        subject=subject,
        html_body=html_body,
        text_body=text_body
    )

    if success:
        print("\n" + "=" * 70)
        print("✅ EMAIL DE TEST ENVOYÉ AVEC SUCCÈS!")
        print("=" * 70)
        print(f"\n📧 Vérifiez la boîte mail de {test_email}")
        print("   (vérifiez aussi les spams si besoin)")
        print("\n🎉 Amazon SES fonctionne correctement!")
        print("\n📝 Prochaines étapes:")
        print("   1. Demandez la sortie du sandbox:")
        print("      https://console.aws.amazon.com/ses")
        print("   2. Lancez le système de campagnes")
    else:
        print("\n" + "=" * 70)
        print("❌ ÉCHEC DE L'ENVOI")
        print("=" * 70)
        print("\n💡 Vérifiez:")
        print("   1. Vos credentials AWS dans aws_config.py")
        print("   2. Que l'email expéditeur est vérifié dans SES")
        print("   3. Que l'email destinataire est vérifié (en sandbox mode)")


if __name__ == '__main__':
    test_simple_email()
