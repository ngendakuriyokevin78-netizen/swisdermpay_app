"""
Modèles Marchand Cash Tel.
- MerchantProfile : profil d'une entreprise (ex: Swisderm)
- PartnerAgreement : accord de partenariat entre marchands
"""
import uuid
from django.db import models
from django.conf import settings


# ── Profil Marchand ───────────────────────────────────────────────────────────

class MerchantProfile(models.Model):
    """
    Profil d'une entreprise utilisant Cash Tel comme moyen de paiement.
    Ex: Swisderm (cosmétiques), et ses entreprises partenaires.
    """

    class Sector(models.TextChoices):
        COSMETICS = 'COSMETICS', 'Cosmétiques'
        FOOD = 'FOOD', 'Alimentation'
        CLOTHING = 'CLOTHING', 'Habillement'
        ELECTRONICS = 'ELECTRONICS', 'Électronique'
        HEALTH = 'HEALTH', 'Santé'
        SERVICES = 'SERVICES', 'Services'
        OTHER = 'OTHER', 'Autre'

    class Status(models.TextChoices):
        PENDING = 'PENDING', 'En attente de validation'
        ACTIVE = 'ACTIVE', 'Actif'
        SUSPENDED = 'SUSPENDED', 'Suspendu'

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    owner = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name='merchant_profile',
        verbose_name='Propriétaire du compte marchand'
    )

    # ── Identité entreprise ──────────────────────────────────────────────────
    company_name = models.CharField(max_length=200, verbose_name='Nom de l\'entreprise')
    trade_name = models.CharField(
        max_length=200, blank=True,
        verbose_name='Nom commercial',
        help_text='Ex: Swisderm'
    )
    sector = models.CharField(
        max_length=30, choices=Sector.choices,
        default=Sector.OTHER, verbose_name='Secteur d\'activité'
    )
    description = models.TextField(blank=True, verbose_name='Description')
    logo = models.ImageField(
        upload_to='merchant_logos/', blank=True, null=True,
        verbose_name='Logo'
    )
    nif = models.CharField(
        max_length=50, blank=True,
        verbose_name='NIF (Numéro d\'Identification Fiscale)',
        help_text='Numéro fiscal burundais'
    )

    # ── Contact ──────────────────────────────────────────────────────────────
    contact_email = models.EmailField(blank=True, verbose_name='Email de contact')
    contact_phone = models.CharField(max_length=20, blank=True, verbose_name='Téléphone')
    address = models.TextField(blank=True, verbose_name='Adresse physique')

    # ── Compte bancaire par défaut ───────────────────────────────────────────
    bank_name = models.CharField(
        max_length=100, blank=True,
        verbose_name='Banque principale',
        help_text='Ex: CRDB'
    )
    bank_account_number = models.CharField(
        max_length=50, blank=True,
        verbose_name='Numéro de compte bancaire'
    )

    # ── Finances ─────────────────────────────────────────────────────────────
    commission_rate = models.DecimalField(
        max_digits=5, decimal_places=2, default=0,
        verbose_name='Taux de commission (%)',
        help_text='Commission prélevée sur chaque vente via Cash Tel'
    )
    total_revenue = models.DecimalField(
        max_digits=18, decimal_places=3, default=0,
        verbose_name='Chiffre d\'affaires total (BIF)'
    )

    # ── Statut ───────────────────────────────────────────────────────────────
    status = models.CharField(
        max_length=20, choices=Status.choices,
        default=Status.PENDING, verbose_name='Statut'
    )
    is_primary = models.BooleanField(
        default=False,
        verbose_name='Entreprise principale',
        help_text='True pour Swisderm (l\'entreprise mère qui gère Cash Tel)'
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Profil Marchand'
        verbose_name_plural = 'Profils Marchands'
        ordering = ['-is_primary', '-created_at']

    def __str__(self):
        label = self.trade_name or self.company_name
        return f"{label} [{self.get_sector_display()}] — {self.status}"


# ── Accord de Partenariat ─────────────────────────────────────────────────────

class PartnerAgreement(models.Model):
    """
    Accord entre Swisderm et une entreprise partenaire
    pour accepter l'argent électronique Cash Tel.
    """

    class Status(models.TextChoices):
        DRAFT = 'DRAFT', 'Brouillon'
        ACTIVE = 'ACTIVE', 'Actif'
        EXPIRED = 'EXPIRED', 'Expiré'
        TERMINATED = 'TERMINATED', 'Résilié'

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    primary_merchant = models.ForeignKey(
        MerchantProfile, on_delete=models.CASCADE,
        related_name='initiated_partnerships',
        verbose_name='Marchand principal (Swisderm)',
        help_text='L\'entreprise mère qui initie le partenariat'
    )
    partner_merchant = models.ForeignKey(
        MerchantProfile, on_delete=models.CASCADE,
        related_name='received_partnerships',
        verbose_name='Marchand partenaire'
    )

    # ── Termes du partenariat ────────────────────────────────────────────────
    commission_share = models.DecimalField(
        max_digits=5, decimal_places=2, default=0,
        verbose_name='Partage de commission (%)',
        help_text='Pourcentage des frais reversé au partenaire'
    )
    agreement_ref = models.CharField(
        max_length=50, unique=True,
        verbose_name='Référence contrat'
    )

    status = models.CharField(
        max_length=20, choices=Status.choices,
        default=Status.DRAFT, verbose_name='Statut'
    )
    start_date = models.DateField(verbose_name='Date de début')
    end_date = models.DateField(null=True, blank=True, verbose_name='Date de fin')

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Accord de Partenariat'
        verbose_name_plural = 'Accords de Partenariat'
        unique_together = ['primary_merchant', 'partner_merchant']

    def __str__(self):
        return (
            f"{self.primary_merchant.trade_name} ↔ "
            f"{self.partner_merchant.trade_name} — {self.status}"
        )
