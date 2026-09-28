"""
Administration Django pour l'authentification.
Dashboard complet : users, rôles, audit logs, blocages.
"""
from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.utils.html import format_html
from .models import User, AuditLog


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    """Interface admin pour les utilisateurs Cash Tel."""

    list_display = [
        'phone_number', 'get_full_name', 'role',
        'is_phone_verified', 'is_blocked', 'failed_pin_attempts',
        'is_active', 'date_joined'
    ]
    list_filter = ['role', 'is_phone_verified', 'is_blocked', 'is_active', 'is_2fa_enabled']
    search_fields = ['phone_number', 'first_name', 'last_name']
    ordering = ['-date_joined']
    readonly_fields = ['id', 'date_joined', 'last_login', 'pin']

    fieldsets = (
        ('Identité', {
            'fields': ('id', 'phone_number', 'first_name', 'last_name', 'role')
        }),
        ('Sécurité', {
            'fields': ('pin', 'failed_pin_attempts', 'is_blocked', 'is_2fa_enabled'),
            'classes': ('collapse',),
        }),
        ('Vérification', {
            'fields': ('is_phone_verified', 'otp', 'otp_expires_at'),
            'classes': ('collapse',),
        }),
        ('Permissions Django', {
            'fields': ('is_active', 'is_staff', 'is_superuser', 'groups', 'user_permissions'),
            'classes': ('collapse',),
        }),
        ('Dates', {'fields': ('date_joined', 'last_login')}),
    )

    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('phone_number', 'first_name', 'last_name', 'role', 'password1', 'password2'),
        }),
    )

    actions = ['debloquer_comptes', 'bloquer_comptes']

    @admin.action(description='Débloquer les comptes sélectionnés')
    def debloquer_comptes(self, request, queryset):
        updated = queryset.update(is_blocked=False, failed_pin_attempts=0)
        self.message_user(request, f'{updated} compte(s) débloqué(s).')

    @admin.action(description='Bloquer les comptes sélectionnés')
    def bloquer_comptes(self, request, queryset):
        updated = queryset.update(is_blocked=True)
        self.message_user(request, f'{updated} compte(s) bloqué(s).')


@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    """Interface admin pour le journal d'audit."""

    list_display = ['action', 'user', 'ip_address', 'created_at']
    list_filter = ['action', 'created_at']
    search_fields = ['user__phone_number', 'action', 'ip_address']
    ordering = ['-created_at']
    readonly_fields = ['user', 'action', 'ip_address', 'details', 'created_at']

    def has_add_permission(self, request):
        return False  # Journal en lecture seule

    def has_change_permission(self, request, obj=None):
        return False
