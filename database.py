#!/usr/bin/env python3
"""
Base de données pour le suivi des sites et leur état de traitement
"""

from datetime import datetime
from sqlalchemy import create_engine, Column, Integer, String, Text, DateTime, Boolean, Enum, Float
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
import enum

Base = declarative_base()


class SiteStatus(enum.Enum):
    """Statut général du site"""
    DISCOVERED = "discovered"  # Site découvert
    EMAIL_PENDING = "email_pending"  # En attente extraction email
    EMAIL_FOUND = "email_found"  # Email trouvé
    EMAIL_NOT_FOUND = "email_not_found"  # Email non trouvé
    SIRET_PENDING = "siret_pending"  # En attente extraction SIRET
    SIRET_FOUND = "siret_found"  # SIRET trouvé
    SIRET_NOT_FOUND = "siret_not_found"  # SIRET non trouvé
    LEADERS_PENDING = "leaders_pending"  # En attente extraction dirigeants
    LEADERS_FOUND = "leaders_found"  # Dirigeants trouvés
    COMPLETED = "completed"  # Traitement complet
    ERROR = "error"  # Erreur lors du traitement


class Site(Base):
    """Modèle pour les sites web découverts"""
    __tablename__ = 'sites'

    id = Column(Integer, primary_key=True)
    domain = Column(String(255), unique=True, nullable=False, index=True)
    source_url = Column(String(500))  # URL d'où le site a été découvert

    # Statuts
    status = Column(Enum(SiteStatus), default=SiteStatus.DISCOVERED, index=True)

    # Emails
    email_checked = Column(Boolean, default=False)
    email_found_at = Column(DateTime, nullable=True)
    emails = Column(Text, nullable=True)  # Stocké en format "email1; email2; email3"
    email_source = Column(String(20), nullable=True)  # "scraping" ou "siret" pour différencier la source

    # SIRET/SIREN
    siret_checked = Column(Boolean, default=False)
    siret_found_at = Column(DateTime, nullable=True)
    siret = Column(String(14), nullable=True)
    siren = Column(String(9), nullable=True)
    siret_type = Column(String(10), nullable=True)  # "SIRET" ou "SIREN"

    # Dirigeants
    leaders_checked = Column(Boolean, default=False)
    leaders_found_at = Column(DateTime, nullable=True)
    leaders = Column(Text, nullable=True)  # Stocké en format "nom1; nom2; nom3"

    # Validation d'email
    email_validated = Column(Boolean, default=False)
    email_validation_score = Column(Integer, default=0)  # Score 0-100
    email_validation_status = Column(String(20), nullable=True)  # 'valid', 'invalid', 'risky', 'unknown'
    email_validation_details = Column(Text, nullable=True)  # JSON avec détails
    email_validation_date = Column(DateTime, nullable=True)
    email_deliverable = Column(Boolean, default=False)

    # Détection CMS
    cms = Column(String(50), nullable=True)  # WordPress, Joomla, Drupal, PrestaShop, etc.
    cms_version = Column(String(20), nullable=True)  # Version du CMS si détectable
    cms_detected_at = Column(DateTime, nullable=True)  # Date de détection

    # Blacklist
    blacklisted = Column(Boolean, default=False, index=True)
    blacklist_reason = Column(Text, nullable=True)
    blacklisted_at = Column(DateTime, nullable=True)

    # Activation/Désactivation
    is_active = Column(Boolean, default=True, index=True)  # Permet de désactiver un site sans le supprimer

    # Tracking LinkAvista
    is_linkavista_seller = Column(Boolean, default=False, index=True)  # Site est un vendeur de backlinks de LinkAvista
    purchased_from = Column(String(255), nullable=True)  # Site vendeur d'où ce site a acheté un backlink

    # Métadonnées
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    last_error = Column(Text, nullable=True)
    retry_count = Column(Integer, default=0)

    # Feuille Google Sheets
    sheet_name = Column(String(50), nullable=True)  # "Feuille 1", "Feuille 2", etc.
    sheet_row = Column(Integer, nullable=True)

    def to_dict(self):
        """Convertir en dictionnaire pour JSON"""
        return {
            'id': self.id,
            'domain': self.domain,
            'source_url': self.source_url,
            'status': self.status.value if self.status else None,
            'email_checked': self.email_checked,
            'email_found_at': self.email_found_at.isoformat() if self.email_found_at else None,
            'emails': self.emails,
            'email_source': self.email_source,
            'email_validated': self.email_validated,
            'email_validation_score': self.email_validation_score,
            'email_validation_status': self.email_validation_status,
            'email_deliverable': self.email_deliverable,
            'email_validation_date': self.email_validation_date.isoformat() if self.email_validation_date else None,
            'siret_checked': self.siret_checked,
            'siret_found_at': self.siret_found_at.isoformat() if self.siret_found_at else None,
            'siret': self.siret,
            'siren': self.siren,
            'siret_type': self.siret_type,
            'leaders_checked': self.leaders_checked,
            'leaders_found_at': self.leaders_found_at.isoformat() if self.leaders_found_at else None,
            'leaders': self.leaders,
            'blacklisted': self.blacklisted,
            'is_active': self.is_active if hasattr(self, 'is_active') else True,
            'is_linkavista_seller': self.is_linkavista_seller if hasattr(self, 'is_linkavista_seller') else False,
            'purchased_from': self.purchased_from if hasattr(self, 'purchased_from') else None,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
            'last_error': self.last_error,
            'retry_count': self.retry_count,
            'sheet_name': self.sheet_name,
            'sheet_row': self.sheet_row,
        }


class ScrapingJob(Base):
    """Suivi des jobs de scraping"""
    __tablename__ = 'scraping_jobs'

    id = Column(Integer, primary_key=True)
    job_type = Column(String(50), nullable=False)  # "crawl", "email", "siret", "leaders"
    status = Column(String(20), default="pending")  # "pending", "running", "completed", "failed"
    start_time = Column(DateTime, nullable=True)
    end_time = Column(DateTime, nullable=True)
    total_sites = Column(Integer, default=0)
    processed_sites = Column(Integer, default=0)
    success_count = Column(Integer, default=0)
    error_count = Column(Integer, default=0)
    log_file = Column(String(255), nullable=True)
    config = Column(Text, nullable=True)  # JSON avec configuration du job
    created_at = Column(DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {
            'id': self.id,
            'job_type': self.job_type,
            'status': self.status,
            'start_time': self.start_time.isoformat() if self.start_time else None,
            'end_time': self.end_time.isoformat() if self.end_time else None,
            'total_sites': self.total_sites,
            'processed_sites': self.processed_sites,
            'success_count': self.success_count,
            'error_count': self.error_count,
            'log_file': self.log_file,
            'config': self.config,
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }


# Configuration de la base de données
DATABASE_URL = 'sqlite:///scrap_email.db'

def init_db():
    """Initialiser la base de données"""
    engine = create_engine(DATABASE_URL)
    Base.metadata.create_all(engine)
    return engine

def get_session():
    """Obtenir une session de base de données"""
    engine = create_engine(DATABASE_URL)
    Session = sessionmaker(bind=engine)
    return Session()


if __name__ == '__main__':
    print("Création de la base de données...")
    init_db()
    print("✓ Base de données créée avec succès : scrap_email.db")
