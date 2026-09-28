"""Serializers circuit EN ATTENTE — AJOUT SEUL."""
from rest_framework import serializers


class PendingCreateSerializer(serializers.Serializer):
    receiver_phone = serializers.CharField(help_text='Destinataire ex: +25762XXXXXX')
    amount = serializers.DecimalField(max_digits=15, decimal_places=2)

    def validate_amount(self, value):
        if value <= 0:
            raise serializers.ValidationError('Le montant doit être positif.')
        return value


class PendingValidateSerializer(serializers.Serializer):
    reference = serializers.CharField()
    pin = serializers.CharField(min_length=4, max_length=4, write_only=True)

    def validate_pin(self, value):
        if not str(value).isdigit():
            raise serializers.ValidationError('Le PIN doit être numérique.')
        return value


class PendingModifySerializer(serializers.Serializer):
    reference = serializers.CharField()
    receiver_phone = serializers.CharField(required=False, allow_blank=True, default='')
    amount = serializers.DecimalField(max_digits=15, decimal_places=2, required=False)

    def validate(self, attrs):
        if not attrs.get('receiver_phone') and attrs.get('amount') is None:
            raise serializers.ValidationError('Fournissez receiver_phone et/ou amount.')
        if attrs.get('amount') is not None and attrs['amount'] <= 0:
            raise serializers.ValidationError('Le montant doit être positif.')
        return attrs


class PendingCancelSerializer(serializers.Serializer):
    reference = serializers.CharField()
    reason = serializers.CharField(required=False, allow_blank=True, default='')
