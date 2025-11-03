# 📧 Guide Complet des Campagnes d'Emails

## 🎉 Système Opérationnel !

Votre système complet de gestion de campagnes d'emails est maintenant installé et fonctionnel.

---

## 🌐 Accès à l'Interface

**URL** : http://admin.perfect-cocon-seo.fr/campaigns

---

## 📚 Fonctionnalités Disponibles

### 1. Créer une Campagne

1. Cliquez sur **"Nouvelle Campagne"**
2. Remplissez les informations :
   - **Nom** : Ex: "Prospection Backlinks Juin 2025"
   - **Description** : Ex: "Première campagne de prospection"
   - **Template** : Choisissez un template prédéfini ou créez le vôtre
   - **Sujet** : Ex: `Collaboration SEO - {{domain}}`
   - **Corps HTML** : Votre message personnalisé

3. **Variables disponibles** (personnalisation automatique) :
   - `{{domain}}` - Le domaine du destinataire
   - `{{email}}` - L'email du destinataire
   - `{{siret}}` - Le SIRET (si disponible)
   - `{{leaders}}` - Les dirigeants (si disponibles)
   - `{{unsubscribe_link}}` - Lien de désinscription (obligatoire)

4. **Options d'envoi** :
   - **Score minimum** : 80 (recommandé) - Ne envoyer qu'aux emails validés avec un bon score
   - **Uniquement délivrables** : Coché (recommandé)
   - **Max par jour** : 200 (limite sandbox) ou plus si sortie du sandbox
   - **Délai entre emails** : 2 secondes (anti-spam)

5. Cliquez sur **"Créer la Campagne"**

---

### 2. Préparer une Campagne

Avant d'envoyer, vous devez **préparer** la campagne :

1. Cliquez sur **"Voir"** sur votre campagne
2. Cliquez sur **"Préparer la Campagne"**
3. Le système va :
   - Sélectionner les destinataires éligibles (score > 80, délivrables)
   - Exclure les emails déjà envoyés
   - Exclure les désabonnés
   - Afficher le nombre total de destinataires

**Exemple** : Si vous avez 102 emails validés avec score > 80, la campagne sera préparée pour 102 destinataires.

---

### 3. Lancer l'Envoi

1. Une fois préparée, cliquez sur **"Lancer l'Envoi"**
2. Choisissez combien d'emails envoyer :
   - **Test** : 10-20 emails pour tester
   - **Batch** : 100-200 emails
   - **Tous** : Laissez vide pour envoyer à tous

3. L'envoi se fait **en arrière-plan**
4. Les statistiques se mettent à jour automatiquement

---

## 📊 Statistiques Disponibles

Pour chaque campagne, vous verrez :

- **Total destinataires** : Nombre d'emails à envoyer
- **Envoyés** : Emails effectivement envoyés
- **Délivrés** : Emails arrivés à destination
- **Ouverts** : Emails lus (tracking pixel)
- **Cliqués** : Liens cliqués dans l'email
- **Taux d'ouverture** : % d'emails ouverts
- **Taux de clic** : % d'emails cliqués
- **Bounces** : Emails rebondis (adresse invalide)

---

## 🎨 Templates Prédéfinis

2 templates sont disponibles par défaut :

### 1. **Proposition de Backlink Simple**
Template basique pour proposer un échange de backlinks.

### 2. **Proposition de Backlink Personnalisée**
Template plus élaboré avec mise en forme professionnelle.

Vous pouvez les utiliser tels quels ou les personnaliser.

---

## 📈 Workflow Complet

### Étape 1 : Validation des Emails (Automatique)
- Le daemon `email-validation-daemon` valide automatiquement tous les emails
- Score de 0 à 100 attribué à chaque email
- Seuls les emails avec score > 80 seront utilisés

### Étape 2 : Création de la Campagne
- Créez votre campagne avec un template
- Personnalisez le message
- Configurez les options d'envoi

### Étape 3 : Préparation
- Le système sélectionne les destinataires éligibles
- Affiche le nombre exact d'emails à envoyer

### Étape 4 : Envoi
- Envoi progressif pour respecter les limites
- Tracking automatique des ouvertures et clics
- Statistiques en temps réel

### Étape 5 : Analyse
- Consultez les statistiques
- Identifiez les emails qui fonctionnent le mieux
- Optimisez vos futures campagnes

---

## ⚙️ Configuration Actuelle

### Amazon SES
- **Statut** : Sandbox Mode
- **Limite quotidienne** : 200 emails/jour
- **Débit** : 1 email/seconde
- **Expéditeur** : david@perfect-cocon-seo.fr

### Base de Données
- **Emails collectés** : 25,443
- **Emails validés** : ~150 (en cours)
- **Emails délivrables** : ~102
- **Taux de succès** : ~68%

---

## 🚀 Pour Augmenter les Limites

### Sortir du Sandbox Mode

1. Allez sur https://console.aws.amazon.com/ses
2. **Account Dashboard** → **Request production access**
3. Remplissez le formulaire :
   - **Mail type** : Transactional
   - **Website** : https://admin.perfect-cocon-seo.fr
   - **Use case** :
     ```
     We send outreach emails to website owners for SEO backlink partnerships.
     Our email list contains verified and validated email addresses.
     We implement unsubscribe mechanisms and comply with GDPR.
     Expected volume: 1,000 emails per day.
     ```

4. **Bounce handling** :
   ```
   We monitor bounces and complaints through SES API.
   We automatically remove bounced/complained addresses.
   We maintain email validation before sending.
   ```

5. Cliquez sur **Submit**
6. **Délai** : 24-48h (souvent quelques heures)
7. **Nouvelle limite** : Jusqu'à 50,000 emails/jour !

---

## 💡 Bonnes Pratiques

### 1. Testez d'abord !
- Envoyez à 10-20 emails avant l'envoi massif
- Vérifiez que les emails arrivent bien
- Testez sur différents clients (Gmail, Outlook, etc.)

### 2. Personnalisez vos messages
- Utilisez les variables `{{domain}}`, `{{leaders}}`
- Ajoutez une vraie valeur (pas de spam)
- Soyez authentique et professionnel

### 3. Respectez les règles
- ✅ Toujours inclure un lien de désinscription
- ✅ Envoyer uniquement aux emails validés
- ✅ Respecter les limites quotidiennes
- ✅ Ne pas acheter de listes d'emails

### 4. Surveillez vos métriques
- **Taux d'ouverture normal** : 15-25%
- **Taux de clic normal** : 2-5%
- **Taux de bounce acceptable** : < 5%
- **Taux de plainte acceptable** : < 0.1%

Si vos métriques sont mauvaises, Amazon peut suspendre votre compte !

### 5. Optimisez progressivement
- Testez différents sujets (A/B testing)
- Analysez les heures d'envoi
- Adaptez le contenu selon les retours

---

## 🔧 Commandes Utiles

### Voir les campagnes
```bash
cd /var/www/Scrap_Email
python3 << 'EOF'
from campaign_manager import CampaignManager
manager = CampaignManager()
campaigns = manager.list_campaigns()
for c in campaigns:
    print(f"{c['name']}: {c['emails_sent']}/{c['total_recipients']} envoyés")
EOF
```

### Créer une campagne en CLI
```bash
python3 << 'EOF'
from campaign_manager import CampaignManager
manager = CampaignManager()

campaign = manager.create_campaign(
    name="Test CLI",
    subject="Test {{domain}}",
    html_body="<p>Bonjour,</p><p>Message pour {{domain}}</p>",
    min_validation_score=80
)
print(f"Campagne créée: {campaign.id}")
EOF
```

### Préparer et envoyer
```bash
python3 << 'EOF'
from campaign_manager import CampaignManager
manager = CampaignManager()

# Préparer
result = manager.prepare_campaign(1)  # ID de la campagne
print(f"Destinataires: {result['total_recipients']}")

# Envoyer (limité à 10 pour test)
stats = manager.run_campaign(1, limit=10)
print(f"Envoyés: {stats['sent']}")
EOF
```

---

## 📞 Support

- **Documentation AWS SES** : https://docs.aws.amazon.com/ses/
- **Status AWS** : https://status.aws.amazon.com/
- **Interface Admin** : http://admin.perfect-cocon-seo.fr

---

## 🎯 Récapitulatif

✅ **Amazon SES** configuré et opérationnel
✅ **25,443 emails** collectés et en cours de validation
✅ **Système de campagnes** complet avec interface web
✅ **Templates** prédéfinis personnalisables
✅ **Tracking** des ouvertures et clics
✅ **Envoi automatique** aux emails validés
✅ **Dashboard** temps réel des statistiques

**Vous êtes prêt à envoyer vos premières campagnes !** 🚀

---

**Prochaine étape recommandée** :
1. Attendez que le daemon valide plus d'emails (actuellement ~150/25,443)
2. Demandez la sortie du sandbox AWS (pour passer à 50k emails/jour)
3. Créez votre première campagne de test (10-20 emails)
4. Analysez les résultats et optimisez
5. Lancez votre première vraie campagne !

Bonne prospection ! 📧
