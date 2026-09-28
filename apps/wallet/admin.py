"""Administration Django pour les Wallets."""
from django.contrib import admin
from django.utils.html import format_html
from .models import Wallet


@admin.register(Wallet)
class WalletAdmin(admin.ModelAdmin):
    list_display = [
        'user', 'wallet_id_short', 'balance_display',
        'status', 'qr_preview', 'created_at'
    ]
    list_filter = ['status', 'created_at']
    search_fields = ['user__phone_number', 'user__first_name', 'user__last_name', 'wallet_id']
    readonly_fields = ['wallet_id', 'qr_code', 'created_at', 'updated_at']
    ordering = ['-created_at']

    fieldsets = (
        ('Utilisateur', {'fields': ('user', 'wallet_id')}),
        ('Finances', {'fields': ('balance', 'status')}),
        ('QR Code', {'fields': ('qr_code',)}),
        ('Dates', {'fields': ('created_at', 'updated_at')}),
    )

    def wallet_id_short(self, obj):
        return str(obj.wallet_id)[:8] + '...'
    wallet_id_short.short_description = 'Wallet ID'

    def balance_display(self, obj):
        color = 'green' if obj.balance > 0 else 'red'
        return format_html(
            '<span style="color: {}; font-weight: bold;">{} BIF</span>',
            color, f"{obj.balance:,.0f}"
        )
    balance_display.short_description = 'Solde'

    def qr_preview(self, obj):
        if obj.qr_code:
            return format_html(
                '<img src="{}" width="50" height="50" style="border-radius:4px"/>',
                obj.qr_code.url
            )
        return '—'
    qr_preview.short_description = 'QR'

    actions = ['geler_wallets', 'activer_wallets']

    @admin.action(description='Geler les wallets sélectionnés')
    def geler_wallets(self, request, queryset):
        updated = queryset.update(status=Wallet.Status.FROZEN)
        self.message_user(request, f'{updated} wallet(s) gelé(s).')

    @admin.action(description='Activer les wallets sélectionnés')
    def activer_wallets(self, request, queryset):
        updated = queryset.update(status=Wallet.Status.ACTIVE)
        self.message_user(request, f'{updated} wallet(s) activé(s).')
