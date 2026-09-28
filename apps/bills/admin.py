"""Admin module Bills."""
from django.contrib import admin
from .models import Biller, BillPayment


@admin.register(Biller)
class BillerAdmin(admin.ModelAdmin):
    list_display = ['name', 'code', 'category', 'is_active']
    list_filter = ['category', 'is_active']
    search_fields = ['name', 'code']


@admin.register(BillPayment)
class BillPaymentAdmin(admin.ModelAdmin):
    list_display = ['biller', 'user', 'reference_number', 'amount', 'created_at']
    list_filter = ['biller', 'created_at']
    search_fields = ['reference_number', 'user__phone_number']
