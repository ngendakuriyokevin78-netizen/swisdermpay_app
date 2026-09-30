"""
Modèles Interopérabilité Cash Tel.
- ExternalProvider : opérateurs Mobile Money (LumiCash, eNoti/Bancobu, eHela)
- ExternalTransfer : transferts entre Cash Tel et opérateurs externes
- ReconciliationRecord : rapprochement des flux inter-opérateurs
"""
import uuid
from django.db import models
from django.conf import settings
from apps.transactions.money import fmt_bif as _b


# ── Opérateurs Externes ───────────────────────────────────────────────────────

class ExternalProvider(models.Model):
    """
    Opérateur Mobile Money partenaire.
    Ex: LumiCash (Econet Leo), eNoti (Bancobu), eHela (IMTO).
    """

    class Status(models.TextChoices):
        ACTIVE = 'ACTIVE', 'Actif'
        TESTING = 'TESTING', 'En test'
        INACTIVE = 'INACTIVE', 'Inactif'

    class ProviderType(models.TextChoices):
        MOBILE_MONEY = 'MOBILE_MONEY', 'Mobile Money'
        BANK = 'BANK', 'Banque'
        FINTECH = 'FINTECH', 'Fintech'

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=100, unique=True, verbose_name='Nom')
    code = models.CharField(
        max_length=20, unique=True,
        verbose_name='Code opérateur',
        help_text='Ex: LUMICASH, ENOTI, EHELA'
    )
    provider_type = models.CharField(
        max_length=20, choices=ProviderType.choices,
        default=ProviderType.MOBILE_MONEY, verbose_name='Type'
    )
    country = models.CharField(max_length=5, default='BI', verbose_name='Pays')
    currency = models.CharField(max_length=5, default='BIF', verbose_name='Devise')

    # ── Configuration API (PLACEHOLDER) ──────────────────────────────────────
    # ⚠️ Ces champs seront remplis quand l'accord avec l'opérateur sera signé
    api_base_url = models.URLField(
        blank=True,
        verbose_name='URL de base API',
        help_text='⚠️ PLACEHOLDER — À remplir avec l\'URL API fournie par l\'opérateur'
    )
    api_key = models.CharField(
        max_length=255, blank=True,
        verbose_name='Clé API',
        help_text='⚠️ PLACEHOLDER — Clé API fournie par l\'opérateur'
    )
    api_secret = models.CharField(
        max_length=255, blank=True,
        verbose_name='Secret API',
        help_text='⚠️ PLACEHOLDER — Secret API fourni par l\'opérateur'
    )
    merchant_id = models.CharField(
        max_length=100, blank=True,
        verbose_name='Merchant ID',
        help_text='⚠️ PLACEHOLDER — Identifiant marchand chez l\'opérateur'
    )
    webhook_url = models.URLField(
        blank=True,
        verbose_name='URL Webhook',
        help_text='URL que l\'opérateur appellera pour les notifications'
    )
    webhook_secret = models.CharField(
        max_length=255, blank=True,
        verbose_name='Secret Webhook',
        help_text='⚠️ PLACEHOLDER — Pour vérifier l\'authenticité des callbacks'
    )
    adapter_class = models.CharField(
        max_length=100, default='apps.interop.adapters.mock_adapter.MockProviderAdapter',
        verbose_name='Classe adaptateur',
        help_text=(
            'Chemin Python de l\'adaptateur API. Ex:\n'
            '- apps.interop.adapters.lumicash_adapter.LumiCashAdapter\n'
            '- apps.interop.adapters.enoti_adapter.EnotiAdapter\n'
            '- apps.interop.adapters.ehela_adapter.EhelaAdapter'
        )
    )

    # ── Limites & Frais ──────────────────────────────────────────────────────
    min_transfer = models.DecimalField(
        max_digits=18, decimal_places=3, default=500,
        verbose_name='Transfert minimum (BIF)'
    )
    max_transfer = models.DecimalField(
        max_digits=18, decimal_places=3, default=5000000,
        verbose_name='Transfert maximum (BIF)'
    )
    fee_percentage = models.DecimalField(
        max_digits=5, decimal_places=2, default=1,
        verbose_name='Frais (%)',
        help_text='Pourcentage de frais pour les transferts inter-opérateurs'
    )
    fee_fixed = models.DecimalField(
        max_digits=12, decimal_places=3, default=0,
        verbose_name='Frais fixes (BIF)'
    )

    # ── Partage des frais (% du fee, total 100) — AJOUT SEUL ───────────────
    fee_split_provider = models.DecimalField(
        max_digits=5, decimal_places=2, default=50,
        verbose_name='Part opérateur (%)',
        help_text='Part des frais reversée à LumiCash/eNoti/eHela')
    fee_split_platform = models.DecimalField(
        max_digits=5, decimal_places=2, default=35,
        verbose_name='Part Swisderm/CashTel (%)')
    fee_split_agent = models.DecimalField(
        max_digits=5, decimal_places=2, default=15,
        verbose_name='Part agents (%)',
        help_text='Pool agents, distribué manuellement')

    status = models.CharField(
        max_length=20, choices=Status.choices,
        default=Status.TESTING, verbose_name='Statut'
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Opérateur Externe'
        verbose_name_plural = 'Opérateurs Externes'
        ordering = ['name']

    def __str__(self):
        return f"{self.name} ({self.code}) [{self.status}]"


# ── Transferts Externes ───────────────────────────────────────────────────────

class ExternalTransfer(models.Model):
    """
    Transfert entre un wallet Cash Tel et un compte chez un opérateur externe.
    SEND    : Cash Tel → LumiCash/eNoti/eHela
    RECEIVE : LumiCash/eNoti/eHela → Cash Tel
    """

    class Direction(models.TextChoices):
        SEND = 'SEND', 'Cash Tel → Opérateur (Envoi)'
        RECEIVE = 'RECEIVE', 'Opérateur → Cash Tel (Réception)'

    class Status(models.TextChoices):
        INITIATED = 'INITIATED', 'Initié'
        PENDING_EXTERNAL = 'PENDING_EXTERNAL', 'En attente opérateur'
        PROCESSING = 'PROCESSING', 'En cours'
        COMPLETED = 'COMPLETED', 'Complété'
        FAILED = 'FAILED', 'Échoué'
        REFUNDED = 'REFUNDED', 'Remboursé'

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    reference = models.CharField(
        max_length=50, unique=True,
        verbose_name='Référence Cash Tel'
    )
    external_reference = models.CharField(
        max_length=100, blank=True,
        verbose_name='Référence opérateur',
        help_text='Référence retournée par l\'API de l\'opérateur'
    )

    # ── Parties ──────────────────────────────────────────────────────────────
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name='external_transfers',
        verbose_name='Utilisateur Cash Tel'
    )
    provider = models.ForeignKey(
        ExternalProvider, on_delete=models.PROTECT,
        related_name='transfers',
        verbose_name='Opérateur'
    )
    external_phone = models.CharField(
        max_length=20,
        verbose_name='Numéro externe',
        help_text='Numéro du compte chez l\'opérateur (ex: +25762...)'
    )

    # ── Montants ─────────────────────────────────────────────────────────────
    direction = models.CharField(
        max_length=20, choices=Direction.choices,
        verbose_name='Direction'
    )
    amount = models.DecimalField(
        max_digits=18, decimal_places=3,
        verbose_name='Montant (BIF)'
    )
    fee = models.DecimalField(
        max_digits=12, decimal_places=3, default=0,
        verbose_name='Frais (BIF)'
    )
    # ── Split du fee (montants, somme = fee) — AJOUT SEUL ──────────────────
    provider_share = models.DecimalField(
        max_digits=12, decimal_places=3, default=0,
        verbose_name='Part opérateur (BIF)')
    platform_share = models.DecimalField(
        max_digits=12, decimal_places=3, default=0,
        verbose_name='Part Swisderm/CashTel (BIF)')
    agent_share = models.DecimalField(
        max_digits=12, decimal_places=3, default=0,
        verbose_name='Part pool agents (BIF)')
    settled = models.BooleanField(
        default=False, verbose_name='Reversé (settlement)')
    # Agent ayant facilité l'envoi (optionnel) — AJOUT SEUL
    agent = models.ForeignKey(
        'authentication.User', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='facilitated_transfers',
        verbose_name='Agent facilitateur')
    status = models.CharField(
        max_length=20, choices=Status.choices,
        default=Status.INITIATED, verbose_name='Statut'
    )

    # ── Réponse API opérateur ────────────────────────────────────────────────
    provider_response = models.JSONField(
        default=dict, blank=True,
        verbose_name='Réponse API opérateur',
        help_text='Réponse complète de l\'API pour traçabilité'
    )
    error_message = models.TextField(blank=True, verbose_name='Message d\'erreur')

    initiated_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Transfert Externe'
        verbose_name_plural = 'Transferts Externes'
        ordering = ['-initiated_at']
        indexes = [
            models.Index(fields=['user', '-initiated_at']),
            models.Index(fields=['provider', 'status']),
            models.Index(fields=['external_reference']),
        ]

    def __str__(self):
        arrow = '->' if self.direction == self.Direction.SEND else '<-'
        return (
            f"Cash Tel {arrow} {self.provider.code} | "
            f"{_b(self.amount)} — {self.status}"
        )


# ── Rapprochement / Réconciliation ───────────────────────────────────────────

class ReconciliationRecord(models.Model):
    """
    Journal de rapprochement entre Cash Tel et les opérateurs externes.
    Permet de détecter les écarts entre les flux internes et externes.
    """

    class Status(models.TextChoices):
        MATCHED = 'MATCHED', 'Concordant'
        MISMATCH = 'MISMATCH', 'Écart détecté'
        PENDING = 'PENDING', 'En attente'
        RESOLVED = 'RESOLVED', 'Résolu'

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    provider = models.ForeignKey(
        ExternalProvider, on_delete=models.PROTECT,
        related_name='reconciliations',
        verbose_name='Opérateur'
    )
    transfer = models.ForeignKey(
        ExternalTransfer, on_delete=models.CASCADE,
        related_name='reconciliations',
        verbose_name='Transfert',
        null=True, blank=True
    )

    internal_amount = models.DecimalField(
        max_digits=18, decimal_places=3,
        verbose_name='Montant interne (Cash Tel)'
    )
    external_amount = models.DecimalField(
        max_digits=18, decimal_places=3,
        verbose_name='Montant externe (opérateur)'
    )
    difference = models.DecimalField(
        max_digits=18, decimal_places=3, default=0,
        verbose_name='Écart (BIF)'
    )

    status = models.CharField(
        max_length=20, choices=Status.choices,
        default=Status.PENDING, verbose_name='Statut'
    )
    notes = models.TextField(blank=True, verbose_name='Notes')

    reconciled_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Rapprochement'
        verbose_name_plural = 'Rapprochements'
        ordering = ['-reconciled_at']

    def __str__(self):
        return f"{self.provider.code} — {self.status} — Écart: {_b(self.difference)}"


# ── Code USSD + menus *300# configurables par l'ADMIN (AJOUT SEUL) ──────────

class UssdConfig(models.Model):
    """Code court opérateur (ex *300#). Modifiable sans toucher au code."""

    short_code = models.CharField(
        max_length=20, default='*300#',
        verbose_name='Code USSD',
        help_text='Ex : *300#. Doit correspondre au code attribué par Lumitel.'
    )
    help_text = models.CharField(
        max_length=255, default='Cash Tel : 1 Envoyer, 2 Attente, 3 Valider.',
        verbose_name="Texte d'aide"
    )
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Code USSD'
        verbose_name_plural = 'Code USSD'

    def __str__(self):
        return f"USSD {self.short_code}"

    @classmethod
    def current_code(cls) -> str:
        try:
            obj = cls.objects.order_by('-updated_at').first()
            return obj.short_code if obj else '*300#'
        except Exception:
            return '*300#'


class UssdMenuOption(models.Model):
    """Option du menu *300#. La clé pilote le routage (ne pas renommer sans dev)."""

    key = models.CharField(
        max_length=10, unique=True,
        verbose_name='Touche',
        help_text="Ex : 1, 2, 3, 4, 5, 6, 7, 8, 9, 0. La touche pilote le routage."
    )
    parent = models.CharField(
        max_length=10, default='root',
        verbose_name='Menu parent',
        help_text='root, plus ou compte'
    )
    label = models.CharField(max_length=60, verbose_name='Libellé affiché')
    enabled = models.BooleanField(default=True, verbose_name='Activée')
    order = models.PositiveSmallIntegerField(default=0, verbose_name='Ordre')

    class Meta:
        verbose_name = 'Option menu USSD'
        verbose_name_plural = 'Options menu USSD'
        ordering = ['parent', 'order', 'key']

    def __str__(self):
        state = 'ON' if self.enabled else 'OFF'
        return f"[{self.parent}] {self.key}. {self.label} ({state})"

    @classmethod
    def labels(cls, parent: str, defaults: dict) -> dict:
        """Libellés actifs pour un menu, sinon valeurs par défaut (sans casser)."""
        try:
            rows = list(cls.objects.filter(parent=parent, enabled=True).order_by('order', 'key'))
            if not rows:
                return dict(defaults)
            return {r.key: r.label for r in rows}
        except Exception:
            return dict(defaults)
