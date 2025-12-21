#!/usr/bin/env python3
"""
Script de fallback intelligent : Recherche N'IMPORTE QUEL email valide sur un site
Quand on ne trouve pas d'email "contact", on cherche tous les emails du site et on valide le meilleur

Workflow:
1. Chercher TOUS les emails sur le site (pas seulement contact@)
2. Filtrer les emails pertinents (exclure info@, noreply@, etc.)
3. Si aucun email trouvé → GÉNÉRER des emails génériques (contact@, info@, hello@, etc.) et les VALIDER
4. Valider chaque email trouvé/généré (syntaxe + DNS + SMTP)
5. Garder le meilleur email (score le plus élevé)
6. Marquer comme "any_valid_email" ou "generic_validated" dans email_source

Usage:
    python3 find_any_valid_email.py [--limit 100] [--concurrent 20] [--batch-size 50]
"""

import asyncio
import aiohttp
import argparse
import time
from database import get_session, get_engine, Site, SiteStatus, safe_commit
from datetime import datetime
from email_finder_async import AsyncEmailFinder
from validate_emails_async import AsyncEmailValidator
from typing import List, Optional, Tuple
import logging
from sqlalchemy.orm import sessionmaker

# Configuration du logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('find_any_valid_email.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


class AnyValidEmailFinder:
    """Cherche n'importe quel email valide sur un site"""

    def __init__(self, max_concurrent: int = 20):
        """
        Initialiser le finder

        Args:
            max_concurrent: Nombre de requêtes simultanées
        """
        self.max_concurrent = max_concurrent
        self.session = None
        self.email_finder = None
        self.email_validator = AsyncEmailValidator(smtp_timeout=5.0, dns_timeout=3.0)  # Async validator

        # Préfixes d'emails génériques à éviter en priorité
        self.generic_prefixes = [
            'noreply', 'no-reply', 'donotreply', 'bounce',
            'mailer-daemon', 'postmaster', 'abuse', 'spam',
            'newsletter', 'marketing', 'promo', 'pub'
        ]

        # Préfixes d'emails à privilégier
        self.priority_prefixes = [
            'contact', 'info', 'hello', 'bonjour', 'support',
            'admin', 'service', 'commercial', 'vente', 'sales',
            'direction', 'gerant', 'owner', 'ceo', 'president',
            'partenariat', 'partner', 'presse', 'press'
        ]

        # Emails génériques à tester en dernier recours - LISTE ÉTENDUE
        # Triés par taux de succès estimé (basé sur les données du secteur)
        self.generic_emails_to_test = [
            # Tier 1 - Très haute probabilité (95%+ des sites B2B ont un de ceux-ci)
            'contact',
            'info',
            'hello',
            'bonjour',

            # Tier 2 - Haute probabilité (versions alternatives contact)
            'support',
            'service',
            'aide',
            'help',

            # Tier 3 - Commercial / Ventes (important pour backlinks!)
            'commercial',
            'vente',
            'ventes',
            'sales',
            'business',
            'devis',

            # Tier 4 - Partenariats (CRITIQUE pour backlinks!)
            'partenariat',
            'partenariats',
            'partner',
            'partners',
            'affiliate',
            'affiliation',
            'agence',
            'agences',
            'agency',

            # Tier 5 - Direction / Leadership
            'direction',
            'admin',
            'administration',
            'gerant',
            'directeur',
            'ceo',

            # Tier 6 - Communication / Marketing
            'communication',
            'com',
            'marketing',
            'presse',
            'press',
            'media',
            'rp',

            # Tier 7 - RH (souvent répondent aux sollicitations)
            'rh',
            'hr',
            'recrutement',
            'recruitment',
            'jobs',
            'emploi',
            'carriere',

            # Tier 8 - Autres
            'webmaster',
            'web',
            'mail',
            'accueil',
            'reception',
            'secretariat',
            'comptabilite',
            'facturation',
            'billing',

            # Tier 9 - Génériques techniques
            'technique',
            'tech',
            'it',
            'dev',
            'team',
            'equipe',
        ]

    async def init_session(self):
        """Initialiser la session aiohttp"""
        connector = aiohttp.TCPConnector(limit=self.max_concurrent, ssl=False, ttl_dns_cache=300)
        timeout = aiohttp.ClientTimeout(total=15, connect=5)  # Timeouts réduits pour plus de vitesse
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }

        self.session = aiohttp.ClientSession(
            connector=connector,
            timeout=timeout,
            headers=headers
        )

        self.email_finder = AsyncEmailFinder(self.session)

    async def close_session(self):
        """Fermer la session aiohttp"""
        if self.session:
            await self.session.close()

    def score_email_prefix(self, email: str) -> int:
        """
        Attribuer un score de priorité à un email en fonction de son préfixe
        Plus le score est élevé, plus l'email est pertinent

        Args:
            email: Email à scorer

        Returns:
            Score de 0 (générique) à 100 (très pertinent)
        """
        prefix = email.split('@')[0].lower()

        # Emails génériques = score bas
        if any(gen in prefix for gen in self.generic_prefixes):
            return 10

        # Emails prioritaires = score élevé
        if any(prio in prefix for prio in self.priority_prefixes):
            return 90

        # Emails nominatifs (prénom.nom@) = score moyen-élevé
        if '.' in prefix and len(prefix.split('.')) == 2:
            parts = prefix.split('.')
            if all(len(p) >= 2 for p in parts):
                return 70

        # Email court (probablement nominatif) = score moyen
        if len(prefix) <= 10 and prefix.isalpha():
            return 60

        # Par défaut = score moyen-bas
        return 40

    def generate_generic_emails(self, domain: str) -> List[str]:
        """
        Générer une liste d'emails génériques à tester

        Args:
            domain: Nom de domaine

        Returns:
            Liste d'emails génériques (ex: contact@domain.com, info@domain.com)
        """
        generic_emails = []

        for prefix in self.generic_emails_to_test:
            email = f"{prefix}@{domain}"
            generic_emails.append(email)

        logger.info(f"  🔧 Génération de {len(generic_emails)} emails génériques à tester")

        return generic_emails

    async def find_all_emails_on_site(self, domain: str) -> List[str]:
        """
        Trouver TOUS les emails sur un site (pas seulement contact@)

        Args:
            domain: Domaine à analyser

        Returns:
            Liste d'emails trouvés
        """
        all_emails = set()

        # Obtenir toutes les pages à vérifier
        pages = self.email_finder.get_pages_to_check(domain)

        # Limiter à 20 pages max pour éviter de surcharger
        pages = pages[:20]

        # Créer les tâches pour toutes les pages
        tasks = [self.email_finder.fetch_page(page) for page in pages]

        # Exécuter toutes les requêtes en parallèle
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Traiter les résultats
        for html in results:
            if isinstance(html, str) and html:
                emails = self.email_finder.extract_emails_from_html(html)
                all_emails.update(emails)

        return list(all_emails)

    async def validate_and_score_emails(self, emails: List[str], is_generic: bool = False) -> List[Tuple[str, int, dict]]:
        """
        Valider tous les emails en parallèle et les scorer

        Args:
            emails: Liste d'emails à valider
            is_generic: Si True, indique que ce sont des emails générés (pas trouvés sur le site)

        Returns:
            Liste de tuples (email, score_total, validation_result)
            Trié par score décroissant
        """
        if not emails:
            return []

        # Valider tous les emails en parallèle avec le validateur async
        validations = await self.email_validator.validate_emails_batch(emails, max_concurrent=50)

        results = []

        for validation in validations:
            try:
                email = validation['email']

                # Ne garder que les emails valides ou risky
                if validation['status'] not in ['valid', 'risky']:
                    smtp_msg = validation['details'].get('smtp', 'N/A')
                    logger.debug(f"  ❌ {email[:40]:40} | INVALIDE - {smtp_msg}")
                    continue

                # Score de préfixe (0-100)
                prefix_score = self.score_email_prefix(email)

                # Score de validation (0-100)
                validation_score = validation['score']

                # Score total = moyenne pondérée
                # 70% validation + 30% préfixe
                total_score = int(validation_score * 0.7 + prefix_score * 0.3)

                # Marquer si c'est un email générique
                validation['is_generic'] = is_generic
                validation['valid'] = validation['status'] == 'valid'

                results.append((email, total_score, validation))

                status_icon = "✅" if validation['deliverable'] else "⚠️"
                generic_marker = " [GÉNÉRÉ]" if is_generic else ""

                logger.info(
                    f"  {status_icon} {email[:40]:40} | "
                    f"Val: {validation_score:3} | "
                    f"Préf: {prefix_score:3} | "
                    f"Tot: {total_score:3} | "
                    f"{validation['status']}{generic_marker}"
                )

            except Exception as e:
                logger.error(f"  ❌ Erreur scoring {validation.get('email', '?')}: {e}")
                continue

        # Trier par score décroissant
        results.sort(key=lambda x: x[1], reverse=True)

        return results

    async def find_best_email(self, site_id: int, site_domain: str, stats: dict) -> None:
        """
        Trouver le meilleur email valide pour un site

        Args:
            site_id: ID du site dans la base
            site_domain: Domaine du site
            stats: Dictionnaire de statistiques
        """
        logger.info(f"\n{'='*80}")
        logger.info(f"🔍 Recherche email valide pour: {site_domain}")
        logger.info(f"{'='*80}")

        # Créer une SESSION DÉDIÉE pour ce site
        engine = get_engine()
        Session = sessionmaker(bind=engine)
        session = Session()

        try:
            # Charger le site depuis la DB
            site = session.query(Site).filter_by(id=site_id).first()
            if not site:
                logger.error(f"❌ Site {site_domain} introuvable en DB")
                return

            # 1. Chercher tous les emails sur le site
            logger.info("📥 Phase 1: Récupération de tous les emails du site...")
            emails_found = await self.find_all_emails_on_site(site_domain)

            scored_emails = []

            if emails_found:
                logger.info(f"✅ {len(emails_found)} email(s) trouvé(s) sur le site")

                # 2. Valider et scorer tous les emails trouvés (async)
                logger.info("🔍 Validation et scoring des emails trouvés...")
                scored_emails = await self.validate_and_score_emails(emails_found, is_generic=False)
            else:
                logger.info(f"❌ Aucun email trouvé sur le site")

            # 3. Si aucun email valide trouvé, générer des emails génériques et les tester
            if not scored_emails:
                logger.info(f"\n{'─'*80}")
                logger.info("📧 Phase 2: FALLBACK - Test d'emails génériques")
                logger.info(f"{'─'*80}")

                # Générer des emails génériques
                generic_emails = self.generate_generic_emails(site_domain)

                # Valider les emails génériques (async)
                logger.info("🔍 Validation des emails génériques...")
                scored_emails = await self.validate_and_score_emails(generic_emails, is_generic=True)

            # 4. Vérifier si on a trouvé au moins un email valide
            if not scored_emails:
                logger.info(f"\n{'='*80}")
                logger.info(f"❌ AUCUN EMAIL VALIDE pour {site_domain}")
                logger.info(f"{'='*80}")

                site.emails = None  # Ne pas stocker de texte, garder NULL
                site.email_source = "any_valid_all_failed"
                site.email_checked = True  # Marquer comme vérifié
                site.status = SiteStatus.EMAIL_NOT_FOUND
                site.updated_at = datetime.utcnow()
                site.retry_count += 1

                # Commit immédiat avec retry
                try:
                    safe_commit(session, max_retries=10)
                except Exception as e:
                    logger.error(f"Erreur commit: {e}")
                    session.rollback()

                stats['no_valid_email'] += 1
                return

            # 5. Prendre le meilleur email (score le plus élevé)
            best_email, best_score, best_validation = scored_emails[0]

            # Déterminer la source
            if best_validation.get('is_generic', False):
                email_source = "generic_validated"
                source_label = "EMAIL GÉNÉRIQUE VALIDÉ"
            else:
                email_source = "any_valid_email"
                source_label = "EMAIL TROUVÉ SUR SITE"

            logger.info(f"\n{'='*80}")
            logger.info(f"🏆 MEILLEUR EMAIL SÉLECTIONNÉ - {source_label}")
            logger.info(f"{'='*80}")
            logger.info(f"  Email: {best_email}")
            logger.info(f"  Score total: {best_score}/100")
            logger.info(f"  Score validation: {best_validation['score']}/100")
            logger.info(f"  Status: {best_validation['status']}")
            logger.info(f"  Deliverable: {'✅' if best_validation['deliverable'] else '❌'}")
            logger.info(f"  Source: {email_source}")
            logger.info(f"{'='*80}")

            # 6. Mettre à jour la base de données
            site.emails = best_email
            site.email_found_at = datetime.utcnow()
            site.email_source = email_source
            site.status = SiteStatus.EMAIL_FOUND

            # Copier les infos de validation
            site.email_validated = True
            site.email_validation_score = best_validation['score']
            site.email_validation_status = best_validation['status']
            site.email_validation_details = str(best_validation['details'])
            site.email_validation_date = datetime.utcnow()
            site.email_deliverable = best_validation['deliverable']

            site.updated_at = datetime.utcnow()
            site.retry_count += 1

            # Commit immédiat avec retry
            try:
                safe_commit(session, max_retries=10)
                logger.info(f"✅ Email enregistré pour {site_domain}")
            except Exception as e:
                logger.error(f"Erreur commit: {e}")
                session.rollback()

            stats['email_found'] += 1

            if best_validation['deliverable']:
                stats['deliverable'] += 1

            if best_validation.get('is_generic', False):
                stats['generic_validated'] += 1
            else:
                stats['found_on_site'] += 1

        except Exception as e:
            logger.error(f"❌ Erreur pour {site_domain}: {e}")
            try:
                site = session.query(Site).filter_by(id=site_id).first()
                if site:
                    site.last_error = str(e)[:500]
                    site.updated_at = datetime.utcnow()
                    site.retry_count += 1
                    safe_commit(session, max_retries=5)
            except:
                pass
            stats['errors'] += 1
        finally:
            session.close()

    async def process_batch(self, sites: List[Tuple[int, str]], stats: dict, parallel_sites: int = 10) -> None:
        """
        Traiter un lot de sites EN PARALLÈLE

        Args:
            sites: Liste de tuples (site_id, domain)
            stats: Dictionnaire de statistiques (thread-safe via asyncio)
            parallel_sites: Nombre de sites à traiter en parallèle
        """
        semaphore = asyncio.Semaphore(parallel_sites)

        async def process_single_site(site_id: int, site_domain: str):
            async with semaphore:
                await self.find_best_email(site_id, site_domain, stats)

        # Créer toutes les tâches et les exécuter en parallèle
        tasks = [process_single_site(site_id, site_domain) for site_id, site_domain in sites]
        await asyncio.gather(*tasks, return_exceptions=True)

        logger.info(f"💾 Batch de {len(sites)} sites traité en parallèle ({parallel_sites} simultanés)")

    async def process_all(self, limit: int = None, batch_size: int = 50, parallel_sites: int = 10):
        """
        Traiter tous les sites sans emails

        Args:
            limit: Nombre maximum de sites à traiter (None = tous)
            batch_size: Taille des lots pour le traitement
            parallel_sites: Nombre de sites à traiter en parallèle dans chaque batch
        """
        start_time = time.time()

        print("\n" + "="*80)
        print("🚀 RECHERCHE D'EMAILS VALIDES - VERSION TURBO PARALLÈLE")
        print("="*80)
        print(f"   Mode 1: Cherche N'IMPORTE QUEL email valide sur le site")
        print(f"   Mode 2: Si rien trouvé → Test emails génériques (contact@, info@, etc.)")
        print(f"   Concurrence HTTP: {self.max_concurrent} requêtes simultanées")
        print(f"   Sites en parallèle: {parallel_sites}")
        print(f"   Batch size: {batch_size} sites par lot")
        if limit:
            print(f"   Limite: {limit:,} sites")
        print("="*80)

        # Initialiser la session
        await self.init_session()

        try:
            # Utiliser l'engine de database.py (PostgreSQL ou SQLite selon config)
            engine = get_engine()
            Session = sessionmaker(bind=engine)
            db_session = Session()

            # Sites sans emails et actifs
            query = db_session.query(Site).filter(
                Site.is_active == True,
                Site.blacklisted == False,
                (
                    (Site.emails == "NO EMAIL FOUND") |
                    (Site.emails == None) |
                    (Site.emails == "")
                )
            ).order_by(Site.created_at.desc())

            if limit:
                sites = query.limit(limit).all()
            else:
                sites = query.all()

            total_sites = len(sites)

            # Extraire seulement (id, domain) pour éviter de garder les objets en mémoire
            sites_data = [(s.id, s.domain) for s in sites]

            # Fermer la session temporaire
            db_session.close()

            print(f"\n📊 Sites à traiter: {total_sites:,}")

            if total_sites == 0:
                print("✅ Aucun site à traiter !")
                return

            stats = {
                'email_found': 0,
                'deliverable': 0,
                'found_on_site': 0,
                'generic_validated': 0,
                'no_valid_email': 0,
                'errors': 0,
            }

            # Traiter par lots
            for i in range(0, total_sites, batch_size):
                batch = sites_data[i:i+batch_size]
                batch_num = i // batch_size + 1
                total_batches = (total_sites + batch_size - 1) // batch_size

                print(f"\n🔄 Lot {batch_num}/{total_batches} ({len(batch)} sites)")
                print("-"*80)

                batch_start = time.time()

                await self.process_batch(batch, stats, parallel_sites=parallel_sites)

                batch_time = time.time() - batch_start
                speed = len(batch) / batch_time if batch_time > 0 else 0

                print(f"\n⏱️  Lot traité en {batch_time:.1f}s ({speed:.2f} sites/sec)")
                print(f"   Emails trouvés dans ce lot: {stats['email_found']}")
                print(f"   └─ Trouvés sur site: {stats['found_on_site']}")
                print(f"   └─ Génériques validés: {stats['generic_validated']}")

                # Pause entre les lots
                if i + batch_size < total_sites:
                    await asyncio.sleep(2)

            # Résumé final
            total_time = time.time() - start_time
            success_rate = (stats['email_found'] / total_sites * 100) if total_sites > 0 else 0
            deliverable_rate = (stats['deliverable'] / stats['email_found'] * 100) if stats['email_found'] > 0 else 0
            generic_rate = (stats['generic_validated'] / stats['email_found'] * 100) if stats['email_found'] > 0 else 0

            print("\n" + "="*80)
            print("✅ TRAITEMENT TERMINÉ!")
            print("="*80)
            print(f"   Temps total: {total_time:.1f}s ({total_time/60:.1f} minutes)")
            print(f"   Sites traités: {total_sites:,}")
            print(f"   Emails trouvés: {stats['email_found']:,} ({success_rate:.1f}%)")
            print(f"     ├─ Trouvés sur site: {stats['found_on_site']:,}")
            print(f"     └─ Génériques validés: {stats['generic_validated']:,} ({generic_rate:.1f}%)")
            print(f"   Deliverable: {stats['deliverable']:,} ({deliverable_rate:.1f}%)")
            print(f"   Aucun email valide: {stats['no_valid_email']:,}")
            print(f"   Erreurs: {stats['errors']:,}")
            print(f"   Vitesse moyenne: {total_sites/total_time:.2f} sites/sec")
            print("="*80)
            print(f"\n💡 Gain: {stats['email_found']:,} nouveaux contacts qualifiés !")
            print(f"📧 Deliverable: {stats['deliverable']:,} emails prêts pour campagne")
            print(f"🔧 Emails génériques: {stats['generic_validated']:,} (validés SMTP)")
            print("🎯 Consultez l'admin: https://admin.perfect-cocon-seo.fr")

        finally:
            await self.close_session()


async def main():
    """Point d'entrée principal"""
    parser = argparse.ArgumentParser(
        description="Recherche d'emails valides - VERSION TURBO PARALLÈLE"
    )
    parser.add_argument('--limit', type=int, default=None, help='Nombre max de sites à traiter')
    parser.add_argument('--concurrent', type=int, default=50, help='Nombre de requêtes HTTP simultanées')
    parser.add_argument('--batch-size', type=int, default=100, help='Taille des lots')
    parser.add_argument('--parallel-sites', type=int, default=20, help='Nombre de sites traités en parallèle')

    args = parser.parse_args()

    finder = AnyValidEmailFinder(max_concurrent=args.concurrent)

    await finder.process_all(
        limit=args.limit,
        batch_size=args.batch_size,
        parallel_sites=args.parallel_sites
    )


if __name__ == "__main__":
    asyncio.run(main())
