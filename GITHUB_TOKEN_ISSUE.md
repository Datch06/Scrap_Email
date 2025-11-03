# 🔐 Problème avec le Token GitHub

## ❌ Erreur Actuelle

```
remote: Permission to Datch06/Scrap_Email.git denied to Datch06.
fatal: unable to access 'https://github.com/Datch06/Scrap_Email.git/': The requested URL returned error: 403
```

## 🔍 Cause

Le token GitHub que vous avez fourni **n'a pas les permissions nécessaires** pour pousser du code vers le repository.

## ✅ Solution : Créer un Nouveau Token avec les Bonnes Permissions

### Étape 1 : Aller sur GitHub Tokens
https://github.com/settings/tokens

### Étape 2 : Supprimer l'Ancien Token (optionnel)
- Trouvez le token qui commence par `github_pat_11AMOMCFQ0...`
- Cliquez sur "Delete"

### Étape 3 : Créer un Nouveau Token

1. Cliquez sur **"Generate new token"** → **"Generate new token (classic)"**

2. **Note** : `scrap-email-full-access`

3. **Sélectionnez TOUTES ces permissions** :
   ```
   ✅ repo (Full control of private repositories)
      ✅ repo:status
      ✅ repo_deployment
      ✅ public_repo
      ✅ repo:invite
      ✅ security_events
   ```

4. **Expiration** : Choisissez "No expiration" ou "90 days"

5. Cliquez sur **"Generate token"**

6. **COPIEZ LE TOKEN** (il commence par `ghp_` ou `github_pat_`)

### Étape 4 : Utiliser le Nouveau Token

```bash
cd /var/www/Scrap_Email

# Remplacez NOUVEAU_TOKEN par votre token
git remote set-url origin https://NOUVEAU_TOKEN@github.com/Datch06/Scrap_Email.git

# Pousser le code
git push -u origin main
```

## 🎯 Permissions Requises

Pour pousser du code vers un repository GitHub, le token DOIT avoir :

- ✅ **repo** (Full control) - **OBLIGATOIRE**
  - Permet de lire et écrire dans les repositories privés et publics
  - Permet de push, pull, créer branches, etc.

Sans cette permission, vous obtiendrez l'erreur 403 "Permission denied".

## 📝 Alternative : Utiliser SSH

Si vous préférez ne pas utiliser de token HTTPS, vous pouvez configurer une clé SSH :

```bash
# Générer une clé SSH
ssh-keygen -t ed25519 -C "david@somucom.com"

# Copier la clé publique
cat ~/.ssh/id_ed25519.pub

# Ajouter la clé sur GitHub
# https://github.com/settings/keys

# Changer le remote
cd /var/www/Scrap_Email
git remote set-url origin git@github.com:Datch06/Scrap_Email.git

# Pousser
git push -u origin main
```

## 🔄 État Actuel

✅ **Code commité localement** : 174 fichiers
✅ **Branche** : main
✅ **Commits** : 2
✅ **Remote configuré** : https://github.com/Datch06/Scrap_Email.git
❌ **Push** : Échec (permissions token insuffisantes)

## 📞 Besoin d'Aide ?

Une fois le nouveau token créé avec les bonnes permissions, envoyez-le moi et je pourrai pousser le code immédiatement !
