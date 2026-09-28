"""
Serializers DRF pour l'authentification Cash Tel.
"""
from rest_framework import serializers
from django.contrib.auth import get_user_model
from django.utils.crypto import get_random_string
from .models import AuditLog

User = get_user_model()


# ── Inscription ────────────────────────────────────────────────────────────────

class RegisterSerializer(serializers.ModelSerializer):
    """Sérialise la création d'un compte utilisateur."""
    pin = serializers.CharField(
        write_only=True, min_length=4, max_length=4,
        help_text='PIN à 4 chiffres'
    )
    password = serializers.CharField(write_only=True, required=False)

    class Meta:
        model = User
        fields = ['phone_number', 'first_name', 'last_name', 'pin', 'password']

    def validate_phone_number(self, value):
        """Validation basique du format téléphone burundais."""
        cleaned = value.replace(' ', '').replace('-', '')
        if not cleaned.startswith('+'):
            cleaned = '+257' + cleaned.lstrip('0')
        if len(cleaned) < 10:
            raise serializers.ValidationError(
                'Numéro de téléphone invalide. Format: +25762XXXXXXX'
            )
        return cleaned

    def validate_pin(self, value):
        """Vérifie que le PIN est bien numérique à 4 chiffres."""
        if not str(value).isdigit():
            raise serializers.ValidationError('Le PIN doit être composé uniquement de chiffres.')
        return value

    def create(self, validated_data):
        pin = validated_data.pop('pin')
        password = validated_data.pop('password', None)

        user = User(**validated_data)
        user.set_password(password or get_random_string(10))
        user.set_pin(pin)
        user.save()
        return user


# ── Vérification OTP ──────────────────────────────────────────────────────────

class VerifyOTPSerializer(serializers.Serializer):
    """Sérialise la vérification du code OTP."""
    phone_number = serializers.CharField()
    otp = serializers.CharField(min_length=6, max_length=6)

    def validate_otp(self, value):
        if not value.isdigit():
            raise serializers.ValidationError('L\'OTP doit être numérique.')
        return value


# ── Login ─────────────────────────────────────────────────────────────────────

class LoginSerializer(serializers.Serializer):
    """Sérialise la connexion par numéro + PIN."""
    phone_number = serializers.CharField()
    pin = serializers.CharField(
        min_length=4, max_length=4, write_only=True
    )


# ── Profil utilisateur ────────────────────────────────────────────────────────

class UserProfileSerializer(serializers.ModelSerializer):
    """Lecture du profil utilisateur (pas de champs sensibles)."""
    full_name = serializers.SerializerMethodField()
    wallet_id = serializers.SerializerMethodField()
    balance = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = [
            'id', 'phone_number', 'first_name', 'last_name',
            'full_name', 'role', 'is_phone_verified',
            'is_2fa_enabled', 'date_joined', 'wallet_id', 'balance'
        ]
        read_only_fields = fields

    def get_full_name(self, obj):
        return obj.get_full_name()

    def get_wallet_id(self, obj):
        try:
            return str(obj.wallet.wallet_id)
        except Exception:
            return None

    def get_balance(self, obj):
        try:
            return str(obj.wallet.balance)
        except Exception:
            return '0.00'


# ── Changement de PIN ─────────────────────────────────────────────────────────

class ChangePinSerializer(serializers.Serializer):
    """Permet de changer le PIN en fournissant l'ancien."""
    current_pin = serializers.CharField(min_length=4, max_length=4, write_only=True)
    new_pin = serializers.CharField(min_length=4, max_length=4, write_only=True)
    confirm_pin = serializers.CharField(min_length=4, max_length=4, write_only=True)

    def validate(self, data):
        if not data['new_pin'].isdigit():
            raise serializers.ValidationError({'new_pin': 'Le PIN doit être numérique.'})
        if data['new_pin'] != data['confirm_pin']:
            raise serializers.ValidationError({'confirm_pin': 'Les PINs ne correspondent pas.'})
        return data


# ── Audit Log ─────────────────────────────────────────────────────────────────

class AuditLogSerializer(serializers.ModelSerializer):
    class Meta:
        model = AuditLog
        fields = ['id', 'action', 'ip_address', 'details', 'created_at']
        read_only_fields = fields
