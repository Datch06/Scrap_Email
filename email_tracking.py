#!/usr/bin/env python3
"""
Email Tracking Utilities
Fonctions pour ajouter le tracking pixel et les liens trackés aux emails
"""

import re
from urllib.parse import quote
from aws_config import TRACKING_DOMAIN


def add_tracking_pixel(html_body: str, email_id: int) -> str:
    """
    Ajoute un pixel de tracking invisible à la fin du corps HTML

    Args:
        html_body: Corps HTML de l'email
        email_id: ID de l'email dans la table campaign_emails

    Returns:
        HTML avec pixel de tracking ajouté
    """
    # URL du pixel de tracking
    tracking_url = f"{TRACKING_DOMAIN}/track/open/{email_id}"

    # Pixel de tracking (image invisible 1x1)
    tracking_pixel = f'<img src="{tracking_url}" width="1" height="1" alt="" style="display:none;" />'

    # Insérer le pixel juste avant la balise </body> ou à la fin si pas de </body>
    if '</body>' in html_body.lower():
        html_body = re.sub(
            r'</body>',
            tracking_pixel + '</body>',
            html_body,
            flags=re.IGNORECASE
        )
    else:
        # Si pas de balise </body>, ajouter à la fin
        html_body += tracking_pixel

    return html_body


def add_click_tracking(html_body: str, email_id: int) -> str:
    """
    Remplace tous les liens <a href="..."> par des liens trackés

    Args:
        html_body: Corps HTML de l'email
        email_id: ID de l'email dans la table campaign_emails

    Returns:
        HTML avec liens trackés
    """
    # Pattern pour trouver tous les liens <a href="...">
    # On exclut les liens mailto: et les liens de désinscription
    link_pattern = r'<a\s+([^>]*\s+)?href=(["\'])([^"\']+)\2([^>]*)>'

    def replace_link(match):
        """Remplace un lien par un lien tracké"""
        pre_attrs = match.group(1) or ''
        quote_char = match.group(2)
        original_url = match.group(3)
        post_attrs = match.group(4) or ''

        # Ne pas tracker les liens mailto: et unsubscribe
        if original_url.startswith('mailto:') or 'unsubscribe' in original_url.lower():
            return match.group(0)

        # Ne pas tracker les liens vides ou ancres
        if not original_url or original_url.startswith('#'):
            return match.group(0)

        # Créer le lien tracké
        encoded_url = quote(original_url, safe='')
        tracked_url = f"{TRACKING_DOMAIN}/track/click/{email_id}?url={encoded_url}"

        return f'<a {pre_attrs}href={quote_char}{tracked_url}{quote_char}{post_attrs}>'

    # Remplacer tous les liens
    html_body = re.sub(link_pattern, replace_link, html_body, flags=re.IGNORECASE)

    return html_body


def add_email_tracking(html_body: str, email_id: int, track_opens: bool = True, track_clicks: bool = True) -> str:
    """
    Ajoute le tracking complet (pixel + liens) à un email HTML

    Args:
        html_body: Corps HTML de l'email
        email_id: ID de l'email dans la table campaign_emails
        track_opens: Activer le tracking des ouvertures (défaut: True)
        track_clicks: Activer le tracking des clics (défaut: True)

    Returns:
        HTML avec tracking ajouté
    """
    if track_clicks:
        html_body = add_click_tracking(html_body, email_id)

    if track_opens:
        html_body = add_tracking_pixel(html_body, email_id)

    return html_body
