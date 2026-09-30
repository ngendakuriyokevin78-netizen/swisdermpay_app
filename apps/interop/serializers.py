"""Serializers interop (ajout seul)."""
from rest_framework import serializers
from .models import ExternalProvider, ExternalTransfer


class ProviderSerializer(serializers.ModelSerializer):
    class Meta:
        model = ExternalProvider
        fields = ['code', 'name', 'provider_type', 'status',
                  'min_transfer', 'max_transfer', 'fee_percentage', 'fee_fixed',
                  'fee_split_provider', 'fee_split_platform', 'fee_split_agent']


class ExternalTransferSerializer(serializers.ModelSerializer):
    provider_code = serializers.CharField(source='provider.code', read_only=True)

    class Meta:
        model = ExternalTransfer
        fields = ['reference', 'external_reference', 'provider_code', 'external_phone',
                  'direction', 'amount', 'fee', 'provider_share', 'platform_share',
                  'agent_share', 'settled', 'status', 'initiated_at', 'completed_at']


class InteropSendSerializer(serializers.Serializer):
    provider_code = serializers.CharField()
    external_phone = serializers.CharField()
    amount = serializers.DecimalField(max_digits=18, decimal_places=3)
    pin = serializers.CharField(min_length=4, max_length=4, write_only=True)
    agent_phone = serializers.CharField(required=False, allow_blank=True, default='',
                                        help_text="Agent facilitateur (optionnel) qui reçoit la part agents")


class InteropReceiveSerializer(serializers.Serializer):
    provider_code = serializers.CharField()
    external_phone = serializers.CharField()
    amount = serializers.DecimalField(max_digits=18, decimal_places=3)
