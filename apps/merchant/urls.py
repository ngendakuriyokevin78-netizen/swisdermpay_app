"""URLs Marchand (ajout seul)."""
from django.urls import path
from . import views

app_name = 'merchant'

urlpatterns = [
    path('my-qr/', views.MyMerchantQRView.as_view(), name='my-qr'),
]
