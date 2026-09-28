"""
Modèle Wallet pour Cash Tel.
Chaque utilisateur possède exactement un wallet (OneToOne).
Le QR code est généré automatiquement au format SWISDERMPAY:wallet_id:phone.
"""
import uuid
import qrcode
from io import BytesIO
from django.core.files import File
from django.db import models
from django.conf import settings


class Wallet(models.Model):
    """
    Portefeuille électronique Cash Tel.
    Associé 1-to-1 à un utilisateur.
    Contient le solde en BIF et le QR code de paiement.
    """

    class Status(models.TextChoices):
        ACTIVE = 'ACTIVE', 'Actif'
        FROZEN = 'FROZEN', 'Gelé'
        SUSPENDED = 'SUSPENDED', 'Suspendu'

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='wallet',
        verbose_name='Utilisateur'
    )
    wallet_id = models.UUIDField(
        default=uuid.uuid4, unique=True, editable=False,
        verbose_name='Identifiant Wallet'
    )
    balance = models.DecimalField(
        max_digits=15, decimal_places=2, default=0,
        verbose_name='Solde (BIF)'
    )
    status = models.CharField(
        max_length=20, choices=Status.choices,
        default=Status.ACTIVE, verbose_name='Statut'
    )
    qr_code = models.ImageField(
        upload_to='qr_codes/', blank=True, null=True,
        verbose_name='QR Code'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Portefeuille'
        verbose_name_plural = 'Portefeuilles'
        ordering = ['-created_at']

    def __str__(self):
        return f"Wallet {self.user.phone_number} — {self.balance} BIF [{self.status}]"

    # ── Génération du QR Code ──────────────────────────────────────────────────

    def generate_qr_code(self):
        """
        Génère le QR code au format : SWISDERMPAY:{wallet_id}:{phone_number}
        Sauvegarde l'image PNG dans le champ qr_code.
        """
        qr_data = f"SWISDERMPAY:{self.wallet_id}:{self.user.phone_number}"

        qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.constants.ERROR_CORRECT_M,
            box_size=10,
            border=4,
        )
        qr.add_data(qr_data)
        qr.make(fit=True)

        img = qr.make_image(fill_color='#1a1a2e', back_color='white')

        buffer = BytesIO()
        img.save(buffer, format='PNG')
        buffer.seek(0)

        filename = f"qr_{self.wallet_id}.png"
        self.qr_code.save(filename, File(buffer), save=False)

    # ── Propriétés utilitaires ────────────────────────────────────────────────

    @property
    def is_active(self):
        return self.status == self.Status.ACTIVE

    @property
    def qr_data(self):
        """Retourne les données brutes du QR code."""
        return f"SWISDERMPAY:{self.wallet_id}:{self.user.phone_number}"
