"""
Serializers DRF pour le module Transactions.
"""
from rest_framework import serializers
from .models import Transaction, Fee


class TransactionSerializer(serializers.ModelSerializer):
    """Sérialise une transaction pour l'historique utilisateur."""
    sender_name = serializers.SerializerMethodField()
    sender_phone = serializers.SerializerMethodField()
    receiver_name = serializers.SerializerMethodField()
    receiver_phone = serializers.SerializerMethodField()
    type_display = serializers.CharField(source='get_transaction_type_display', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    sender_balance = serializers.SerializerMethodField()
    receiver_balance = serializers.SerializerMethodField()

    class Meta:
        model = Transaction
        fields = [
            'reference', 'transaction_type', 'type_display',
            'status', 'status_display',
            'amount', 'fee', 'total_amount',
            'sender_name', 'sender_phone', 'sender_balance',
            'receiver_name', 'receiver_phone', 'receiver_balance',
            'description', 'metadata',
            'created_at',
        ]
        read_only_fields = fields

    def _balance(self, user):
        try:
            return str(user.wallet.balance)
        except Exception:
            return None

    def get_sender_name(self, obj):
        return obj.sender.get_full_name() if obj.sender else 'Cash Tel'

    def get_sender_phone(self, obj):
        return obj.sender.phone_number if obj.sender else None

    def get_receiver_name(self, obj):
        return obj.receiver.get_full_name() if obj.receiver else 'Cash Tel'

    def get_receiver_phone(self, obj):
        return obj.receiver.phone_number if obj.receiver else None

    def get_sender_balance(self, obj):
        return self._balance(obj.sender) if obj.sender else None

    def get_receiver_balance(self, obj):
        return self._balance(obj.receiver) if obj.receiver else None


class TransferByPhoneSerializer(serializers.Serializer):
    """Entrée pour un transfert P2P par numéro de téléphone."""
    receiver_phone = serializers.CharField(
        help_text='Numéro du destinataire (ex: +25762XXXXXXX)'
    )
    amount = serializers.DecimalField(
        max_digits=15, decimal_places=2,
        help_text='Montant en BIF (minimum 100 BIF)'
    )
    pin = serializers.CharField(
        min_length=4, max_length=4, write_only=True,
        help_text='Votre PIN à 4 chiffres'
    )

    def validate_amount(self, value):
        if value <= 0:
            raise serializers.ValidationError('Le montant doit être positif.')
        return value

    def validate_pin(self, value):
        if not str(value).isdigit():
            raise serializers.ValidationError('Le PIN doit être numérique.')
        return value


class TransferByQRSerializer(serializers.Serializer):
    """Entrée pour un transfert par scan de QR Code."""
    qr_data = serializers.CharField(
        help_text='Données du QR Code scanné (SWISDERMPAY:wallet_id:phone[:montant])'
    )
    amount = serializers.DecimalField(
        max_digits=15, decimal_places=2, required=False,
        help_text='Montant BIF (inutile si intégré au QR)'
    )
    pin = serializers.CharField(
        min_length=4, max_length=4, write_only=True,
        help_text='Votre PIN à 4 chiffres'
    )

    def validate_qr_data(self, value):
        if not (value.startswith('SWISDERMPAY:') or value.startswith('CASHTEL:')):
            raise serializers.ValidationError(
                'QR Code invalide. Format : SWISDERMPAY:{wallet_id}:{phone}'
            )
        return value

    def validate_amount(self, value):
        if value <= 0:
            raise serializers.ValidationError('Le montant doit être positif.')
        return value


class FeeSerializer(serializers.ModelSerializer):
    """Sérialise la grille des frais."""
    class Meta:
        model = Fee
        fields = ['id', 'min_amount', 'max_amount', 'fee_value', 'fee_type', 'is_active']
        read_only_fields = fields
