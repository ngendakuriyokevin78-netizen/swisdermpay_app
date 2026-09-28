"""
Serializers DRF pour le module Wallet.
"""
from rest_framework import serializers
from .models import Wallet


class WalletSerializer(serializers.ModelSerializer):
    """Lecture complète du wallet avec URL QR code."""
    owner_name = serializers.SerializerMethodField()
    owner_phone = serializers.SerializerMethodField()
    qr_code_url = serializers.SerializerMethodField()
    qr_data = serializers.SerializerMethodField()

    class Meta:
        model = Wallet
        fields = [
            'wallet_id', 'balance', 'status',
            'owner_name', 'owner_phone',
            'qr_code_url', 'qr_data',
            'created_at', 'updated_at'
        ]
        read_only_fields = fields

    def get_owner_name(self, obj):
        return obj.user.get_full_name()

    def get_owner_phone(self, obj):
        return obj.user.phone_number

    def get_qr_code_url(self, obj):
        request = self.context.get('request')
        if obj.qr_code and request:
            return request.build_absolute_uri(obj.qr_code.url)
        return None

    def get_qr_data(self, obj):
        return obj.qr_data


class WalletSummarySerializer(serializers.ModelSerializer):
    """Version légère pour les listes (transactions, etc.)."""
    owner_name = serializers.SerializerMethodField()

    class Meta:
        model = Wallet
        fields = ['wallet_id', 'balance', 'status', 'owner_name']
        read_only_fields = fields

    def get_owner_name(self, obj):
        return obj.user.get_full_name()
