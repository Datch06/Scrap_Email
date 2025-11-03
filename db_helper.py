#!/usr/bin/env python3
"""
Helper pour intégrer les scripts existants avec la base de données
"""

from datetime import datetime
from database import get_session, Site, ScrapingJob, SiteStatus


class DBHelper:
    """Classe utilitaire pour faciliter l'intégration avec la base de données"""

    def __init__(self):
        self.session = get_session()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.session.close()

    def add_site(self, domain, source_url=None):
        """Ajouter un nouveau site ou récupérer s'il existe déjà"""
        site = self.session.query(Site).filter(Site.domain == domain).first()

        if not site:
            site = Site(
                domain=domain,
                source_url=source_url,
                status=SiteStatus.DISCOVERED
            )
            self.session.add(site)
            self.session.commit()
            print(f"✓ Ajouté: {domain}")
        else:
            print(f"⏭ Existe déjà: {domain}")

        return site

    def update_email(self, domain, emails, email_source='scraping'):
        """Mettre à jour les emails d'un site

        Args:
            domain: Le nom de domaine
            emails: Les emails trouvés
            email_source: Source de l'email ('scraping' ou 'siret')
        """
        site = self.session.query(Site).filter(Site.domain == domain).first()

        if not site:
            print(f"⚠ Site non trouvé: {domain}")
            return None

        site.emails = emails
        site.email_source = email_source
        site.email_checked = True

        if emails and emails != 'NO EMAIL FOUND':
            site.email_found_at = datetime.utcnow()
            site.status = SiteStatus.EMAIL_FOUND
        else:
            site.status = SiteStatus.EMAIL_NOT_FOUND

        site.updated_at = datetime.utcnow()
        self.session.commit()

        return site

    def update_siret(self, domain, siret, siret_type='SIRET'):
        """Mettre à jour le SIRET/SIREN d'un site"""
        site = self.session.query(Site).filter(Site.domain == domain).first()

        if not site:
            print(f"⚠ Site non trouvé: {domain}")
            return None

        site.siret = siret
        site.siret_type = siret_type
        site.siret_checked = True

        if siret and siret != 'NON TROUVÉ':
            site.siret_found_at = datetime.utcnow()
            site.status = SiteStatus.SIRET_FOUND
            # Extraire le SIREN (9 premiers chiffres)
            if len(siret) >= 9:
                site.siren = siret[:9]
        else:
            site.status = SiteStatus.SIRET_NOT_FOUND

        site.updated_at = datetime.utcnow()
        self.session.commit()

        return site

    def update_leaders(self, domain, leaders):
        """Mettre à jour les dirigeants d'un site"""
        site = self.session.query(Site).filter(Site.domain == domain).first()

        if not site:
            print(f"⚠ Site non trouvé: {domain}")
            return None

        # Convertir liste en string si nécessaire
        if isinstance(leaders, list):
            leaders_str = '; '.join(leaders)
        else:
            leaders_str = leaders

        site.leaders = leaders_str
        site.leaders_checked = True

        if leaders_str and leaders_str != 'NON TROUVÉ':
            site.leaders_found_at = datetime.utcnow()
            site.status = SiteStatus.LEADERS_FOUND

            # Vérifier si le site est complet
            if site.emails and site.siret:
                site.status = SiteStatus.COMPLETED
        else:
            # Pas de dirigeants trouvés, mais vérifier si email + SIRET présents
            if site.emails and site.siret:
                site.status = SiteStatus.SIRET_FOUND  # Au moins email + SIRET

        site.updated_at = datetime.utcnow()
        self.session.commit()

        return site

    def set_error(self, domain, error_message):
        """Marquer un site comme ayant une erreur"""
        site = self.session.query(Site).filter(Site.domain == domain).first()

        if not site:
            print(f"⚠ Site non trouvé: {domain}")
            return None

        site.status = SiteStatus.ERROR
        site.last_error = error_message
        site.retry_count += 1
        site.updated_at = datetime.utcnow()
        self.session.commit()

        return site

    def get_sites_for_processing(self, status=None, limit=None):
        """Récupérer les sites à traiter"""
        query = self.session.query(Site)

        if status:
            query = query.filter(Site.status == status)

        if limit:
            query = query.limit(limit)

        return query.all()

    def get_sites_without_email(self, limit=None):
        """Récupérer les sites sans email"""
        query = self.session.query(Site).filter(
            (Site.email_checked == False) |
            (Site.emails.is_(None)) |
            (Site.emails == '')
        )

        if limit:
            query = query.limit(limit)

        return query.all()

    def get_sites_without_siret(self, limit=None):
        """Récupérer les sites sans SIRET"""
        query = self.session.query(Site).filter(
            (Site.siret_checked == False) |
            (Site.siret.is_(None)) |
            (Site.siret == '')
        )

        if limit:
            query = query.limit(limit)

        return query.all()

    def get_sites_without_leaders(self, limit=None):
        """Récupérer les sites avec SIRET mais sans dirigeants"""
        query = self.session.query(Site).filter(
            Site.siret.isnot(None),
            Site.siret != '',
            Site.siret != 'NON TROUVÉ',
            (Site.leaders_checked == False) |
            (Site.leaders.is_(None)) |
            (Site.leaders == '')
        )

        if limit:
            query = query.limit(limit)

        return query.all()

    def create_job(self, job_type, total_sites=0, config=None):
        """Créer un nouveau job"""
        import json

        job = ScrapingJob(
            job_type=job_type,
            status='pending',
            total_sites=total_sites,
            config=json.dumps(config) if config else None
        )
        self.session.add(job)
        self.session.commit()

        return job

    def start_job(self, job_id):
        """Démarrer un job"""
        job = self.session.query(ScrapingJob).filter(ScrapingJob.id == job_id).first()
        if job:
            job.status = 'running'
            job.start_time = datetime.utcnow()
            self.session.commit()
        return job

    def update_job_progress(self, job_id, processed=None, success=None, error=None):
        """Mettre à jour la progression d'un job"""
        job = self.session.query(ScrapingJob).filter(ScrapingJob.id == job_id).first()
        if job:
            if processed is not None:
                job.processed_sites = processed
            if success is not None:
                job.success_count = success
            if error is not None:
                job.error_count = error
            self.session.commit()
        return job

    def complete_job(self, job_id, status='completed'):
        """Terminer un job"""
        job = self.session.query(ScrapingJob).filter(ScrapingJob.id == job_id).first()
        if job:
            job.status = status
            job.end_time = datetime.utcnow()
            self.session.commit()
        return job

    def get_stats(self):
        """Obtenir des statistiques rapides"""
        total = self.session.query(Site).count()
        with_email = self.session.query(Site).filter(
            Site.emails.isnot(None),
            Site.emails != '',
            Site.emails != 'NO EMAIL FOUND'
        ).count()
        with_siret = self.session.query(Site).filter(
            Site.siret.isnot(None),
            Site.siret != '',
            Site.siret != 'NON TROUVÉ'
        ).count()
        with_leaders = self.session.query(Site).filter(
            Site.leaders.isnot(None),
            Site.leaders != '',
            Site.leaders != 'NON TROUVÉ'
        ).count()

        return {
            'total': total,
            'with_email': with_email,
            'with_siret': with_siret,
            'with_leaders': with_leaders,
        }


# Exemple d'utilisation
if __name__ == '__main__':
    print("Test du DBHelper")
    print("=" * 60)

    with DBHelper() as db:
        # Ajouter un site de test
        site = db.add_site('example.fr', 'https://source.com')

        # Mettre à jour avec un email
        db.update_email('example.fr', 'contact@example.fr')

        # Mettre à jour avec SIRET
        db.update_siret('example.fr', '12345678901234', 'SIRET')

        # Mettre à jour avec dirigeants
        db.update_leaders('example.fr', ['Jean Dupont', 'Marie Martin'])

        # Afficher les stats
        stats = db.get_stats()
        print("\nStatistiques:")
        print(f"  Total: {stats['total']}")
        print(f"  Avec email: {stats['with_email']}")
        print(f"  Avec SIRET: {stats['with_siret']}")
        print(f"  Avec dirigeants: {stats['with_leaders']}")

    print("\n✓ Test terminé")
