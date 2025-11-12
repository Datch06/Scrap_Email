# Configuration du Cron pour Mise à Jour Nocturne des Segments

## Installation automatique du cron

Pour installer automatiquement le cron qui rafraîchit les segments chaque nuit à 2h du matin:

```bash
# Ajouter le cron job
(crontab -l 2>/dev/null; echo "0 2 * * * cd /var/www/Scrap_Email && /usr/bin/python3 refresh_segments_nightly.py >> logs/segments_refresh.log 2>&1") | crontab -
```

## Vérification

Pour vérifier que le cron a été ajouté:

```bash
crontab -l | grep refresh_segments
```

## Tester manuellement

Pour tester le script manuellement:

```bash
cd /var/www/Scrap_Email
python3 refresh_segments_nightly.py
```

## Modifier l'heure d'exécution

Le cron est configuré pour s'exécuter à **2h du matin** tous les jours.

Pour changer l'heure, modifiez la ligne cron:
- `0 2 * * *` = Tous les jours à 2h00
- `0 3 * * *` = Tous les jours à 3h00
- `0 1 * * *` = Tous les jours à 1h00
- `30 2 * * *` = Tous les jours à 2h30

## Voir les logs

Les logs sont enregistrés dans `logs/segments_refresh.log`:

```bash
tail -f /var/www/Scrap_Email/logs/segments_refresh.log
```

## Supprimer le cron

Pour supprimer le cron job:

```bash
crontab -l | grep -v refresh_segments_nightly | crontab -
```

## Format du cron

```
┌───────────── minute (0-59)
│ ┌───────────── heure (0-23)
│ │ ┌───────────── jour du mois (1-31)
│ │ │ ┌───────────── mois (1-12)
│ │ │ │ ┌───────────── jour de la semaine (0-7, dimanche = 0 ou 7)
│ │ │ │ │
* * * * * commande à exécuter
```

Exemples:
- `0 2 * * *` - Tous les jours à 2h00
- `0 */6 * * *` - Toutes les 6 heures
- `0 2 * * 1` - Tous les lundis à 2h00
- `30 3 1 * *` - Le 1er de chaque mois à 3h30
