"""Alias GET /api/transactions/ — historique seul (namespace séparé)."""
from django.urls import path
from .views import TransactionListView, AdminAllTransactionsView

app_name = 'transactions_history'

urlpatterns = [
    path('', TransactionListView.as_view(), name='transaction-list'),
    path('all/', AdminAllTransactionsView.as_view(), name='transaction-all'),
]
