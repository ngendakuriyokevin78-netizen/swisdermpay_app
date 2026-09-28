"""Admin bancaire (ajout seul)."""
from django.contrib import admin
from .models import BankPartner, BankAccount, BankTransfer, BankFloat


@admin.register(BankPartner)
class BankPartnerAdmin(admin.ModelAdmin):
    list_display = ['code', 'name', 'status', 'is_default', 'api_base_url', 'adapter_class', 'updated_at']
    list_filter = ['status', 'is_default']
    search_fields = ['code', 'name', 'api_base_url']
    fieldsets = (
        ('Identité', {'fields': ('name', 'code', 'swift_code', 'country', 'status', 'is_default')}),
        ('Configuration API — modifiable sans code source', {
            'fields': ('api_base_url', 'api_key', 'api_secret', 'webhook_secret', 'adapter_class'),
            'description': 'Renseignez ici les accès fournis par la banque. Aucune modification du code requise.',
        }),
        ('Limites', {'fields': ('min_transfer', 'max_transfer', 'daily_limit')}),
    )


@admin.register(BankAccount)
class BankAccountAdmin(admin.ModelAdmin):
    list_display = ['bank', 'account_number', 'account_name', 'user']
    search_fields = ['account_number', 'user__phone_number']


@admin.register(BankTransfer)
class BankTransferAdmin(admin.ModelAdmin):
    list_display = ['reference', 'user', 'direction', 'amount', 'status', 'initiated_at']
    list_filter = ['status', 'direction']
    search_fields = ['reference', 'bank_reference', 'user__phone_number']
    readonly_fields = ['reference', 'bank_reference', 'bank_response']


@admin.register(BankFloat)
class BankFloatAdmin(admin.ModelAdmin):
    list_display = ['bank', 'ceiling', 'updated_by', 'updated_at']
    readonly_fields = ['updated_at']
