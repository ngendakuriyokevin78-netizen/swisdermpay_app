"""URLs Boutique (ajout seul)."""
from django.urls import path
from . import views

app_name = 'shop'

urlpatterns = [
    path('merchants/', views.MerchantListView.as_view(), name='merchant-list'),
    path('products/', views.ProductListView.as_view(), name='product-list'),
    path('orders/', views.OrderCreateView.as_view(), name='order-create'),
    path('scan-pay/', views.ScanPayView.as_view(), name='scan-pay'),
    path('my-orders/', views.MyOrdersView.as_view(), name='my-orders'),
]
