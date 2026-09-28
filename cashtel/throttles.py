"""Throttles sécurité — AJOUT SEUL (aucune vue existante modifiée par ce fichier)."""
import logging
from rest_framework.throttling import AnonRateThrottle, UserRateThrottle

logger = logging.getLogger('cashtel')


class _FailOpenMixin:
    """Sans Redis en local (runserver Windows), le throttle laisse passer au lieu de 500."""

    def allow_request(self, request, view):
        try:
            return super().allow_request(request, view)
        except Exception as e:
            logger.warning(f"Throttle inopérant (cache KO), accès autorisé : {e}")
            return True


class ResilientAnonThrottle(_FailOpenMixin, AnonRateThrottle):
    pass


class ResilientUserThrottle(_FailOpenMixin, UserRateThrottle):
    pass


class LoginRateThrottle(_FailOpenMixin, AnonRateThrottle):
    scope = 'login'


class OtpRateThrottle(_FailOpenMixin, AnonRateThrottle):
    scope = 'otp'


class UssdRateThrottle(_FailOpenMixin, AnonRateThrottle):
    scope = 'ussd'


class StrictUserThrottle(_FailOpenMixin, UserRateThrottle):
    scope = 'strict_user'
