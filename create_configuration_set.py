#!/usr/bin/env python3
"""
Créer automatiquement le Configuration Set dans AWS SES
"""

import boto3
from botocore.exceptions import ClientError
from aws_config import AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY, AWS_REGION

def create_configuration_set():
    """Créer le Configuration Set email-campaign-tracking"""

    print("=" * 70)
    print("🔧 CRÉATION DU CONFIGURATION SET AWS SES")
    print("=" * 70)
    print()

    client = boto3.client(
        'ses',
        aws_access_key_id=AWS_ACCESS_KEY_ID,
        aws_secret_access_key=AWS_SECRET_ACCESS_KEY,
        region_name=AWS_REGION
    )

    config_set_name = 'email-campaign-tracking'

    # 1. Créer le Configuration Set
    print(f"1️⃣ Création du Configuration Set '{config_set_name}'...")
    try:
        client.create_configuration_set(
            ConfigurationSet={
                'Name': config_set_name
            }
        )
        print(f"   ✅ Configuration Set créé avec succès")
    except ClientError as e:
        if e.response['Error']['Code'] == 'ConfigurationSetAlreadyExists':
            print(f"   ℹ️  Configuration Set existe déjà")
        else:
            print(f"   ❌ Erreur: {e.response['Error']['Message']}")
            return False

    print()

    # 2. Lister les SNS topics pour trouver le bon
    print("2️⃣ Recherche du topic SNS...")

    sns_client = boto3.client(
        'sns',
        aws_access_key_id=AWS_ACCESS_KEY_ID,
        aws_secret_access_key=AWS_SECRET_ACCESS_KEY,
        region_name=AWS_REGION
    )

    try:
        topics = sns_client.list_topics()
        sns_topic_arn = None

        for topic in topics.get('Topics', []):
            if 'ses-notifications' in topic['TopicArn'].lower() or 'perfectcoconseo' in topic['TopicArn'].lower():
                sns_topic_arn = topic['TopicArn']
                print(f"   ✅ Topic SNS trouvé: {sns_topic_arn}")
                break

        if not sns_topic_arn:
            print("   ⚠️  Aucun topic SNS trouvé")
            print("   📋 Topics disponibles:")
            for topic in topics.get('Topics', []):
                print(f"      - {topic['TopicArn']}")
            print()
            print("   Veuillez entrer l'ARN du topic SNS à utiliser:")
            sns_topic_arn = input("   > ").strip()

    except ClientError as e:
        print(f"   ❌ Erreur SNS: {e.response['Error']['Message']}")
        return False

    if not sns_topic_arn:
        print("   ❌ Pas de topic SNS configuré")
        return False

    print()

    # 3. Créer Event Destination pour Bounces et Complaints
    print("3️⃣ Création Event Destination: Bounces & Complaints...")
    try:
        client.create_configuration_set_event_destination(
            ConfigurationSetName=config_set_name,
            EventDestination={
                'Name': 'bounces-complaints-destination',
                'Enabled': True,
                'MatchingEventTypes': ['bounce', 'complaint'],
                'SNSDestination': {
                    'TopicARN': sns_topic_arn
                }
            }
        )
        print("   ✅ Event Destination créée (Bounces & Complaints)")
    except ClientError as e:
        if e.response['Error']['Code'] == 'EventDestinationAlreadyExists':
            print("   ℹ️  Event Destination existe déjà")
        else:
            print(f"   ❌ Erreur: {e.response['Error']['Message']}")

    print()

    # 4. Créer Event Destination pour Delivery, Opens, Clicks
    print("4️⃣ Création Event Destination: Delivery, Opens & Clicks...")
    try:
        client.create_configuration_set_event_destination(
            ConfigurationSetName=config_set_name,
            EventDestination={
                'Name': 'tracking-destination',
                'Enabled': True,
                'MatchingEventTypes': ['send', 'delivery', 'open', 'click'],
                'SNSDestination': {
                    'TopicARN': sns_topic_arn
                }
            }
        )
        print("   ✅ Event Destination créée (Delivery, Opens & Clicks)")
    except ClientError as e:
        if e.response['Error']['Code'] == 'EventDestinationAlreadyExists':
            print("   ℹ️  Event Destination existe déjà")
        else:
            print(f"   ❌ Erreur: {e.response['Error']['Message']}")

    print()
    print("=" * 70)
    print("✅ CONFIGURATION SET CRÉÉ ET CONFIGURÉ")
    print("=" * 70)
    print()
    print(f"📋 Configuration Set: {config_set_name}")
    print(f"📡 SNS Topic: {sns_topic_arn}")
    print()
    print("🎉 Vous pouvez maintenant envoyer des emails avec tracking!")
    print()

    return True

if __name__ == '__main__':
    try:
        success = create_configuration_set()
        if success:
            print("✅ Configuration terminée avec succès!")
        else:
            print("❌ Erreur lors de la configuration")
    except Exception as e:
        print(f"❌ Erreur inattendue: {e}")
