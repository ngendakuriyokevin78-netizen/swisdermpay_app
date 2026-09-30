"""URLs Boutique (ajout seul)."""
from django.urls import path
from . import views

app_name = 'shop'

urlpatterns = [
    path('merchants/', views.MerchantListView.as_view(), name='merchant-list'),
    path('products/', views.ProductListView.as_view(), name='product-list'),
    path('packages/', views.PackageListView.as_view(), name='package-list'),
    path('admin/products/', views.ProductRegisterView.as_view(), name='admin-product-register'),
    path('admin/packages/', views.PackageRegisterView.as_view(), name='admin-package-register'),
    path('orders-package/', views.OrderPackageView.as_view(), name='order-package'),
    path('orders/', views.OrderCreateView.as_view(), name='order-create'),
    path('free-pay/', views.FreePayView.as_view(), name='free-pay'),
    path('bonus/grant/', views.BonusGrantView.as_view(), name='bonus-grant'),
    path('admin-stats/', views.AdminShopStatsView.as_view(), name='admin-stats'),
    path('scan-pay/', views.ScanPayView.as_view(), name='scan-pay'),
    path('my-orders/', views.MyOrdersView.as_view(), name='my-orders'),
]
