"""
URLs principales de Cash Tel.
Regroupe toutes les routes API et la documentation Swagger.
"""
from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.views.generic import RedirectView
from rest_framework import permissions
from drf_yasg.views import get_schema_view
from drf_yasg import openapi

# ── Configuration Swagger ──────────────────────────────────────────────────────
schema_view = get_schema_view(
    openapi.Info(
        title="Cash Tel API",
        default_version='v1',
        description=(
            "API Mobile Money pour le Burundi.\n\n"
            "**Devise :** BIF (Franc Burundais)\n"
            "**Auth :** JWT Bearer Token\n\n"
            "Pour obtenir un token : POST /api/auth/login/"
        ),
        contact=openapi.Contact(email="support@cashtel.bi"),
        license=openapi.License(name="Propriétaire"),
    ),
    public=True,
    permission_classes=(permissions.AllowAny,),
)

urlpatterns = [
    # Page d'accueil (le lien "Voir le site" de l'admin pointe ici)
    path('', RedirectView.as_view(url='/m/', permanent=False), name='home'),

    # Administration Django
    path('admin/', admin.site.urls),

    # Documentation API interactive
    path('api/docs/', schema_view.with_ui('swagger', cache_timeout=0), name='schema-swagger-ui'),
    path('api/redoc/', schema_view.with_ui('redoc', cache_timeout=0), name='schema-redoc'),

    # Modules API
    path('api/auth/', include('apps.authentication.urls')),
    path('api/wallet/', include('apps.wallet.urls')),
    path('api/transfer/', include('apps.transactions.urls')),
    path('api/agent/', include('apps.agent.urls')),
    path('api/bills/', include('apps.bills.urls')),
    # Extensions Swisderm (ajout seul — aucune route existante modifiée)
    path('api/shop/', include('apps.shop.urls')),
    path('api/merchant/', include('apps.merchant.urls')),
    path('api/banking/', include('apps.banking.urls')),
    path('api/interop/', include('apps.interop.urls')),
    path('m/', include('apps.mobile.urls')),
    # Alias exigé par le cahier des charges : GET /api/transactions/
    path('api/transactions/', include('apps.transactions.history_urls', namespace='transactions_history')),
]

# Servir les fichiers médias en développement
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
