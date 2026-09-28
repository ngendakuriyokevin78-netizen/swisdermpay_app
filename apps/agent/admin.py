"""Admin module Agent."""
from django.contrib import admin
from .models import AgentProfile, WithdrawalRequest


@admin.register(AgentProfile)
class AgentProfileAdmin(admin.ModelAdmin):
    list_display = ['user', 'shop_name', 'commission_balance', 'is_verified', 'created_at']
    list_filter = ['is_verified']
    search_fields = ['user__phone_number', 'shop_name']


@admin.register(WithdrawalRequest)
class WithdrawalRequestAdmin(admin.ModelAdmin):
    list_display = ['code', 'customer', 'amount', 'fee', 'status', 'agent', 'created_at']
    list_filter = ['status']
    search_fields = ['code', 'customer__phone_number']
    readonly_fields = ['code', 'fee', 'transaction', 'created_at']
