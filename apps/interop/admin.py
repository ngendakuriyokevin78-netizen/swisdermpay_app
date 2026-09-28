"""Admin interop (ajout seul)."""
from django.contrib import admin
from .models import ExternalProvider, ExternalTransfer, ReconciliationRecord, UssdConfig, UssdMenuOption


@admin.register(ExternalProvider)
class ExternalProviderAdmin(admin.ModelAdmin):
    list_display = ['code', 'name', 'provider_type', 'status', 'api_base_url', 'fee_percentage']
    list_filter = ['status', 'provider_type']
    search_fields = ['code', 'name', 'api_base_url']
    fieldsets = (
        ('Identité', {'fields': ('name', 'code', 'provider_type', 'country', 'currency', 'status')}),
        ('Configuration API — modifiable sans code source', {
            'fields': ('api_base_url', 'api_key', 'api_secret', 'merchant_id', 'webhook_url', 'webhook_secret', 'adapter_class'),
            'description': "Renseignez ici les accès fournis par l'entreprise partenaire. Aucune modification du code requise.",
        }),
        ('Frais & partage', {'fields': ('fee_percentage', 'fee_fixed', 'fee_split_provider', 'fee_split_platform', 'fee_split_agent')}),
        ('Limites', {'fields': ('min_transfer', 'max_transfer')}),
    )


@admin.register(ExternalTransfer)
class ExternalTransferAdmin(admin.ModelAdmin):
    list_display = ['reference', 'user', 'provider', 'direction', 'amount', 'fee',
                    'provider_share', 'platform_share', 'agent_share', 'settled', 'status']
    list_filter = ['status', 'direction', 'provider', 'settled']
    search_fields = ['reference', 'external_reference', 'user__phone_number']
    readonly_fields = ['reference', 'external_reference', 'provider_response']


@admin.register(ReconciliationRecord)
class ReconciliationAdmin(admin.ModelAdmin):
    list_display = ['provider', 'transfer', 'difference', 'status', 'reconciled_at']
    list_filter = ['status', 'provider']


@admin.register(UssdConfig)
class UssdConfigAdmin(admin.ModelAdmin):
    list_display = ['short_code', 'help_text', 'updated_at']
    search_fields = ['short_code']


@admin.register(UssdMenuOption)
class UssdMenuOptionAdmin(admin.ModelAdmin):
    list_display = ['parent', 'key', 'label', 'enabled', 'order']
    list_filter = ['parent', 'enabled']
    search_fields = ['key', 'label']
    list_editable = ['label', 'enabled', 'order']
