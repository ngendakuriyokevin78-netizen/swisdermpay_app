"""URLs pour le module Wallet."""
from django.urls import path
from . import views

app_name = 'wallet'

urlpatterns = [
    path('me/', views.WalletDetailView.as_view(), name='wallet-detail'),
    path('qr/', views.WalletQRCodeView.as_view(), name='wallet-qr-image'),
    path('qr-data/', views.WalletQRDataView.as_view(), name='wallet-qr-data'),
    path('qr-amount/', views.WalletQRAmountView.as_view(), name='wallet-qr-amount'),
]
