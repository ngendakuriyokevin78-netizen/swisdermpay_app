"""
Signaux Django pour l'authentification.
Crée automatiquement un Wallet à chaque nouvel utilisateur.
"""
from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import User


@receiver(post_save, sender=User)
def create_wallet_for_new_user(sender, instance, created, **kwargs):
    """
    À la création d'un utilisateur, génère son wallet et son QR code.
    Utilise get_or_create pour éviter les doublons.
    """
    if created:
        from apps.wallet.models import Wallet
        wallet, _ = Wallet.objects.get_or_create(user=instance)
        # Génère le QR code si pas encore fait
        if not wallet.qr_code:
            wallet.generate_qr_code()
            wallet.save()
