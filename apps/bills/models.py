"""
Modèles Bills : fournisseurs génériques + paiements.
Ex : REGIDESO (eau), ENDEL / REGIDESO élec, Lumicash, Econet.
"""
from django.db import models
from django.conf import settings
from apps.transactions.money import fmt_bif as _b


class Biller(models.Model):
    """Fournisseur de service facturable."""

    class Category(models.TextChoices):
        WATER = 'WATER', 'Eau'
        ELECTRICITY = 'ELECTRICITY', 'Électricité'
        AIRTIME = 'AIRTIME', 'Crédit téléphone'
        OTHER = 'OTHER', 'Autre'

    name = models.CharField(max_length=100, unique=True, verbose_name='Nom')
    code = models.CharField(max_length=30, unique=True, verbose_name='Code')
    category = models.CharField(max_length=20, choices=Category.choices, verbose_name='Catégorie')
    is_active = models.BooleanField(default=True, verbose_name='Actif')

    class Meta:
        verbose_name = 'Fournisseur'
        verbose_name_plural = 'Fournisseurs'

    def __str__(self):
        return f"{self.name} [{self.get_category_display()}]"


class BillPayment(models.Model):
    """Paiement de facture effectué par un utilisateur."""

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name='bill_payments', verbose_name='Payeur'
    )
    biller = models.ForeignKey(Biller, on_delete=models.PROTECT, verbose_name='Fournisseur')
    reference_number = models.CharField(max_length=100, verbose_name='Référence facture')
    amount = models.DecimalField(max_digits=18, decimal_places=3, verbose_name='Montant (BIF)')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Paiement facture'
        verbose_name_plural = 'Paiements factures'
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.biller.name} {_b(self.amount)} — {self.reference_number}"
