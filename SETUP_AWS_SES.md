# 🚀 Guide de Configuration Amazon SES

## Étape 1 : Récupérer vos Credentials AWS

### 1.1 Créer un utilisateur IAM

1. Allez sur **AWS Console** : https://console.aws.amazon.com/
2. Recherchez et ouvrez **IAM** (Identity and Access Management)
3. Dans le menu de gauche, cliquez sur **Users**
4. Cliquez sur **Create user**

### 1.2 Configurer l'utilisateur

1. **Nom d'utilisateur** : `ses-email-sender`
2. Cochez **Provide user access to the AWS Management Console** : **NON** (on veut juste l'API)
3. Cliquez sur **Next**

### 1.3 Attacher les permissions

1. Sélectionnez **Attach policies directly**
2. Dans la barre de recherche, tapez : `SES`
3. Cochez **AmazonSESFullAccess**
4. Cliquez sur **Next**
5. Cliquez sur **Create user**

### 1.4 Créer les Access Keys

1. Cliquez sur l'utilisateur que vous venez de créer
2. Allez dans l'onglet **Security credentials**
3. Scrollez jusqu'à **Access keys**
4. Cliquez sur **Create access key**
5. Sélectionnez **Application running outside AWS**
6. Cliquez sur **Next**
7. Cliquez sur **Create access key**
8. **⚠️ IMPORTANT** : Copiez :
   - **Access key ID** (commence par AKIA...)
   - **Secret access key** (vous ne pourrez plus le voir après!)
9. Téléchargez le fichier CSV (recommandé)

---

## Étape 2 : Configurer le fichier aws_config.py

1. Ouvrez le fichier : `/var/www/Scrap_Email/aws_config.py`

2. Remplacez les valeurs suivantes :

```python
AWS_ACCESS_KEY_ID = 'VOTRE_ACCESS_KEY_ICI'  # Collez votre Access Key ID
AWS_SECRET_ACCESS_KEY = 'VOTRE_SECRET_KEY_ICI'  # Collez votre Secret Access Key
AWS_REGION = 'eu-west-1'  # Europe (Irlande) ou 'us-east-1' pour USA

SES_SENDER_EMAIL = 'votre-email@exemple.com'  # Email que vous allez vérifier
SES_SENDER_NAME = 'Votre Nom ou Entreprise'
```

3. Sauvegardez le fichier

---

## Étape 3 : Choisir une Région SES

### Régions recommandées :

- **eu-west-1** (Irlande) - Pour l'Europe ✅ Recommandé si vous êtes en France
- **us-east-1** (Virginie) - Pour les USA
- **eu-central-1** (Francfort) - Alternative Europe

**Vérifiez que SES est disponible** :
https://docs.aws.amazon.com/general/latest/gr/ses.html

---

## Étape 4 : Vérifier votre Email Expéditeur

### Option A : Vérifier un email individuel (plus rapide pour tester)

1. Allez sur **AWS Console SES** : https://console.aws.amazon.com/ses
2. **⚠️ Important** : Sélectionnez la bonne région en haut à droite (ex: eu-west-1)
3. Dans le menu de gauche, cliquez sur **Verified identities**
4. Cliquez sur **Create identity**
5. Sélectionnez **Email address**
6. Entrez votre email (ex: `contact@votre-domaine.fr`)
7. Cliquez sur **Create identity**
8. **Vérifiez votre boîte mail** et cliquez sur le lien de vérification
9. Retournez sur la console, le statut devrait passer à **Verified** (actualisez la page)

### Option B : Vérifier un domaine complet (recommandé pour la production)

1. Sur **AWS Console SES** → **Verified identities**
2. Cliquez sur **Create identity**
3. Sélectionnez **Domain**
4. Entrez votre domaine (ex: `votre-domaine.fr`)
5. Cochez **Generate DKIM settings** (recommandé)
6. Cliquez sur **Create identity**
7. AWS vous donnera des enregistrements DNS à ajouter :
   - Un enregistrement **TXT** pour vérifier le domaine
   - Trois enregistrements **CNAME** pour DKIM

### Ajouter les enregistrements DNS :

**Exemple pour OVH** :
1. Allez dans votre espace client OVH
2. Sélectionnez votre domaine
3. Allez dans **Zone DNS**
4. Ajoutez les enregistrements fournis par AWS

**Enregistrement de vérification** :
- Type : `TXT`
- Sous-domaine : `_amazonses`
- Valeur : (le token fourni par AWS)

**Enregistrements DKIM** (3 enregistrements) :
- Type : `CNAME`
- Sous-domaine : (fourni par AWS, ex: `abc123._domainkey`)
- Cible : (fournie par AWS)

⏱️ **Temps de propagation** : 15 min à 48h (généralement 1-2h)

---

## Étape 5 : Sortir du Sandbox Mode

Par défaut, AWS SES est en **Sandbox Mode** avec ces limitations :
- ❌ 200 emails/jour maximum
- ❌ Uniquement vers des emails vérifiés

### Demander la sortie du sandbox :

1. Sur **AWS Console SES** → **Account dashboard**
2. En haut à droite, cliquez sur **Request production access**
3. Remplissez le formulaire :

**Mail type** : Transactional
**Website URL** : https://admin.perfect-cocon-seo.fr
**Use case description** (exemple) :
```
We are sending outreach emails to website owners for SEO backlink partnerships.
Our email list contains verified and validated email addresses.
We have implemented unsubscribe mechanisms and comply with GDPR.
Expected volume: 1,000 emails per day.
```

**Bounces/complaints handling** :
```
We monitor bounces and complaints through SES API.
We automatically remove bounced/complained addresses from our list.
We maintain email validation before sending.
```

4. Cliquez sur **Submit request**
5. ⏱️ **Délai de réponse** : 24-48h (souvent quelques heures)

---

## Étape 6 : Tester la Configuration

```bash
cd /var/www/Scrap_Email

# 1. Vérifier la config
python3 aws_config.py

# 2. Setup SES
python3 ses_manager.py

# 3. Envoyer un email de test
python3 test_ses.py
```

---

## 📋 Checklist Finale

- [ ] Credentials AWS créées (Access Key + Secret Key)
- [ ] Fichier `aws_config.py` configuré
- [ ] Région SES sélectionnée
- [ ] Email expéditeur vérifié (ou domaine vérifié)
- [ ] Test d'envoi réussi
- [ ] Demande de sortie du sandbox envoyée
- [ ] Enregistrements DNS configurés (si domaine)

---

## 🆘 Problèmes Courants

### "MessageRejected: Email address is not verified"
➡️ L'email expéditeur n'est pas vérifié dans SES. Vérifiez-le d'abord.

### "MessageRejected: Email address is in sandbox mode"
➡️ L'email destinataire doit être vérifié en sandbox mode. Sortez du sandbox ou vérifiez le destinataire.

### "InvalidClientTokenId"
➡️ Vos credentials AWS sont incorrectes. Vérifiez `AWS_ACCESS_KEY_ID` et `AWS_SECRET_ACCESS_KEY`.

### "Slow Down"
➡️ Vous envoyez trop vite. Respectez le `DELAY_BETWEEN_EMAILS`.

### Le statut reste en "Pending"
➡️ Pour un email : vérifiez votre boîte mail (spam aussi)
➡️ Pour un domaine : vérifiez que les DNS sont bien configurés

---

## 📞 Support

- Documentation AWS SES : https://docs.aws.amazon.com/ses/
- Support AWS : https://console.aws.amazon.com/support/
- Status AWS : https://status.aws.amazon.com/

---

**Prêt à envoyer vos premiers emails !** 🚀
