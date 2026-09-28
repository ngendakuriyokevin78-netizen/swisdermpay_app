"""URLs bancaires (ajout seul)."""
from django.urls import path
from . import views
from . import config_views  # AJOUT config API sans code source

app_name = 'banking'

urlpatterns = [
    path('banks/', views.BankListView.as_view(), name='bank-list'),
    path('deposit/', views.BankDepositView.as_view(), name='bank-deposit'),
    path('withdraw/', views.BankWithdrawView.as_view(), name='bank-withdraw'),
    path('my-transfers/', views.MyBankTransfersView.as_view(), name='bank-my'),
    path('webhooks/<str:bank_code>/', views.BankWebhookView.as_view(), name='bank-webhook'),
    path('float/', views.FloatStatusView.as_view(), name='float-status'),
    path('float/set/', views.FloatSetView.as_view(), name='float-set'),
    # Config API banques visible/modifiable sans code source (ADMIN)
    path('partners-config/', config_views.BankConfigView.as_view(), name='bank-config'),
]
