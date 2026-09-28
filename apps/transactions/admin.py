"""
Administration Django pour les Transactions et Frais.
Dashboard complet avec filtres, export, et détails.
"""
from django.contrib import admin
from django.utils.html import format_html
from .models import Transaction, Fee


@admin.register(Transaction)
class TransactionAdmin(admin.ModelAdmin):
    """Interface admin pour toutes les transactions."""

    list_display = [
        'reference_short', 'transaction_type', 'status_badge',
        'sender', 'sender_balance', 'receiver', 'receiver_balance',
        'amount_display', 'fee_display', 'created_at'
    ]
    list_filter = ['transaction_type', 'status', 'created_at']
    search_fields = [
        'reference', 'sender__phone_number', 'receiver__phone_number',
        'sender__first_name', 'receiver__first_name'
    ]
    readonly_fields = [
        'reference', 'sender', 'receiver', 'amount', 'fee',
        'transaction_type', 'created_at', 'updated_at', 'metadata'
    ]
    ordering = ['-created_at']
    date_hierarchy = 'created_at'

    fieldsets = (
        ('Référence', {'fields': ('reference', 'transaction_type', 'status')}),
        ('Parties', {'fields': ('sender', 'receiver')}),
        ('Montants', {'fields': ('amount', 'fee')}),
        ('Détails', {'fields': ('description', 'metadata')}),
        ('Dates', {'fields': ('created_at', 'updated_at')}),
    )

    def reference_short(self, obj):
        return str(obj.reference)[:8].upper() + '...'
    reference_short.short_description = 'Référence'

    def status_badge(self, obj):
        colors = {
            'SUCCESS': '#27ae60',
            'PENDING': '#f39c12',
            'FAILED': '#e74c3c',
            'REVERSED': '#95a5a6',
        }
        color = colors.get(obj.status, '#999')
        return format_html(
            '<span style="background:{};color:white;padding:2px 8px;'
            'border-radius:10px;font-size:11px">{}</span>',
            color, obj.get_status_display()
        )
    status_badge.short_description = 'Statut'

    def amount_display(self, obj):
        return f"{obj.amount:,.0f} BIF"
    amount_display.short_description = 'Montant'

    def fee_display(self, obj):
        return f"{obj.fee:,.0f} BIF"
    fee_display.short_description = 'Frais'

    def sender_balance(self, obj):
        try:
            return f"{obj.sender.wallet.balance:,.0f} BIF"
        except Exception:
            return '—'
    sender_balance.short_description = 'Solde expéditeur'

    def receiver_balance(self, obj):
        try:
            return f"{obj.receiver.wallet.balance:,.0f} BIF"
        except Exception:
            return '—'
    receiver_balance.short_description = 'Solde destinataire'

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False


@admin.register(Fee)
class FeeAdmin(admin.ModelAdmin):
    """Gestion de la grille tarifaire."""

    list_display = ['min_amount', 'max_amount', 'fee_value', 'fee_type', 'is_active']
    list_filter = ['fee_type', 'is_active']
    list_editable = ['is_active']
    ordering = ['min_amount']

    fieldsets = (
        ('Tranche', {'fields': ('min_amount', 'max_amount')}),
        ('Frais', {'fields': ('fee_value', 'fee_type')}),
        ('Statut', {'fields': ('is_active',)}),
    )
