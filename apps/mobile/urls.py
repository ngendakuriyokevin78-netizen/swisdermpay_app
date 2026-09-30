"""URLs Interface Téléphone (ajout seul)."""
from django.urls import path
from . import views

app_name = 'mobile'

urlpatterns = [
    path('manifest.webmanifest', views.ManifestView.as_view(), name='manifest'),
    path('sw.js', views.ServiceWorkerView.as_view(), name='sw'),
    path('icons/icon-<int:size>.png', views.AppIconView.as_view(), name='icon'),
    path('', views.MobileAppView.as_view(), name='app'),
    path('vendeur/', views.MerchantQRView.as_view(), name='merchant-qr'),
]
