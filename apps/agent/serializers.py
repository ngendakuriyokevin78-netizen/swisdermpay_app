"""Serializers module Agent."""
from rest_framework import serializers


class CashInSerializer(serializers.Serializer):
    customer_phone = serializers.CharField()
    amount = serializers.DecimalField(max_digits=18, decimal_places=3)

    def validate_amount(self, value):
        if value <= 0:
            raise serializers.ValidationError('Le montant doit être positif.')
        return value


class CashOutSerializer(serializers.Serializer):
    customer_phone = serializers.CharField()
    amount = serializers.DecimalField(max_digits=18, decimal_places=3)
    pin = serializers.CharField(min_length=4, max_length=4, write_only=True)

    def validate_amount(self, value):
        if value <= 0:
            raise serializers.ValidationError('Le montant doit être positif.')
        return value


class WithdrawRequestSerializer(serializers.Serializer):
    """Demande client : montant + PIN (AJOUT SEUL)."""
    amount = serializers.DecimalField(max_digits=18, decimal_places=3)
    pin = serializers.CharField(min_length=4, max_length=4, write_only=True)
    idempotency_key = serializers.CharField(required=False, allow_blank=True, default='')

    def validate_amount(self, value):
        if value <= 0:
            raise serializers.ValidationError('Le montant doit être positif.')
        return value


class WithdrawConfirmSerializer(serializers.Serializer):
    """Confirmation agent : code à 6 chiffres (AJOUT SEUL)."""
    code = serializers.CharField(min_length=6, max_length=6)
