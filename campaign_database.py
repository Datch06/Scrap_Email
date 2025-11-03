#!/usr/bin/env python3
"""
Base de données pour les campagnes d'emails
"""

from datetime import datetime
from sqlalchemy import create_engine, Column, Integer, String, Text, DateTime, Boolean, Enum, Float, ForeignKey
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship
import enum

Base = declarative_base()


class CampaignStatus(enum.Enum):
    """Statut d'une campagne"""
    DRAFT = "draft"  # Brouillon
    SCHEDULED = "scheduled"  # Planifiée
    RUNNING = "running"  # En cours d'envoi
    PAUSED = "paused"  # En pause
    COMPLETED = "completed"  # Terminée
    CANCELLED = "cancelled"  # Annulée


class EmailStatus(enum.Enum):
    """Statut d'un email envoyé"""
    PENDING = "pending"  # En attente d'envoi
    SENT = "sent"  # Envoyé
    DELIVERED = "delivered"  # Délivré
    OPENED = "opened"  # Ouvert
    CLICKED = "clicked"  # Cliqué
    BOUNCED = "bounced"  # Rebondi
    COMPLAINED = "complained"  # Marqué comme spam
    UNSUBSCRIBED = "unsubscribed"  # Désabonné
    FAILED = "failed"  # Échec d'envoi


class Campaign(Base):
    """Modèle pour une campagne d'emails"""
    __tablename__ = 'campaigns'

    id = Column(Integer, primary_key=True)
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)

    # Statut
    status = Column(Enum(CampaignStatus), default=CampaignStatus.DRAFT, index=True)

    # Template
    template_id = Column(Integer, ForeignKey('email_templates.id'), nullable=True)
    subject = Column(String(500), nullable=False)
    html_body = Column(Text, nullable=False)
    text_body = Column(Text, nullable=True)

    # Configuration d'envoi
    from_email = Column(String(255), nullable=False)
    from_name = Column(String(255), nullable=False)
    reply_to = Column(String(255), nullable=True)

    # Filtres de destinataires
    min_validation_score = Column(Integer, default=80)  # Score minimum pour l'envoi
    only_deliverable = Column(Boolean, default=True)  # Uniquement emails délivrables
    exclude_domains = Column(Text, nullable=True)  # Domaines à exclure (séparés par virgules)

    # Planification
    scheduled_at = Column(DateTime, nullable=True)
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)

    # Limites d'envoi
    max_emails_per_day = Column(Integer, default=200)
    delay_between_emails = Column(Integer, default=2)  # secondes

    # Statistiques
    total_recipients = Column(Integer, default=0)
    emails_sent = Column(Integer, default=0)
    emails_delivered = Column(Integer, default=0)
    emails_opened = Column(Integer, default=0)
    emails_clicked = Column(Integer, default=0)
    emails_bounced = Column(Integer, default=0)
    emails_complained = Column(Integer, default=0)
    emails_failed = Column(Integer, default=0)

    # Métadonnées
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    created_by = Column(String(100), nullable=True)

    # Relations
    emails = relationship("CampaignEmail", back_populates="campaign", cascade="all, delete-orphan")

    def to_dict(self):
        """Convertir en dictionnaire"""
        return {
            'id': self.id,
            'name': self.name,
            'description': self.description,
            'status': self.status.value if self.status else None,
            'subject': self.subject,
            'from_email': self.from_email,
            'from_name': self.from_name,
            'reply_to': self.reply_to,
            'min_validation_score': self.min_validation_score,
            'only_deliverable': self.only_deliverable,
            'scheduled_at': self.scheduled_at.isoformat() if self.scheduled_at else None,
            'started_at': self.started_at.isoformat() if self.started_at else None,
            'completed_at': self.completed_at.isoformat() if self.completed_at else None,
            'max_emails_per_day': self.max_emails_per_day,
            'total_recipients': self.total_recipients,
            'emails_sent': self.emails_sent,
            'emails_delivered': self.emails_delivered,
            'emails_opened': self.emails_opened,
            'emails_clicked': self.emails_clicked,
            'emails_bounced': self.emails_bounced,
            'emails_complained': self.emails_complained,
            'emails_failed': self.emails_failed,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
            # Stats calculées
            'open_rate': round((self.emails_opened / self.emails_sent * 100) if self.emails_sent > 0 else 0, 2),
            'click_rate': round((self.emails_clicked / self.emails_sent * 100) if self.emails_sent > 0 else 0, 2),
            'bounce_rate': round((self.emails_bounced / self.emails_sent * 100) if self.emails_sent > 0 else 0, 2),
        }


class EmailTemplate(Base):
    """Modèle pour les templates d'emails"""
    __tablename__ = 'email_templates'

    id = Column(Integer, primary_key=True)
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    category = Column(String(100), nullable=True)  # Ex: "prospection", "suivi", etc.

    subject = Column(String(500), nullable=False)
    html_body = Column(Text, nullable=False)
    text_body = Column(Text, nullable=True)

    # Variables disponibles (JSON)
    available_variables = Column(Text, nullable=True)  # ["domain", "contact", "siret", etc.]

    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'description': self.description,
            'category': self.category,
            'subject': self.subject,
            'html_body': self.html_body,
            'text_body': self.text_body,
            'available_variables': self.available_variables,
            'is_active': self.is_active,
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }


class CampaignEmail(Base):
    """Modèle pour suivre chaque email envoyé dans une campagne"""
    __tablename__ = 'campaign_emails'

    id = Column(Integer, primary_key=True)
    campaign_id = Column(Integer, ForeignKey('campaigns.id'), nullable=False, index=True)
    site_id = Column(Integer, nullable=False, index=True)  # Référence à la table sites

    # Destinataire
    to_email = Column(String(255), nullable=False, index=True)
    to_domain = Column(String(255), nullable=True)

    # Statut
    status = Column(Enum(EmailStatus), default=EmailStatus.PENDING, index=True)

    # IDs Amazon SES
    message_id = Column(String(255), nullable=True, unique=True, index=True)

    # Dates
    sent_at = Column(DateTime, nullable=True)
    delivered_at = Column(DateTime, nullable=True)
    opened_at = Column(DateTime, nullable=True)
    clicked_at = Column(DateTime, nullable=True)
    bounced_at = Column(DateTime, nullable=True)

    # Tracking
    open_count = Column(Integer, default=0)
    click_count = Column(Integer, default=0)

    # Erreurs
    error_message = Column(Text, nullable=True)
    bounce_type = Column(String(50), nullable=True)  # "hard" ou "soft"

    # Métadonnées
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relations
    campaign = relationship("Campaign", back_populates="emails")

    def to_dict(self):
        return {
            'id': self.id,
            'campaign_id': self.campaign_id,
            'site_id': self.site_id,
            'to_email': self.to_email,
            'to_domain': self.to_domain,
            'status': self.status.value if self.status else None,
            'message_id': self.message_id,
            'sent_at': self.sent_at.isoformat() if self.sent_at else None,
            'delivered_at': self.delivered_at.isoformat() if self.delivered_at else None,
            'opened_at': self.opened_at.isoformat() if self.opened_at else None,
            'clicked_at': self.clicked_at.isoformat() if self.clicked_at else None,
            'open_count': self.open_count,
            'click_count': self.click_count,
            'error_message': self.error_message,
        }


class Unsubscribe(Base):
    """Liste des désabonnements"""
    __tablename__ = 'unsubscribes'

    id = Column(Integer, primary_key=True)
    email = Column(String(255), nullable=False, unique=True, index=True)
    reason = Column(Text, nullable=True)
    unsubscribed_at = Column(DateTime, default=datetime.utcnow)
    campaign_id = Column(Integer, nullable=True)  # Campagne à l'origine du désabonnement


# Configuration de la base de données
DATABASE_URL = 'sqlite:///campaigns.db'

def init_campaign_db():
    """Initialiser la base de données des campagnes"""
    engine = create_engine(DATABASE_URL)
    Base.metadata.create_all(engine)
    return engine

def get_campaign_session():
    """Obtenir une session de base de données"""
    engine = create_engine(DATABASE_URL)
    Session = sessionmaker(bind=engine)
    return Session()


if __name__ == '__main__':
    print("Création de la base de données des campagnes...")
    init_campaign_db()
    print("✓ Base de données créée avec succès : campaigns.db")
