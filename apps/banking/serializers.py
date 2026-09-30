"""Serializers bancaires (ajout seul)."""
from rest_framework import serializers
from .models import BankPartner, BankTransfer


class BankPartnerSerializer(serializers.ModelSerializer):
    class Meta:
        model = BankPartner
        fields = ['code', 'name', 'status', 'is_default', 'min_transfer', 'max_transfer']


class BankTransferSerializer(serializers.ModelSerializer):
    bank_code = serializers.CharField(source='bank_account.bank.code', read_only=True)
    account_number = serializers.CharField(source='bank_account.account_number', read_only=True)

    class Meta:
        model = BankTransfer
        fields = ['reference', 'bank_reference', 'bank_code', 'account_number',
                  'direction', 'amount', 'fee', 'status', 'initiated_at', 'completed_at']


class BankDepositSerializer(serializers.Serializer):
    bank_code = serializers.CharField(default='CRDB')
    account_number = serializers.CharField()
    amount = serializers.DecimalField(max_digits=18, decimal_places=3)

    def validate_amount(self, v):
        if v <= 0:
            raise serializers.ValidationError('Montant positif requis.')
        return v


class BankWithdrawSerializer(BankDepositSerializer):
    pin = serializers.CharField(min_length=4, max_length=4, write_only=True)
