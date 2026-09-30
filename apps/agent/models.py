"""
Modèle AgentProfile Cash Tel.
Chaque utilisateur avec rôle AGENT possède un profil agent
avec solde de commissions cumulées.
"""
from django.db import models
from django.conf import settings
from apps.transactions.money import fmt_bif as _b


class AgentProfile(models.Model):
    """Profil agent : commissions + kiosque."""

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name='agent_profile', verbose_name='Agent'
    )
    commission_balance = models.DecimalField(
        max_digits=18, decimal_places=3, default=0,
        verbose_name='Commissions (BIF)'
    )
    shop_name = models.CharField(
        max_length=150, blank=True, verbose_name='Nom boutique'
    )
    is_verified = models.BooleanField(default=False, verbose_name='Agent vérifié')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Profil Agent'
        verbose_name_plural = 'Profils Agents'

    def __str__(self):
        return f"Agent {self.user.phone_number} — {_b(self.commission_balance)}"


class WithdrawalRequest(models.Model):
    """
    Demande de retrait initiée par le CLIENT sur téléphone (AJOUT SEUL).
    Le client obtient un code à 6 chiffres à présenter à l'agent.
    L'agent confirme et remet le cash. Aucune modification du cashout existant.
    """

    class Status(models.TextChoices):
        PENDING = 'PENDING', 'En attente agent'
        COMPLETED = 'COMPLETED', 'Terminé'
        CANCELLED = 'CANCELLED', 'Annulé'
        EXPIRED = 'EXPIRED', 'Expiré'

    customer = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name='withdrawal_requests', verbose_name='Client'
    )
    amount = models.DecimalField(max_digits=18, decimal_places=3, verbose_name='Montant (BIF)')
    fee = models.DecimalField(max_digits=12, decimal_places=3, default=0, verbose_name='Frais (BIF)')
    code = models.CharField(max_length=6, unique=True, verbose_name='Code retrait')
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)
    agent = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='handled_withdrawals', verbose_name='Agent'
    )
    transaction = models.OneToOneField(
        'transactions.Transaction', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='withdrawal_request'
    )
    idempotency_key = models.CharField(max_length=64, blank=True, default='')
    expires_at = models.DateTimeField(verbose_name='Expire le')
    completed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Demande de retrait'
        verbose_name_plural = 'Demandes de retrait'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['code']),
            models.Index(fields=['customer', 'status']),
        ]

    def __str__(self):
        return f"Retrait {_b(self.amount)} {self.customer.phone_number} code {self.code} [{self.status}]"
