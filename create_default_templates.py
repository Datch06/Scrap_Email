#!/usr/bin/env python3
"""
Créer les templates d'emails par défaut
"""

from campaign_database import get_campaign_session, EmailTemplate
import json

def create_default_templates():
    """Créer les templates par défaut"""
    session = get_campaign_session()

    templates = [
        {
            'name': 'Proposition de Backlink Simple',
            'category': 'prospection',
            'description': 'Template simple pour proposer un échange de backlinks',
            'subject': 'Collaboration SEO - {{domain}}',
            'html_body': '''<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <style>
        body { font-family: Arial, sans-serif; line-height: 1.6; color: #333; }
        .container { max-width: 600px; margin: 0 auto; padding: 20px; }
        .button { display: inline-block; padding: 12px 24px; background: #667eea; color: white; text-decoration: none; border-radius: 5px; margin: 20px 0; }
        .footer { margin-top: 40px; padding-top: 20px; border-top: 1px solid #eee; font-size: 12px; color: #666; }
    </style>
</head>
<body>
    <div class="container">
        <h2>Bonjour,</h2>

        <p>Je m'appelle David et je travaille pour Perfect Cocon SEO.</p>

        <p>J'ai découvert votre site <strong>{{domain}}</strong> et j'ai trouvé votre contenu très intéressant.</p>

        <p>Je vous contacte car nous proposons des échanges de backlinks de qualité qui pourraient être bénéfiques pour nos deux sites en termes de référencement.</p>

        <h3>Ce que je propose :</h3>
        <ul>
            <li>Un backlink depuis un site de qualité avec un bon DA/PA</li>
            <li>Contenu pertinent et contextualisé</li>
            <li>Lien en DoFollow</li>
        </ul>

        <p>Seriez-vous intéressé(e) par un échange ou une collaboration ?</p>

        <p>
            <a href="mailto:david@perfect-cocon-seo.fr" class="button">Répondre à cette proposition</a>
        </p>

        <p>Cordialement,<br>
        David<br>
        Perfect Cocon SEO</p>

        <div class="footer">
            <p>Vous recevez cet email car nous pensons que notre proposition pourrait vous intéresser.</p>
            <p><a href="{{unsubscribe_link}}">Se désabonner</a></p>
        </div>
    </div>
</body>
</html>''',
            'text_body': '''Bonjour,

Je m'appelle David et je travaille pour Perfect Cocon SEO.

J'ai découvert votre site {{domain}} et j'ai trouvé votre contenu très intéressant.

Je vous contacte car nous proposons des échanges de backlinks de qualité qui pourraient être bénéfiques pour nos deux sites en termes de référencement.

Ce que je propose :
- Un backlink depuis un site de qualité avec un bon DA/PA
- Contenu pertinent et contextualisé
- Lien en DoFollow

Seriez-vous intéressé(e) par un échange ou une collaboration ?

Répondez-moi à : david@perfect-cocon-seo.fr

Cordialement,
David
Perfect Cocon SEO

---
Pour vous désabonner : {{unsubscribe_link}}''',
            'available_variables': json.dumps(['domain', 'email', 'siret', 'leaders'])
        },
        {
            'name': 'Proposition de Backlink Personnalisée',
            'category': 'prospection',
            'description': 'Template avec plus de personnalisation',
            'subject': 'Opportunité de collaboration SEO pour {{domain}}',
            'html_body': '''<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <style>
        body { font-family: Arial, sans-serif; line-height: 1.6; color: #333; }
        .container { max-width: 600px; margin: 0 auto; padding: 20px; background: #f9f9f9; }
        .content { background: white; padding: 30px; border-radius: 8px; }
        .highlight { background: #fff3cd; padding: 15px; border-left: 4px solid #ffc107; margin: 20px 0; }
        .button { display: inline-block; padding: 12px 24px; background: #28a745; color: white; text-decoration: none; border-radius: 5px; margin: 20px 0; }
        .footer { margin-top: 40px; padding-top: 20px; border-top: 1px solid #eee; font-size: 12px; color: #666; text-align: center; }
    </style>
</head>
<body>
    <div class="container">
        <div class="content">
            <h2>Bonjour,</h2>

            <p>Je suis David de Perfect Cocon SEO, et je suis tombé sur votre site <strong>{{domain}}</strong>.</p>

            <p>J'ai particulièrement apprécié la qualité de votre contenu et je pense que nous pourrions établir un partenariat mutuellement bénéfique.</p>

            <div class="highlight">
                <strong>🎯 Mon objectif :</strong> Créer des partenariats de qualité avec des sites pertinents pour améliorer le référencement de chacun.
            </div>

            <h3>💡 Ce que je propose :</h3>
            <ul>
                <li><strong>Backlink de qualité</strong> depuis un site avec un bon Domain Authority</li>
                <li><strong>Article contextualisé</strong> rédigé par nos soins</li>
                <li><strong>Lien DoFollow</strong> vers votre site</li>
                <li><strong>Thématique pertinente</strong> en lien avec votre secteur</li>
            </ul>

            <h3>🤝 En échange :</h3>
            <p>Un backlink similaire depuis votre site vers l'un de nos sites partenaires.</p>

            <p>Seriez-vous intéressé(e) pour discuter de cette opportunité ?</p>

            <p style="text-align: center;">
                <a href="mailto:david@perfect-cocon-seo.fr?subject=Collaboration%20SEO%20-%20{{domain}}" class="button">
                    Je suis intéressé(e)
                </a>
            </p>

            <p>Au plaisir d'échanger avec vous,</p>

            <p><strong>David</strong><br>
            Perfect Cocon SEO<br>
            📧 david@perfect-cocon-seo.fr</p>
        </div>

        <div class="footer">
            <p>Cet email est envoyé uniquement aux sites de qualité sélectionnés manuellement.</p>
            <p><a href="{{unsubscribe_link}}" style="color: #666;">Se désabonner</a></p>
        </div>
    </div>
</body>
</html>''',
            'available_variables': json.dumps(['domain', 'email', 'siret', 'leaders'])
        }
    ]

    for template_data in templates:
        # Vérifier si le template existe déjà
        existing = session.query(EmailTemplate).filter(
            EmailTemplate.name == template_data['name']
        ).first()

        if not existing:
            template = EmailTemplate(**template_data)
            session.add(template)
            print(f"✅ Template créé: {template_data['name']}")
        else:
            print(f"⊘ Template existe déjà: {template_data['name']}")

    session.commit()
    print(f"\n✅ {len(templates)} templates créés")

if __name__ == '__main__':
    create_default_templates()
