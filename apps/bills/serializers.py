"""Serializers module Bills."""
from rest_framework import serializers
from .models import Biller, BillPayment


class BillerSerializer(serializers.ModelSerializer):
    class Meta:
        model = Biller
        fields = ['id', 'name', 'code', 'category', 'is_active']
        read_only_fields = fields


class PayBillSerializer(serializers.Serializer):
    biller_code = serializers.CharField(help_text='Ex: REGIDESO, ENDEL, LUMICASH')
    reference_number = serializers.CharField(help_text='N° compteur / facture / téléphone')
    amount = serializers.DecimalField(max_digits=18, decimal_places=3)
    pin = serializers.CharField(min_length=4, max_length=4, write_only=True)

    def validate_amount(self, value):
        if value <= 0:
            raise serializers.ValidationError('Le montant doit être positif.')
        return value
