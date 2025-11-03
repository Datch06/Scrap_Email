#!/usr/bin/env python3
"""
Test rapide de la validation d'email
"""

from validate_emails import EmailValidator
import json

validator = EmailValidator()

# Emails de test
test_emails = [
    'contact@google.com',  # Email valide
    'invalid@invalid-domain-xyz123.com',  # Domaine invalide
    'test@tempmail.com',  # Email jetable
    'not-an-email',  # Format invalide
]

print("🧪 TEST DE VALIDATION D'EMAILS\n")
print("=" * 80)

for email in test_emails:
    print(f"\n📧 Test: {email}")
    result = validator.validate_email(email)

    status_emoji = {
        'valid': '✅',
        'invalid': '❌',
        'risky': '⚠️',
        'unknown': '❓'
    }.get(result['status'], '❓')

    print(f"{status_emoji} Status: {result['status'].upper()} | Score: {result['score']}/100")
    print(f"   Deliverable: {'Oui' if result['deliverable'] else 'Non'}")
    print(f"   Syntaxe: {result['details']['syntax']['message']}")

    if result['details']['dns']['message']:
        print(f"   DNS: {result['details']['dns']['message']}")

    if result['details']['smtp']['message']:
        print(f"   SMTP: {result['details']['smtp']['message']}")

print("\n" + "=" * 80)
print("✅ Test terminé!")
