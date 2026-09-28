"""URLs Interface Téléphone (ajout seul)."""
from django.urls import path
from . import views

app_name = 'mobile'

urlpatterns = [
    path('', views.MobileAppView.as_view(), name='app'),
    path('vendeur/', views.MerchantQRView.as_view(), name='merchant-qr'),
]
