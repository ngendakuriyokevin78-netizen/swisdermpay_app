"""
Modèles du module Transactions Cash Tel.
- Fee : table des frais par tranche de montant
- Transaction : toutes les opérations financières
"""
import uuid
from django.db import models
from django.conf import settings


# ── Table des Frais ───────────────────────────────────────────────────────────

class Fee(models.Model):
    """
    Grille tarifaire des frais de transaction.
    Chaque ligne définit les frais pour une tranche de montant.
    Les frais peuvent être fixes (BIF) ou en pourcentage.
    """

    class FeeType(models.TextChoices):
        FIXED = 'FIXED', 'Fixe (BIF)'
        PERCENTAGE = 'PERCENTAGE', 'Pourcentage (%)'

    min_amount = models.DecimalField(
        max_digits=15, decimal_places=2,
        verbose_name='Montant minimum (BIF)'
    )
    max_amount = models.DecimalField(
        max_digits=15, decimal_places=2,
        verbose_name='Montant maximum (BIF)'
    )
    fee_value = models.DecimalField(
        max_digits=10, decimal_places=2,
        verbose_name='Valeur des frais'
    )
    fee_type = models.CharField(
        max_length=20, choices=FeeType.choices,
        default=FeeType.FIXED, verbose_name='Type de frais'
    )
    is_active = models.BooleanField(default=True, verbose_name='Actif')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Frais'
        verbose_name_plural = 'Grille des Frais'
        ordering = ['min_amount']

    def __str__(self):
        if self.fee_type == self.FeeType.FIXED:
            return f"{self.min_amount:,.0f}–{self.max_amount:,.0f} BIF → {self.fee_value:,.0f} BIF fixe"
        return f"{self.min_amount:,.0f}–{self.max_amount:,.0f} BIF → {self.fee_value}%"


# ── Transaction ───────────────────────────────────────────────────────────────

class Transaction(models.Model):
    """
    Enregistrement de toutes les opérations financières.
    Types : TRANSFER, DEPOSIT, WITHDRAWAL, BILL
    Statuts : PENDING → SUCCESS ou FAILED (ou REVERSED)
    """

    class TransactionType(models.TextChoices):
        TRANSFER = 'TRANSFER', 'Transfert P2P'
        DEPOSIT = 'DEPOSIT', 'Dépôt (Cash In)'
        WITHDRAWAL = 'WITHDRAWAL', 'Retrait (Cash Out)'
        BILL = 'BILL', 'Paiement Facture'

    class Status(models.TextChoices):
        PENDING = 'PENDING', 'En attente'
        SUCCESS = 'SUCCESS', 'Réussi'
        FAILED = 'FAILED', 'Échoué'
        REVERSED = 'REVERSED', 'Annulé/Remboursé'

    # ── Référence unique ──────────────────────────────────────────────────────
    reference = models.UUIDField(
        default=uuid.uuid4, unique=True, editable=False,
        verbose_name='Référence'
    )

    # ── Parties ───────────────────────────────────────────────────────────────
    sender = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL, null=True, blank=True,
        related_name='sent_transactions',
        verbose_name='Expéditeur'
    )
    receiver = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL, null=True, blank=True,
        related_name='received_transactions',
        verbose_name='Destinataire'
    )

    # ── Montants ──────────────────────────────────────────────────────────────
    amount = models.DecimalField(
        max_digits=15, decimal_places=2,
        verbose_name='Montant (BIF)'
    )
    fee = models.DecimalField(
        max_digits=10, decimal_places=2, default=0,
        verbose_name='Frais (BIF)'
    )

    # ── Classification ────────────────────────────────────────────────────────
    transaction_type = models.CharField(
        max_length=20, choices=TransactionType.choices,
        verbose_name='Type'
    )
    status = models.CharField(
        max_length=20, choices=Status.choices,
        default=Status.PENDING, verbose_name='Statut'
    )

    # ── Métadonnées ───────────────────────────────────────────────────────────
    description = models.TextField(blank=True, verbose_name='Description')
    metadata = models.JSONField(
        default=dict, verbose_name='Métadonnées',
        help_text='Données supplémentaires JSON (ex: détails facture, agent, etc.)'
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Transaction'
        verbose_name_plural = 'Transactions'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['sender', '-created_at']),
            models.Index(fields=['receiver', '-created_at']),
            models.Index(fields=['status']),
            models.Index(fields=['transaction_type']),
        ]

    def __str__(self):
        return f"[{self.get_transaction_type_display()}] {self.reference} — {self.amount:,.0f} BIF ({self.status})"

    @property
    def total_amount(self):
        """Montant total débité de l'expéditeur (montant + frais)."""
        return self.amount + self.fee
