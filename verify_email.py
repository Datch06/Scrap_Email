#!/usr/bin/env python3
"""
Vérifier l'email expéditeur dans SES
"""

from ses_manager import SESManager

def verify_sender_email():
    """Vérifier l'email expéditeur"""
    print("=" * 70)
    print("📧 VÉRIFICATION DE L'EMAIL EXPÉDITEUR")
    print("=" * 70)
    print()

    manager = SESManager()

    print(f"Email à vérifier: {manager.sender_email}")
    print()

    # Vérifier le statut actuel
    print("1️⃣ Vérification du statut actuel...")
    status = manager.check_verification_status(manager.sender_email)

    if status == 'Success':
        print(f"✅ Email {manager.sender_email} déjà vérifié!")
        return True
    elif status == 'Pending':
        print(f"⏳ Email {manager.sender_email} en attente de vérification")
        print("   Vérifiez votre boîte mail et cliquez sur le lien")
        return False
    else:
        print(f"❌ Email {manager.sender_email} non vérifié")
        print()
        print("2️⃣ Envoi de la demande de vérification...")

        if manager.verify_email(manager.sender_email):
            print()
            print("=" * 70)
            print("✅ EMAIL DE VÉRIFICATION ENVOYÉ!")
            print("=" * 70)
            print()
            print(f"📧 Vérifiez la boîte mail de: {manager.sender_email}")
            print("   (vérifiez aussi les spams)")
            print()
            print("🔗 Cliquez sur le lien dans l'email pour vérifier l'adresse")
            print()
            print("⏱️  Une fois vérifié, relancez ce script ou testez l'envoi")
            return False
        else:
            print("❌ Échec de l'envoi de la demande")
            return False

if __name__ == '__main__':
    verify_sender_email()
