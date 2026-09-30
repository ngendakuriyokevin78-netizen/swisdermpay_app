"""URLs pour le module Transactions."""
from django.urls import path
from . import views
from . import pending_views  # AJOUT : circuit en attente (aucune route existante modifiée)

app_name = 'transactions'

urlpatterns = [
    # Transferts P2P
    path('send/', views.TransferByPhoneView.as_view(), name='transfer-phone'),
    path('qr/', views.TransferByQRView.as_view(), name='transfer-qr'),
    path('reverse/', views.ReverseTransferView.as_view(), name='transfer-reverse'),
    # Frais
    path('fees/', views.FeeGridView.as_view(), name='fee-grid'),
    path('simulate/', views.SimulateFeeView.as_view(), name='fee-simulate'),
    # Historique via /api/transfer/history/
    path('history/', views.TransactionListView.as_view(), name='transaction-history'),
    # Résumé reçus/envoyés jour/semaine (ajout seul)
    path('summary/', views.TransactionSummaryView.as_view(), name='transaction-summary'),
    # ── Circuit EN ATTENTE (ajout seul, multi-lignes PENDING par expéditeur) ──
    path('pending/create/', pending_views.PendingCreateView.as_view(), name='pending-create'),
    path('pending/list/', pending_views.PendingListView.as_view(), name='pending-list'),
    path('pending/validate/', pending_views.PendingValidateView.as_view(), name='pending-validate'),
    path('pending/modify/', pending_views.PendingModifyView.as_view(), name='pending-modify'),
    path('pending/cancel/', pending_views.PendingCancelView.as_view(), name='pending-cancel'),
]

# Alias séparé pour GET /api/transactions/ : voir history_urls.py
# (le include de cashtel/urls.py pointe vers ce module, pas vers ce tuple)
history_urls = ([path('', views.TransactionListView.as_view(), name='transaction-list')], 'transactions_history')
