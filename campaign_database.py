#!/usr/bin/env python3
"""
Base de données pour les campagnes d'emails
"""

from datetime import datetime
from sqlalchemy import create_engine, Column, Integer, String, Text, DateTime, Boolean, Enum, Float, ForeignKey
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship
import enum
import json

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
    segment_id = Column(Integer, ForeignKey('contact_segments.id'), nullable=True, index=True)  # Segment ciblé
    min_validation_score = Column(Integer, default=80)  # Score minimum pour l'envoi
    only_deliverable = Column(Boolean, default=True)  # Uniquement emails délivrables
    exclude_domains = Column(Text, nullable=True)  # Domaines à exclure (séparés par virgules)

    # Type de campagne
    is_continuous = Column(Boolean, default=False)  # Campagne continue qui envoie automatiquement aux nouveaux contacts

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
    emails_unsubscribed = Column(Integer, default=0)

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
            'segment_id': self.segment_id,
            'min_validation_score': self.min_validation_score,
            'only_deliverable': self.only_deliverable,
            'is_continuous': self.is_continuous,
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
            'emails_unsubscribed': self.emails_unsubscribed,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
            # Stats calculées
            'open_rate': round((self.emails_opened / self.emails_sent * 100) if self.emails_sent > 0 else 0, 2),
            'click_rate': round((self.emails_clicked / self.emails_sent * 100) if self.emails_sent > 0 else 0, 2),
            'bounce_rate': round((self.emails_bounced / self.emails_sent * 100) if self.emails_sent > 0 else 0, 2),
            'unsubscribed_rate': round((self.emails_unsubscribed / self.emails_sent * 100) if self.emails_sent > 0 else 0, 2),
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
    campaign_id = Column(Integer, ForeignKey('campaigns.id'), nullable=True, index=True)  # Nullable for scenario emails
    sequence_id = Column(Integer, ForeignKey('contact_sequences.id'), nullable=True, index=True)  # Link to scenario sequence
    variant_id = Column(Integer, ForeignKey('step_template_variants.id'), nullable=True, index=True)  # A/B test variant
    site_id = Column(Integer, nullable=False, index=True)  # Référence à la table sites

    # Destinataire
    to_email = Column(String(255), nullable=False, index=True)
    to_domain = Column(String(255), nullable=True)

    # Expéditeur
    from_name = Column(String(255), nullable=True)
    from_email = Column(String(255), nullable=True)

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
    bounce_reason = Column(Text, nullable=True)  # Raison détaillée du bounce

    # Métadonnées
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relations
    campaign = relationship("Campaign", back_populates="emails")
    sequence = relationship("ContactSequence", back_populates="emails", foreign_keys=[sequence_id])

    def to_dict(self):
        return {
            'id': self.id,
            'campaign_id': self.campaign_id,
            'site_id': self.site_id,
            'to_email': self.to_email,
            'to_domain': self.to_domain,
            'from_name': self.from_name,
            'from_email': self.from_email,
            'status': self.status.value if self.status else None,
            'message_id': self.message_id,
            'sent_at': self.sent_at.isoformat() if self.sent_at else None,
            'delivered_at': self.delivered_at.isoformat() if self.delivered_at else None,
            'opened_at': self.opened_at.isoformat() if self.opened_at else None,
            'clicked_at': self.clicked_at.isoformat() if self.clicked_at else None,
            'open_count': self.open_count,
            'click_count': self.click_count,
            'error_message': self.error_message,
            'bounce_type': self.bounce_type,
            'bounce_reason': self.bounce_reason,
            'bounced_at': self.bounced_at.isoformat() if self.bounced_at else None,
        }


class ScenarioStatus(enum.Enum):
    """Statut d'un scénario"""
    DRAFT = "draft"  # Brouillon
    ACTIVE = "active"  # Actif
    PAUSED = "paused"  # En pause
    COMPLETED = "completed"  # Terminé
    ARCHIVED = "archived"  # Archivé


class StepTrigger(enum.Enum):
    """Type de déclencheur pour une étape"""
    ENTRY = "entry"  # Point d'entrée du scénario
    OPENED = "opened"  # Email ouvert
    NOT_OPENED = "not_opened"  # Email non ouvert après délai
    CLICKED = "clicked"  # Lien cliqué
    NOT_CLICKED = "not_clicked"  # Lien non cliqué après délai
    REPLIED = "replied"  # Réponse reçue
    DELAY = "delay"  # Délai fixe après l'étape précédente


class SequenceStatus(enum.Enum):
    """Statut d'un contact dans une séquence"""
    ACTIVE = "active"  # Séquence active
    COMPLETED = "completed"  # Séquence terminée
    STOPPED = "stopped"  # Arrêtée (réponse, désinscription)
    FAILED = "failed"  # Échec


class Scenario(Base):
    """Modèle pour un scénario d'automatisation d'emails"""
    __tablename__ = 'scenarios'

    id = Column(Integer, primary_key=True)
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    status = Column(Enum(ScenarioStatus), default=ScenarioStatus.DRAFT, index=True)

    # Template d'entrée
    entry_template_id = Column(Integer, ForeignKey('email_templates.id'), nullable=True)

    # Segment de contacts ciblé
    segment_id = Column(Integer, ForeignKey('contact_segments.id'), nullable=True)

    # Contraintes d'envoi
    daily_cap = Column(Integer, default=500)
    cooldown_days = Column(Integer, default=3)  # Jours entre deux emails au même contact
    send_window_start = Column(String(10), default='09:00')  # Format HH:MM
    send_window_end = Column(String(10), default='17:30')
    send_days = Column(String(50), default='mon,tue,wed,thu,fri')  # Jours d'envoi
    timezone = Column(String(50), default='Europe/Paris')

    # Filtres de contacts
    min_validation_score = Column(Integer, default=80)
    only_deliverable = Column(Boolean, default=True)

    # Compliance
    include_unsubscribe = Column(Boolean, default=True)
    stop_on_reply = Column(Boolean, default=True)
    stop_on_unsubscribe = Column(Boolean, default=True)

    # Statistiques
    total_contacts_entered = Column(Integer, default=0)
    total_emails_sent = Column(Integer, default=0)
    active_sequences = Column(Integer, default=0)
    completed_sequences = Column(Integer, default=0)

    # Métadonnées
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    created_by = Column(String(100), nullable=True)

    # Relations
    steps = relationship("ScenarioStep", back_populates="scenario", cascade="all, delete-orphan", order_by="ScenarioStep.step_order")
    sequences = relationship("ContactSequence", back_populates="scenario", cascade="all, delete-orphan")

    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'description': self.description,
            'status': self.status.value if self.status else None,
            'segment_id': self.segment_id,
            'entry_template_id': self.entry_template_id,
            'daily_cap': self.daily_cap,
            'cooldown_days': self.cooldown_days,
            'send_window_start': self.send_window_start,
            'send_window_end': self.send_window_end,
            'send_days': self.send_days,
            'timezone': self.timezone,
            'min_validation_score': self.min_validation_score,
            'only_deliverable': self.only_deliverable,
            'include_unsubscribe': self.include_unsubscribe,
            'stop_on_reply': self.stop_on_reply,
            'stop_on_unsubscribe': self.stop_on_unsubscribe,
            'total_contacts_entered': self.total_contacts_entered,
            'total_emails_sent': self.total_emails_sent,
            'active_sequences': self.active_sequences,
            'completed_sequences': self.completed_sequences,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
            'steps': [step.to_dict() for step in self.steps] if self.steps else []
        }


class ScenarioStep(Base):
    """Étape d'un scénario"""
    __tablename__ = 'scenario_steps'

    id = Column(Integer, primary_key=True)
    scenario_id = Column(Integer, ForeignKey('scenarios.id'), nullable=False, index=True)
    step_order = Column(Integer, nullable=False)  # Ordre d'affichage
    step_name = Column(String(100), nullable=True)

    # Déclencheur
    trigger_type = Column(Enum(StepTrigger), nullable=False, index=True)
    delay_days = Column(Integer, default=0)
    delay_hours = Column(Integer, default=0)

    # Conditions (pour les triggers conditionnels)
    parent_step_id = Column(Integer, ForeignKey('scenario_steps.id'), nullable=True)  # Étape parente

    # Action : envoyer un email
    template_id = Column(Integer, ForeignKey('email_templates.id'), nullable=False)

    # Métadonnées
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relations
    scenario = relationship("Scenario", back_populates="steps")
    parent_step = relationship("ScenarioStep", remote_side=[id], backref="child_steps")
    template_variants = relationship("StepTemplateVariant", back_populates="step", cascade="all, delete-orphan")

    def to_dict(self):
        return {
            'id': self.id,
            'scenario_id': self.scenario_id,
            'step_order': self.step_order,
            'step_name': self.step_name,
            'trigger_type': self.trigger_type.value if self.trigger_type else None,
            'delay_days': self.delay_days,
            'delay_hours': self.delay_hours,
            'parent_step_id': self.parent_step_id,
            'template_id': self.template_id,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }


class StepTemplateVariant(Base):
    """Variante de template pour A/B testing"""
    __tablename__ = 'step_template_variants'

    id = Column(Integer, primary_key=True)
    step_id = Column(Integer, ForeignKey('scenario_steps.id'), nullable=False, index=True)
    template_id = Column(Integer, ForeignKey('email_templates.id'), nullable=False)

    # Poids pour la distribution (ex: 50 = 50% des contacts)
    weight = Column(Integer, default=50, nullable=False)

    # Nom de la variante (ex: "Variante A", "Version formelle")
    variant_name = Column(String(100), nullable=True)

    # Statistiques
    sent_count = Column(Integer, default=0)
    opened_count = Column(Integer, default=0)
    clicked_count = Column(Integer, default=0)

    created_at = Column(DateTime, default=datetime.utcnow)

    # Relations
    step = relationship("ScenarioStep", back_populates="template_variants")
    template = relationship("EmailTemplate")

    def to_dict(self):
        return {
            'id': self.id,
            'step_id': self.step_id,
            'template_id': self.template_id,
            'weight': self.weight,
            'variant_name': self.variant_name,
            'sent_count': self.sent_count,
            'opened_count': self.opened_count,
            'clicked_count': self.clicked_count,
            'open_rate': round((self.opened_count / self.sent_count * 100) if self.sent_count > 0 else 0, 2),
            'click_rate': round((self.clicked_count / self.sent_count * 100) if self.sent_count > 0 else 0, 2)
        }


class ContactSequence(Base):
    """État d'un contact dans une séquence"""
    __tablename__ = 'contact_sequences'

    id = Column(Integer, primary_key=True)
    scenario_id = Column(Integer, ForeignKey('scenarios.id'), nullable=False, index=True)
    contact_id = Column(Integer, nullable=False, index=True)  # ID du site

    current_step_id = Column(Integer, ForeignKey('scenario_steps.id'), nullable=True)
    status = Column(Enum(SequenceStatus), default=SequenceStatus.ACTIVE, index=True)
    stop_reason = Column(String(100), nullable=True)

    # Timestamps
    entered_at = Column(DateTime, default=datetime.utcnow, index=True)
    last_action_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    next_action_at = Column(DateTime, nullable=True, index=True)  # Prochain envoi planifié

    # Statistiques
    total_emails_sent = Column(Integer, default=0)
    last_email_sent_at = Column(DateTime, nullable=True)

    # Relations
    scenario = relationship("Scenario", back_populates="sequences")
    current_step = relationship("ScenarioStep", foreign_keys=[current_step_id])
    emails = relationship("CampaignEmail", back_populates="sequence", foreign_keys="CampaignEmail.sequence_id")

    def to_dict(self):
        return {
            'id': self.id,
            'scenario_id': self.scenario_id,
            'contact_id': self.contact_id,
            'current_step_id': self.current_step_id,
            'status': self.status.value if self.status else None,
            'stop_reason': self.stop_reason,
            'entered_at': self.entered_at.isoformat() if self.entered_at else None,
            'last_action_at': self.last_action_at.isoformat() if self.last_action_at else None,
            'completed_at': self.completed_at.isoformat() if self.completed_at else None,
            'next_action_at': self.next_action_at.isoformat() if self.next_action_at else None,
            'total_emails_sent': self.total_emails_sent,
            'last_email_sent_at': self.last_email_sent_at.isoformat() if self.last_email_sent_at else None
        }


class ContactSegment(Base):
    """Segment de contacts pour ciblage avancé"""
    __tablename__ = 'contact_segments'

    id = Column(Integer, primary_key=True)
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)

    # Critères de filtrage (JSON)
    filters = Column(Text, nullable=False)  # JSON avec les critères
    """
    Exemple de filters JSON:
    {
        "email_validation_score_min": 80,
        "email_validation_score_max": 100,
        "email_deliverable": true,
        "domains_include": ["gmail.com", "yahoo.com"],
        "domains_exclude": ["temp-mail.com"],
        "cities": ["Paris", "Lyon"],
        "has_siret": true,
        "has_phone": false
    }
    """

    # Statistiques
    estimated_count = Column(Integer, default=0)  # Nombre estimé de contacts
    last_count_update = Column(DateTime, nullable=True)

    # Métadonnées
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    is_active = Column(Boolean, default=True)

    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'description': self.description,
            'filters': json.loads(self.filters) if self.filters else {},
            'estimated_count': self.estimated_count,
            'last_count_update': self.last_count_update.isoformat() if self.last_count_update else None,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
            'is_active': self.is_active
        }


class OperationLedger(Base):
    """Journal des opérations (idempotence)"""
    __tablename__ = 'operation_ledger'

    id = Column(Integer, primary_key=True)
    op_id = Column(String(255), unique=True, nullable=False, index=True)  # Clé d'idempotence
    op_type = Column(String(50), nullable=False)  # send_email, schedule_email, update_contact

    # Contexte
    scenario_id = Column(Integer, ForeignKey('scenarios.id'), nullable=True, index=True)
    contact_id = Column(Integer, nullable=True, index=True)
    step_id = Column(Integer, ForeignKey('scenario_steps.id'), nullable=True)
    template_id = Column(Integer, ForeignKey('email_templates.id'), nullable=True)

    # Résultat
    message_id = Column(String(255), nullable=True)  # AWS SES message ID
    campaign_email_id = Column(Integer, ForeignKey('campaign_emails.id'), nullable=True)
    scheduled_at = Column(DateTime, nullable=True)
    executed_at = Column(DateTime, nullable=True, index=True)
    status = Column(String(50), default='pending')  # pending, executed, failed, skipped

    # Détails
    reason = Column(Text, nullable=True)
    extra_data = Column(Text, nullable=True)  # JSON (renamed from metadata to avoid SQLAlchemy conflict)

    # Métadonnées
    created_at = Column(DateTime, default=datetime.utcnow, index=True)

    def to_dict(self):
        return {
            'id': self.id,
            'op_id': self.op_id,
            'op_type': self.op_type,
            'scenario_id': self.scenario_id,
            'contact_id': self.contact_id,
            'step_id': self.step_id,
            'template_id': self.template_id,
            'message_id': self.message_id,
            'campaign_email_id': self.campaign_email_id,
            'scheduled_at': self.scheduled_at.isoformat() if self.scheduled_at else None,
            'executed_at': self.executed_at.isoformat() if self.executed_at else None,
            'status': self.status,
            'reason': self.reason,
            'extra_data': self.extra_data,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }


class Unsubscribe(Base):
    """Liste des désabonnements"""
    __tablename__ = 'unsubscribes'

    id = Column(Integer, primary_key=True)
    email = Column(String(255), nullable=False, unique=True, index=True)
    reason = Column(Text, nullable=True)
    unsubscribed_at = Column(DateTime, default=datetime.utcnow)
    campaign_id = Column(Integer, nullable=True)  # Campagne à l'origine du désabonnement


class EmailBlacklist(Base):
    """Liste noire des emails qui ont bounce (hard ou soft)"""
    __tablename__ = 'email_blacklist'

    id = Column(Integer, primary_key=True)
    email = Column(String(255), nullable=False, unique=True, index=True)
    bounce_type = Column(String(50), nullable=False)  # "hard" ou "soft"
    bounce_reason = Column(Text, nullable=True)  # Raison détaillée du bounce
    first_bounced_at = Column(DateTime, default=datetime.utcnow)
    last_bounced_at = Column(DateTime, default=datetime.utcnow)
    bounce_count = Column(Integer, default=1)  # Nombre de fois que cet email a bounce
    campaign_id = Column(Integer, nullable=True)  # Dernière campagne où l'email a bounce


# Configuration de la base de données
import os
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATABASE_URL = f'sqlite:///{BASE_DIR}/campaigns.db'

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
