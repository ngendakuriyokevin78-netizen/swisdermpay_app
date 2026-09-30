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
    """
    Inscription ouverte à tous :
    - phone_number + prénom/nom + password (connexion app internet)
    - pin OPTIONNEL (ancien flux). Si absent, à créer plus tard dans l'app
      via POST /api/auth/set-pin/ et exigé uniquement pour les transferts.
    Rétro-compat : pin seul (sans password) reste accepté.
    """
    pin = serializers.CharField(
        write_only=True, min_length=4, max_length=4, required=False,
        help_text='PIN transfert 4 chiffres (optionnel à l’inscription, à créer dans l’app)'
    )
    password = serializers.CharField(
        write_only=True, required=False, min_length=8, max_length=128,
        help_text='Mot de passe connexion (min 8 caractères, recommandé)'
    )

    class Meta:
        model = User
        fields = ['phone_number', 'first_name', 'last_name', 'pin', 'password']

    def validate_phone_number(self, value):
        """Normalisation +257 + détection Lumitel (recommandation, jamais bloquant)."""
        from .phone_utils import normalize_phone
        try:
            return normalize_phone(value)
        except ValueError as e:
            raise serializers.ValidationError(str(e))

    def validate_pin(self, value):
        """Vérifie que le PIN est bien numérique à 4 chiffres."""
        if value in (None, ''):
            return value
        if not str(value).isdigit() or len(str(value)) != 4:
            raise serializers.ValidationError('Le PIN transfert doit être 4 chiffres.')
        return value

    def validate(self, data):
        # Au moins password OU pin (compat anciens clients pin-only)
        if not data.get('password') and not data.get('pin'):
            raise serializers.ValidationError(
                {'password': 'Mot de passe requis (min 8 caractères). PIN seul accepté pour compatibilité.'}
            )
        pwd = data.get('password') or ''
        if pwd and len(pwd) < 8:
            raise serializers.ValidationError({'password': 'Mot de passe : 8 caractères minimum.'})
        return data

    def create(self, validated_data):
        pin = validated_data.pop('pin', None)
        password = validated_data.pop('password', None)

        user = User(**validated_data)
        user.set_password(password or get_random_string(12))
        if pin:
            user.set_pin(pin)
        # Sinon pin reste NULL -> à créer dans l'app (set-pin), transferts bloqués d'ici là
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
    """
    Connexion app internet : password en priorité.
    Rétro-compat : pin accepté si password absent (anciens comptes + USSD).
    """
    phone_number = serializers.CharField()
    password = serializers.CharField(write_only=True, required=False, allow_blank=True)
    pin = serializers.CharField(
        min_length=4, max_length=4, write_only=True, required=False, allow_blank=True
    )

    def validate(self, data):
        if not (data.get('password') or data.get('pin')):
            raise serializers.ValidationError(
                {'password': 'Mot de passe ou PIN requis.'}
            )
        return data


# ── Profil utilisateur ────────────────────────────────────────────────────────

class UserProfileSerializer(serializers.ModelSerializer):
    """Lecture du profil utilisateur (pas de champs sensibles)."""
    full_name = serializers.SerializerMethodField()
    wallet_id = serializers.SerializerMethodField()
    balance = serializers.SerializerMethodField()
    has_pin = serializers.SerializerMethodField()
    operator = serializers.SerializerMethodField()
    is_lumitel = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = [
            'id', 'phone_number', 'first_name', 'last_name',
            'full_name', 'role', 'is_phone_verified',
            'is_2fa_enabled', 'date_joined', 'wallet_id', 'balance',
            'has_pin', 'operator', 'is_lumitel',
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

    def get_has_pin(self, obj):
        return bool(obj.pin)

    def get_operator(self, obj):
        try:
            from .phone_utils import operator_of
            return operator_of(obj.phone_number)
        except Exception:
            return 'INCONNU'

    def get_is_lumitel(self, obj):
        try:
            from .phone_utils import is_lumitel
            return is_lumitel(obj.phone_number)
        except Exception:
            return False


# ── Création PIN transfert depuis l'intérieur de l'app ──────────────────────

class SetPinSerializer(serializers.Serializer):
    """Crée le code transfert 4 chiffres une fois connecté (intérieur app)."""
    pin = serializers.CharField(min_length=4, max_length=4, write_only=True)
    confirm_pin = serializers.CharField(min_length=4, max_length=4, write_only=True)

    def validate(self, data):
        if not str(data['pin']).isdigit() or len(str(data['pin'])) != 4:
            raise serializers.ValidationError({'pin': 'Le code transfert doit être 4 chiffres.'})
        if data['pin'] != data['confirm_pin']:
            raise serializers.ValidationError({'confirm_pin': 'Les codes ne correspondent pas.'})
        return data


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
