"""
Modèles Intégration Bancaire Cash Tel.
- BankPartner : banques partenaires (CRDB, etc.)
- BankAccount : comptes bancaires liés aux wallets
- BankTransfer : transferts banque ↔ wallet
"""
import uuid
from django.db import models
from django.conf import settings


# ── Banques Partenaires ───────────────────────────────────────────────────────

class BankPartner(models.Model):
    """
    Banque partenaire de Cash Tel.
    Chaque banque a sa propre API d'intégration.
    """

    class Status(models.TextChoices):
        ACTIVE = 'ACTIVE', 'Actif'
        TESTING = 'TESTING', 'En test'
        INACTIVE = 'INACTIVE', 'Inactif'

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=100, unique=True, verbose_name='Nom de la banque')
    code = models.CharField(
        max_length=20, unique=True,
        verbose_name='Code banque',
        help_text='Ex: CRDB, BCB, BANCOBU, IBB, KCB, ECOBANK'
    )
    swift_code = models.CharField(max_length=20, blank=True, verbose_name='Code SWIFT')
    country = models.CharField(max_length=5, default='BI', verbose_name='Pays')

    # ── Configuration API (PLACEHOLDER) ──────────────────────────────────────
    # ⚠️ Ces champs seront remplis quand l'accord avec la banque sera signé
    api_base_url = models.URLField(
        blank=True,
        verbose_name='URL de base API',
        help_text='⚠️ PLACEHOLDER — À remplir avec l\'URL API fournie par la banque'
    )
    api_key = models.CharField(
        max_length=255, blank=True,
        verbose_name='Clé API',
        help_text='⚠️ PLACEHOLDER — Clé API fournie par la banque (à stocker chiffré en prod)'
    )
    api_secret = models.CharField(
        max_length=255, blank=True,
        verbose_name='Secret API',
        help_text='⚠️ PLACEHOLDER — Secret API fourni par la banque'
    )
    webhook_secret = models.CharField(
        max_length=255, blank=True,
        verbose_name='Secret Webhook',
        help_text='⚠️ PLACEHOLDER — Pour vérifier les notifications de la banque'
    )
    adapter_class = models.CharField(
        max_length=100, default='apps.banking.adapters.mock_adapter.MockBankAdapter',
        verbose_name='Classe adaptateur',
        help_text='Chemin Python de l\'adaptateur API. Ex: apps.banking.adapters.crdb_adapter.CRDBAdapter'
    )

    # ── Limites ──────────────────────────────────────────────────────────────
    min_transfer = models.DecimalField(
        max_digits=15, decimal_places=2, default=1000,
        verbose_name='Transfert minimum (BIF)'
    )
    max_transfer = models.DecimalField(
        max_digits=15, decimal_places=2, default=10000000,
        verbose_name='Transfert maximum (BIF)'
    )
    daily_limit = models.DecimalField(
        max_digits=15, decimal_places=2, default=50000000,
        verbose_name='Limite journalière (BIF)'
    )

    status = models.CharField(
        max_length=20, choices=Status.choices,
        default=Status.TESTING, verbose_name='Statut'
    )
    is_default = models.BooleanField(
        default=False,
        verbose_name='Banque par défaut',
        help_text='True pour CRDB (banque principale de Swisderm)'
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Banque Partenaire'
        verbose_name_plural = 'Banques Partenaires'
        ordering = ['-is_default', 'name']

    def __str__(self):
        default_tag = ' ★' if self.is_default else ''
        return f"{self.name} ({self.code}){default_tag} [{self.status}]"


# ── Comptes Bancaires Liés ────────────────────────────────────────────────────

class BankAccount(models.Model):
    """
    Compte bancaire lié à un utilisateur ou un marchand Cash Tel.
    Permet les transferts banque ↔ wallet.
    """

    class AccountType(models.TextChoices):
        PERSONAL = 'PERSONAL', 'Personnel'
        BUSINESS = 'BUSINESS', 'Entreprise'

    class VerificationStatus(models.TextChoices):
        PENDING = 'PENDING', 'En attente de vérification'
        VERIFIED = 'VERIFIED', 'Vérifié'
        REJECTED = 'REJECTED', 'Rejeté'

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name='bank_accounts',
        verbose_name='Titulaire'
    )
    bank = models.ForeignKey(
        BankPartner, on_delete=models.PROTECT,
        related_name='accounts',
        verbose_name='Banque'
    )

    account_number = models.CharField(max_length=50, verbose_name='Numéro de compte')
    account_name = models.CharField(max_length=200, verbose_name='Nom du titulaire')
    account_type = models.CharField(
        max_length=20, choices=AccountType.choices,
        default=AccountType.PERSONAL, verbose_name='Type de compte'
    )

    verification_status = models.CharField(
        max_length=20, choices=VerificationStatus.choices,
        default=VerificationStatus.PENDING, verbose_name='Statut vérification'
    )
    is_primary = models.BooleanField(default=False, verbose_name='Compte principal')

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Compte Bancaire'
        verbose_name_plural = 'Comptes Bancaires'
        unique_together = ['bank', 'account_number']

    def __str__(self):
        return f"{self.bank.code} {self.account_number} — {self.account_name}"


# ── Transferts Bancaires ──────────────────────────────────────────────────────

class BankTransfer(models.Model):
    """
    Transfert entre un compte bancaire et un wallet Cash Tel.
    DEPOSIT  : Banque → Wallet (ex: CRDB → wallet client Swisderm)
    WITHDRAW : Wallet → Banque (ex: retrait vers compte CRDB)
    """

    class Direction(models.TextChoices):
        DEPOSIT = 'DEPOSIT', 'Banque → Wallet (Dépôt)'
        WITHDRAW = 'WITHDRAW', 'Wallet → Banque (Retrait)'

    class Status(models.TextChoices):
        INITIATED = 'INITIATED', 'Initié'
        PENDING_BANK = 'PENDING_BANK', 'En attente banque'
        PROCESSING = 'PROCESSING', 'En cours de traitement'
        COMPLETED = 'COMPLETED', 'Complété'
        FAILED = 'FAILED', 'Échoué'
        CANCELLED = 'CANCELLED', 'Annulé'

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    reference = models.CharField(
        max_length=50, unique=True,
        verbose_name='Référence Cash Tel'
    )
    bank_reference = models.CharField(
        max_length=100, blank=True,
        verbose_name='Référence banque',
        help_text='Référence retournée par l\'API de la banque'
    )

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name='bank_transfers',
        verbose_name='Utilisateur'
    )
    bank_account = models.ForeignKey(
        BankAccount, on_delete=models.PROTECT,
        related_name='transfers',
        verbose_name='Compte bancaire'
    )

    direction = models.CharField(
        max_length=20, choices=Direction.choices,
        verbose_name='Direction'
    )
    amount = models.DecimalField(
        max_digits=15, decimal_places=2,
        verbose_name='Montant (BIF)'
    )
    fee = models.DecimalField(
        max_digits=10, decimal_places=2, default=0,
        verbose_name='Frais (BIF)'
    )
    status = models.CharField(
        max_length=20, choices=Status.choices,
        default=Status.INITIATED, verbose_name='Statut'
    )

    # ── Réponse API banque ───────────────────────────────────────────────────
    bank_response = models.JSONField(
        default=dict, blank=True,
        verbose_name='Réponse API banque',
        help_text='Réponse complète de l\'API bancaire pour traçabilité'
    )
    error_message = models.TextField(blank=True, verbose_name='Message d\'erreur')

    initiated_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Transfert Bancaire'
        verbose_name_plural = 'Transferts Bancaires'
        ordering = ['-initiated_at']
        indexes = [
            models.Index(fields=['user', '-initiated_at']),
            models.Index(fields=['status']),
        ]

    def __str__(self):
        direction_arrow = 'BNK->WAL' if self.direction == self.Direction.DEPOSIT else 'WAL->BNK'
        return f"{direction_arrow} {self.amount:,.0f} BIF — {self.status} — {self.reference}"


class BankFloat(models.Model):
    """
    Plafond cantonné déclaré par banque (AJOUT SEUL — garde-fou émission).
    Total e-money (somme Wallet.balance) ne doit jamais dépasser
    la somme des plafonds. Ex : Swisderm déclare 1 000 000 chez CRDB.
    """

    bank = models.OneToOneField(
        BankPartner, on_delete=models.CASCADE,
        related_name='float_ceiling', verbose_name='Banque'
    )
    ceiling = models.DecimalField(
        max_digits=18, decimal_places=2, default=0,
        verbose_name='Plafond cantonné (BIF)')
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, verbose_name='Déclaré par')
    notes = models.CharField(max_length=255, blank=True, default='')
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Plafond cantonné'
        verbose_name_plural = 'Plafonds cantonnés'

    def __str__(self):
        return f"{self.bank.code} plafond {self.ceiling:,.0f} BIF"
