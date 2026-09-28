"""Admin Marchands (ajout seul)."""
from django.contrib import admin
from .models import MerchantProfile, PartnerAgreement


@admin.register(MerchantProfile)
class MerchantProfileAdmin(admin.ModelAdmin):
    list_display = ['trade_name', 'company_name', 'sector', 'status', 'is_primary', 'total_revenue']
    list_filter = ['status', 'sector', 'is_primary']
    search_fields = ['trade_name', 'company_name', 'owner__phone_number']


@admin.register(PartnerAgreement)
class PartnerAgreementAdmin(admin.ModelAdmin):
    list_display = ['agreement_ref', 'primary_merchant', 'partner_merchant', 'status']
    list_filter = ['status']
