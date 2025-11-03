# 📦 GitHub Repository Setup Guide

## ✅ Étape 1 : Créer un Personal Access Token (PAT)

1. Allez sur GitHub : https://github.com/settings/tokens
2. Cliquez sur **"Generate new token"** → **"Generate new token (classic)"**
3. Nom du token : `scrap-email-deploy`
4. Sélectionnez les permissions :
   - ✅ **repo** (Full control of private repositories)
   - ✅ **workflow** (Update GitHub Action workflows)
5. Cliquez sur **"Generate token"**
6. **Copiez le token** (vous ne pourrez plus le voir après)

## ✅ Étape 2 : Créer le repository sur GitHub

### Option A : Via l'interface web (Recommandé)

1. Allez sur https://github.com/new
2. Remplissez :
   - **Repository name** : `scrap-email`
   - **Description** : `Professional email scraping and campaign management platform for SEO backlink prospecting`
   - **Visibility** : ✅ Private
3. Ne pas initialiser avec README, .gitignore, ou license (déjà fait en local)
4. Cliquez sur **"Create repository"**

### Option B : Via l'API

```bash
# Remplacez YOUR_GITHUB_TOKEN par votre token
curl -H "Authorization: token YOUR_GITHUB_TOKEN" \
  -d '{"name":"scrap-email","description":"Professional email scraping and campaign management platform","private":true}' \
  https://api.github.com/user/repos
```

## ✅ Étape 3 : Pousser le code vers GitHub

```bash
cd /var/www/Scrap_Email

# Ajouter le remote GitHub (remplacez USERNAME par votre username GitHub)
git remote add origin https://github.com/USERNAME/scrap-email.git

# Renommer la branche en main
git branch -M main

# Pousser le code (utilisez votre token comme mot de passe)
git push -u origin main
```

Quand demandé :
- **Username** : `david@somucom.com` ou votre username GitHub
- **Password** : Collez votre **Personal Access Token** (pas votre mot de passe)

## ✅ Étape 4 : Configuration Git avec le Token

Pour éviter de retaper le token à chaque fois :

```bash
# Méthode 1 : Credential helper (recommandé)
git config --global credential.helper store
git push -u origin main
# Entrez le token une fois, il sera sauvegardé

# Méthode 2 : URL avec token
git remote set-url origin https://YOUR_TOKEN@github.com/USERNAME/scrap-email.git
```

## 📊 État Actuel du Repository Local

✅ **Git initialisé** : Oui
✅ **Fichiers committés** : 172 fichiers
✅ **Branche** : master (à renommer en main)
✅ **.gitignore** : Configuré (exclut .env, .db, .log, etc.)
✅ **README.md** : Créé avec documentation complète

## 🔐 Fichiers Protégés (Exclus du Git)

Ces fichiers sont automatiquement exclus via `.gitignore` :

- ✅ `scrap_email.db` - Base de données SQLite
- ✅ `campaigns.db` - Base campagnes
- ✅ `.env` - Variables d'environnement
- ✅ `aws_config.py` - Credentials AWS
- ✅ `.htpasswd` - Mots de passe
- ✅ `*.log` - Logs d'application
- ✅ `credentials.json` - Credentials Google

## 📝 Commandes Rapides

### Après avoir créé le repository sur GitHub :

```bash
cd /var/www/Scrap_Email

# Renommer la branche
git branch -M main

# Ajouter le remote (REMPLACEZ USERNAME)
git remote add origin https://github.com/USERNAME/scrap-email.git

# Pousser le code
git push -u origin main
```

### Pour les futures mises à jour :

```bash
cd /var/www/Scrap_Email

# Voir les changements
git status

# Ajouter les changements
git add .

# Committer
git commit -m "Description des changements"

# Pousser
git push
```

## 🔄 Automatiser les Commits

Script pour commit automatique :

```bash
#!/bin/bash
cd /var/www/Scrap_Email
git add .
git commit -m "Auto update: $(date '+%Y-%m-%d %H:%M:%S')"
git push
```

## 📞 Support

Si vous rencontrez des problèmes :
1. Vérifiez que votre token a les bonnes permissions
2. Vérifiez votre username GitHub
3. Essayez avec HTTPS plutôt que SSH

---

**Documentation GitHub** : https://docs.github.com/en/authentication
