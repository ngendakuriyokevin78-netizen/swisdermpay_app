"""URLs interop (ajout seul)."""
from django.urls import path
from . import views
from . import ussd_views  # AJOUT tous-téléphones (aucune route existante modifiée)
from . import menu_views  # AJOUT menu *300# modifiable sans code source
from . import provider_config_views  # AJOUT config partenaires sans code source

app_name = 'interop'

urlpatterns = [
    path('providers/', views.ProviderListView.as_view(), name='provider-list'),
    path('send/', views.InteropSendView.as_view(), name='interop-send'),
    path('receive/', views.InteropReceiveView.as_view(), name='interop-receive'),
    path('my-transfers/', views.MyInteropView.as_view(), name='interop-my'),
    path('webhooks/<str:provider_code>/', views.InteropWebhookView.as_view(), name='interop-webhook'),
    path('settlement/', views.SettlementReportView.as_view(), name='settlement'),
    path('settlement/mark/', views.SettlementMarkView.as_view(), name='settlement-mark'),
    # Tous téléphones : USSD + SMS (maquette opérateur)
    path('ussd/', ussd_views.UssdGatewayView.as_view(), name='ussd-gateway'),
    path('sms/', ussd_views.SmsGatewayView.as_view(), name='sms-gateway'),
    # Menu *300# visible et modifiable sans code source (ADMIN en écriture)
    path('ussd-menu/', menu_views.UssdMenuReadView.as_view(), name='ussd-menu-read'),
    path('ussd-menu/update/', menu_views.UssdMenuWriteView.as_view(), name='ussd-menu-write'),
    # Config API entreprises partenaires sans code source (ADMIN)
    path('providers-config/', provider_config_views.ProviderConfigView.as_view(), name='provider-config'),
]
