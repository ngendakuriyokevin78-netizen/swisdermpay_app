"""URLs module Agent."""
from django.urls import path
from . import views

app_name = 'agent'

urlpatterns = [
    path('cashin/', views.CashInView.as_view(), name='cashin'),
    path('cashout/', views.CashOutView.as_view(), name='cashout'),
    # Retrait initié client (ajout seul)
    path('withdraw-request/', views.WithdrawRequestView.as_view(), name='withdraw-request'),
    path('withdraw-confirm/', views.WithdrawConfirmView.as_view(), name='withdraw-confirm'),
    path('withdraw-cancel/', views.WithdrawCancelView.as_view(), name='withdraw-cancel'),
    # Commission agent visible (ajout seul)
    path('commission/', views.CommissionView.as_view(), name='commission'),
    path('commission/claim/', views.CommissionClaimView.as_view(), name='commission-claim'),
]
