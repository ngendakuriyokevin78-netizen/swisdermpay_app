"""Vues Interface Téléphone PWA (ajout seul, HTML léger pour mobile)."""
from django.views.generic import TemplateView


class MobileAppView(TemplateView):
    template_name = 'mobile/app.html'


class MerchantQRView(TemplateView):
    """Page vendeur : affiche gros QR à faire scanner."""
    template_name = 'mobile/merchant_qr.html'
