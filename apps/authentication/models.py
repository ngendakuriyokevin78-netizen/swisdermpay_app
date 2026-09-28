"""
Modèles d'authentification Cash Tel.
- User : modèle utilisateur personnalisé avec PIN hashé et OTP
- AuditLog : journal d'audit pour les actions sensibles
"""
import uuid
from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin
from django.contrib.auth.hashers import make_password, check_password as django_check_password
from django.db import models
from django.utils import timezone


# ── Manager utilisateur ────────────────────────────────────────────────────────

class UserManager(BaseUserManager):
    """Manager personnalisé utilisant phone_number comme identifiant principal."""

    def create_user(self, phone_number, password=None, **extra_fields):
        if not phone_number:
            raise ValueError('Le numéro de téléphone est obligatoire.')
        user = self.model(phone_number=phone_number, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, phone_number, password=None, **extra_fields):
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        extra_fields.setdefault('role', User.Role.ADMIN)
        extra_fields.setdefault('is_phone_verified', True)

        if not extra_fields.get('is_staff'):
            raise ValueError('Le superutilisateur doit avoir is_staff=True.')
        if not extra_fields.get('is_superuser'):
            raise ValueError('Le superutilisateur doit avoir is_superuser=True.')

        return self.create_user(phone_number, password, **extra_fields)


# ── Modèle Utilisateur ─────────────────────────────────────────────────────────

class User(AbstractBaseUser, PermissionsMixin):
    """
    Utilisateur Cash Tel.
    Identification par numéro de téléphone.
    Rôles : USER (client standard), AGENT (cash in/out), ADMIN.
    """

    class Role(models.TextChoices):
        USER = 'USER', 'Utilisateur'
        AGENT = 'AGENT', 'Agent'
        ADMIN = 'ADMIN', 'Administrateur'

    # ── Identité ────────────────────────────────────────────────────────────────
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    phone_number = models.CharField(
        max_length=20, unique=True,
        verbose_name='Numéro de téléphone',
        help_text='Format : +25762XXXXXXX'
    )
    first_name = models.CharField(max_length=100, verbose_name='Prénom')
    last_name = models.CharField(max_length=100, verbose_name='Nom')
    role = models.CharField(
        max_length=10, choices=Role.choices,
        default=Role.USER, verbose_name='Rôle'
    )

    # ── PIN sécurisé ────────────────────────────────────────────────────────────
    pin = models.CharField(
        max_length=128, blank=True, null=True,
        verbose_name='PIN hashé (PBKDF2)'
    )
    failed_pin_attempts = models.PositiveSmallIntegerField(
        default=0, verbose_name='Tentatives PIN échouées'
    )
    is_blocked = models.BooleanField(
        default=False, verbose_name='Compte bloqué'
    )

    # ── OTP (One Time Password) pour inscription ────────────────────────────────
    otp = models.CharField(max_length=6, blank=True, null=True)
    otp_expires_at = models.DateTimeField(blank=True, null=True)
    is_phone_verified = models.BooleanField(
        default=False, verbose_name='Téléphone vérifié'
    )

    # ── Double authentification ──────────────────────────────────────────────────
    is_2fa_enabled = models.BooleanField(
        default=False, verbose_name='2FA activée'
    )

    # ── Champs Django standard ───────────────────────────────────────────────────
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)
    date_joined = models.DateTimeField(default=timezone.now)

    objects = UserManager()

    USERNAME_FIELD = 'phone_number'
    REQUIRED_FIELDS = ['first_name', 'last_name']

    class Meta:
        verbose_name = 'Utilisateur'
        verbose_name_plural = 'Utilisateurs'
        ordering = ['-date_joined']

    def __str__(self):
        return f"{self.get_full_name()} ({self.phone_number})"

    def get_full_name(self):
        return f"{self.first_name} {self.last_name}"

    def get_short_name(self):
        return self.first_name

    # ── Méthodes PIN ────────────────────────────────────────────────────────────

    def set_pin(self, raw_pin: str):
        """Hash et enregistre le PIN avec PBKDF2."""
        if not str(raw_pin).isdigit() or len(str(raw_pin)) != 4:
            raise ValueError('Le PIN doit être composé de 4 chiffres.')
        self.pin = make_password(str(raw_pin))

    def check_pin(self, raw_pin: str) -> bool:
        """Vérifie le PIN fourni contre le hash stocké."""
        if not self.pin:
            return False
        return django_check_password(str(raw_pin), self.pin)

    # ── Propriétés ──────────────────────────────────────────────────────────────

    @property
    def is_agent(self):
        return self.role == self.Role.AGENT

    @property
    def is_admin_user(self):
        return self.role == self.Role.ADMIN


# ── Journal d'Audit ───────────────────────────────────────────────────────────

class AuditLog(models.Model):
    """
    Journal d'audit pour traçabilité des actions sensibles.
    Ex: connexion, transfert, blocage de compte.
    """
    user = models.ForeignKey(
        User, on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='audit_logs',
        verbose_name='Utilisateur'
    )
    action = models.CharField(max_length=100, verbose_name='Action')
    ip_address = models.GenericIPAddressField(
        null=True, blank=True, verbose_name='Adresse IP'
    )
    details = models.JSONField(default=dict, verbose_name='Détails')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Journal d'audit"
        verbose_name_plural = "Journaux d'audit"
        ordering = ['-created_at']

    def __str__(self):
        return f"[{self.action}] {self.user} — {self.created_at:%d/%m/%Y %H:%M}"


# ── Maintenance / Réparation (AJOUT SEUL — nouvelle table uniquement) ──────

class MaintenanceWindow(models.Model):
    """Coupure programmée par l'ADMIN pour réparation. Fin auto après durée."""

    reason = models.CharField(max_length=255, blank=True, verbose_name='Motif')
    starts_at = models.DateTimeField(verbose_name='Début')
    ends_at = models.DateTimeField(verbose_name='Fin prévue')
    enabled = models.BooleanField(default=True, verbose_name='Active')
    created_by = models.ForeignKey(
        'authentication.User', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='maintenances',
        verbose_name='Créée par'
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Maintenance'
        verbose_name_plural = 'Maintenances'
        ordering = ['-created_at']

    def __str__(self):
        return f"Maintenance {self.starts_at:%d/%m %H:%M}→{self.ends_at:%H:%M} [{'ON' if self.enabled else 'OFF'}]"

    @classmethod
    def current(cls):
        from django.utils import timezone
        now = timezone.now()
        return cls.objects.filter(
            enabled=True, starts_at__lte=now, ends_at__gt=now
        ).order_by('-created_at').first()
