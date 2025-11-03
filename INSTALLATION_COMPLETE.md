# Installation Complète - Scrap Email Interface

Date: 2025-10-18
Statut: **Installation Réussie** ✅

---

## Récapitulatif de l'Installation

### 1. Problèmes Résolus

#### Conflit de Port
- **Problème**: Datadog Agent utilisait les ports 5000 et 5001
- **Solution**: Application configurée sur le port **5002**

#### Processus Orphelin
- **Problème**: Ancien processus Python (PID 875679) encore actif
- **Solution**: Processus arrêté avec succès

### 2. Services Installés et Configurés

#### Service Flask
- **Nom**: scrap-email-interface.service
- **Statut**: ✅ Active (running)
- **Port**: 5002
- **Host**: 127.0.0.1
- **Mode**: Production

#### Nginx Reverse Proxy
- **Version**: 1.18.0
- **Statut**: ✅ Active (running)
- **Configuration**: /etc/nginx/sites-available/admin.perfect-cocon-seo.fr

#### SSL/TLS (Let's Encrypt)
- **Certificat**: ✅ Installé et valide
- **Expiration**: 2026-01-16
- **Auto-renouvellement**: ✅ Configuré (via certbot.timer)

---

## Accès à l'Application

### URL Publique
**https://admin.perfect-cocon-seo.fr**

### Pages Disponibles

1. **Dashboard**: https://admin.perfect-cocon-seo.fr/
   - Vue d'ensemble des statistiques
   - Graphiques et métriques

2. **Gestion des Sites**: https://admin.perfect-cocon-seo.fr/sites
   - Liste des sites scrapés
   - Filtres et recherche
   - Édition et suppression

3. **Jobs de Scraping**: https://admin.perfect-cocon-seo.fr/jobs
   - Historique des jobs
   - Lancement de nouveaux jobs

### API REST

Toutes les API sont accessibles via HTTPS:

```bash
# Statistiques globales
curl https://admin.perfect-cocon-seo.fr/api/stats

# Liste des sites (avec pagination)
curl https://admin.perfect-cocon-seo.fr/api/sites?page=1&per_page=50

# Détails d'un site
curl https://admin.perfect-cocon-seo.fr/api/sites/1

# Liste des jobs
curl https://admin.perfect-cocon-seo.fr/api/jobs

# Export CSV
curl https://admin.perfect-cocon-seo.fr/api/export/csv > sites.csv
```

---

## Configuration Technique

### Fichiers de Configuration

1. **Service systemd**: [/etc/systemd/system/scrap-email-interface.service](scrap-email-interface.service:1)
   ```ini
   Environment="FLASK_PORT=5002"
   ExecStart=/usr/bin/python3 /var/www/Scrap_Email/app.py
   ```

2. **Nginx**: /etc/nginx/sites-available/admin.perfect-cocon-seo.fr
   ```nginx
   proxy_pass http://127.0.0.1:5002;
   ```

3. **SSL**: /etc/letsencrypt/live/admin.perfect-cocon-seo.fr/
   - fullchain.pem
   - privkey.pem

### Architecture

```
Internet (HTTPS:443)
    ↓
Nginx Reverse Proxy
    ↓ (HTTP:5002)
Flask App (Gunicorn)
    ↓
SQLite Database (scrap_email.db)
```

---

## Statistiques Actuelles

Au moment de l'installation:

- **Total de sites**: 4
- **Sites avec email**: 2 (50%)
- **Sites avec SIRET**: 2 (50%)
- **Sites avec dirigeants**: 2 (50%)
- **Sites complets**: 2 (50%)
- **Jobs en cours**: 0

---

## Commandes de Gestion

### Vérifier le Statut des Services

```bash
# Service Flask
sudo systemctl status scrap-email-interface.service

# Nginx
sudo systemctl status nginx

# Certificat SSL
sudo certbot certificates
```

### Gérer le Service Flask

```bash
# Arrêter
sudo systemctl stop scrap-email-interface.service

# Démarrer
sudo systemctl start scrap-email-interface.service

# Redémarrer
sudo systemctl restart scrap-email-interface.service

# Voir les logs en temps réel
sudo journalctl -u scrap-email-interface.service -f
```

### Gérer Nginx

```bash
# Tester la configuration
sudo nginx -t

# Recharger (sans downtime)
sudo systemctl reload nginx

# Redémarrer
sudo systemctl restart nginx

# Voir les logs
sudo tail -f /var/log/nginx/scrap-email-access.log
sudo tail -f /var/log/nginx/scrap-email-error.log
```

### SSL/Certificats

```bash
# Renouveler manuellement (normalement automatique)
sudo certbot renew

# Tester le renouvellement
sudo certbot renew --dry-run

# Voir tous les certificats
sudo certbot certificates
```

---

## Sécurité

### Configuré

✅ HTTPS/SSL activé avec Let's Encrypt
✅ Redirection automatique HTTP → HTTPS
✅ Service Flask accessible uniquement en local (127.0.0.1)
✅ Nginx fait office de reverse proxy sécurisé
✅ CORS activé pour les API

### Recommandations Supplémentaires

Pour renforcer la sécurité en production:

1. **Authentification**: Ajouter un système d'authentification (OAuth, JWT, etc.)
2. **Rate Limiting**: Limiter le nombre de requêtes par IP
3. **Firewall**: Configurer UFW pour bloquer les ports non nécessaires
4. **Monitoring**: Configurer des alertes pour les erreurs
5. **Backup**: Mettre en place des sauvegardes automatiques de la base de données

---

## Maintenance

### Renouvellement SSL

Le certificat SSL se renouvelle automatiquement via le timer systemd `certbot.timer`.

Vérification:
```bash
sudo systemctl status certbot.timer
```

### Base de Données

Localisation: [/var/www/Scrap_Email/scrap_email.db](scrap_email.db:1)

Sauvegarde manuelle:
```bash
cd /var/www/Scrap_Email
cp scrap_email.db scrap_email.db.backup-$(date +%Y%m%d)
```

### Logs

Les logs sont accessibles via:
```bash
# Logs du service Flask
sudo journalctl -u scrap-email-interface.service -n 100

# Logs Nginx
sudo tail -100 /var/log/nginx/scrap-email-error.log
```

---

## Prochaines Étapes Recommandées

1. **Tester l'interface** via https://admin.perfect-cocon-seo.fr
2. **Ajouter de nouveaux sites** pour tester le scraping
3. **Configurer l'authentification** pour sécuriser l'accès
4. **Mettre en place des backups automatiques** de la base de données
5. **Configurer des alertes** pour surveiller le service

---

## Support et Documentation

### Fichiers de Documentation

- [README_INTERFACE.md](README_INTERFACE.md:1) - Guide d'utilisation de l'interface
- [DEPLOYMENT.md](DEPLOYMENT.md:1) - Guide de déploiement
- [ETAT_APRES_REDEMARRAGE.md](ETAT_APRES_REDEMARRAGE.md:1) - État après le redémarrage

### Contacts

En cas de problème:
1. Vérifier les logs (voir section Logs ci-dessus)
2. Vérifier le statut des services
3. Consulter la documentation

---

## Résumé des URLs

| Service | URL | Statut |
|---------|-----|--------|
| Dashboard | https://admin.perfect-cocon-seo.fr/ | ✅ |
| Sites | https://admin.perfect-cocon-seo.fr/sites | ✅ |
| Jobs | https://admin.perfect-cocon-seo.fr/jobs | ✅ |
| API Stats | https://admin.perfect-cocon-seo.fr/api/stats | ✅ |
| Export CSV | https://admin.perfect-cocon-seo.fr/api/export/csv | ✅ |

---

**Installation terminée avec succès !** 🎉

L'application est maintenant accessible en production sur https://admin.perfect-cocon-seo.fr
