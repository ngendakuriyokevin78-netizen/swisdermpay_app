"""URLs module Bills."""
from django.urls import path
from . import views

app_name = 'bills'

urlpatterns = [
    path('billers/', views.BillerListView.as_view(), name='biller-list'),
    path('pay/', views.PayBillView.as_view(), name='bill-pay'),
]
