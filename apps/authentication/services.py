"""
Services métier pour l'authentification Cash Tel.
- OTPService : génération et vérification OTP
- SMSService : envoi SMS (mockable)
- AuditService : journal d'audit
"""
import random
import string
import logging
from datetime import timedelta
from django.utils import timezone
from django.conf import settings

logger = logging.getLogger('apps.authentication')


# ── Service OTP ───────────────────────────────────────────────────────────────

class OTPService:
    """Gère la génération et la vérification des OTP à 6 chiffres."""

    @staticmethod
    def generate() -> str:
        """Génère un OTP numérique à 6 chiffres."""
        return ''.join(random.choices(string.digits, k=6))

    @staticmethod
    def send_otp(user) -> str:
        """
        Génère un OTP, l'attache à l'utilisateur et l'envoie par SMS.
        Retourne l'OTP (utile pour les tests).
        """
        otp = OTPService.generate()
        user.otp = otp
        user.otp_expires_at = timezone.now() + timedelta(
            minutes=settings.OTP_EXPIRY_MINUTES
        )
        user.save(update_fields=['otp', 'otp_expires_at'])

        # Envoi SMS
        SMSService.send(
            phone=user.phone_number,
            message=f"Swisderm Pay: Votre code de vérification est {otp}. Valide {settings.OTP_EXPIRY_MINUTES} min."
        )

        logger.info(f"OTP généré pour {user.phone_number}")
        return otp

    @staticmethod
    def verify(user, otp_code: str) -> bool:
        """
        Vérifie l'OTP fourni.
        Retourne True si valide et non expiré, False sinon.
        Anti-bruteforce SANS migration : compteur en cache (5 essais / 10 min).
        """
        from django.core.cache import cache

        if not user.otp or not user.otp_expires_at:
            return False

        cache_key = f"otp_fail:{user.phone_number}"
        try:
            fails = int(cache.get(cache_key) or 0)
        except Exception:
            fails = 0
        if fails >= 5:
            logger.warning(f"OTP bloqué temporairement pour {user.phone_number} (5 échecs)")
            return False

        # Vérification expiration
        if timezone.now() > user.otp_expires_at:
            logger.warning(f"OTP expiré pour {user.phone_number}")
            return False

        # Vérification valeur
        if user.otp != str(otp_code):
            logger.warning(f"OTP incorrect pour {user.phone_number}")
            try:
                cache.set(cache_key, fails + 1, timeout=600)
            except Exception:
                pass
            return False

        # Succès : reset compteur + invalide l'OTP après usage (usage unique)
        try:
            cache.delete(cache_key)
        except Exception:
            pass
        user.otp = None
        user.otp_expires_at = None
        user.is_phone_verified = True
        user.save(update_fields=['otp', 'otp_expires_at', 'is_phone_verified'])

        logger.info(f"OTP validé pour {user.phone_number}")
        return True


# ── Service SMS ───────────────────────────────────────────────────────────────

class SMSService:
    """
    Service d'envoi SMS.
    Backend configurable via SMS_BACKEND dans settings :
    - 'mock' : affiche le message dans les logs (développement)
    - 'africastalking' : envoie via Africa's Talking (production)
    """

    @staticmethod
    def send(phone: str, message: str):
        """Envoie un SMS synchrone."""
        backend = getattr(settings, 'SMS_BACKEND', 'mock')

        if backend == 'mock':
            SMSService._mock_send(phone, message)
        elif backend == 'africastalking':
            SMSService._africastalking_send(phone, message)
        else:
            logger.warning(f"Backend SMS inconnu : {backend}")

    @staticmethod
    def _redis_reachable() -> bool:
        """Test rapide (<1s) : évite 60s d'attente Celery quand Redis est coupé (dev local)."""
        try:
            from urllib.parse import urlparse
            import socket
            parts = urlparse(getattr(settings, 'REDIS_URL', 'redis://localhost:6379/0'))
            sock = socket.create_connection((parts.hostname or 'localhost', parts.port or 6379), timeout=1)
            sock.close()
            return True
        except Exception:
            return False

    @staticmethod
    def send_async(phone: str, message: str):
        """Envoie un SMS via Celery, avec repli synchrone immédiat si Redis indisponible."""
        try:
            if not SMSService._redis_reachable():
                raise ConnectionError("Redis injoignable")
            from .tasks import send_sms_task
            send_sms_task.delay(phone, message)
        except Exception:
            logger.warning("Celery indisponible, envoi SMS synchrone.")
            SMSService.send(phone, message)

    @staticmethod
    def _mock_send(phone: str, message: str):
        """Backend mock : affiche dans les logs (compatible Windows/cp1252)."""
        logger.info(f"[SMS MOCK] -> {phone}: {message}")
        try:
            print(f"\n{'='*60}")
            print(f"[SMS] -> {phone}")
            print(f"   {message}")
            print(f"{'='*60}\n")
        except UnicodeEncodeError:
            # Console Windows sans UTF-8 : retombe sur ASCII
            safe = message.encode('ascii', 'replace').decode()
            print(f"[SMS] -> {phone}: {safe}")

    @staticmethod
    def _africastalking_send(phone: str, message: str):
        """Backend Africa's Talking pour la production."""
        try:
            import africastalking
            africastalking.initialize(
                settings.AFRICAS_TALKING_USERNAME,
                settings.AFRICAS_TALKING_API_KEY
            )
            sms = africastalking.SMS
            response = sms.send(
                message,
                [phone],
                sender_id=settings.AFRICAS_TALKING_SENDER_ID
            )
            logger.info(f"SMS envoyé via Africa's Talking : {response}")
        except Exception as e:
            logger.error(f"Erreur envoi SMS Africa's Talking vers {phone}: {e}")


# ── Service Audit ─────────────────────────────────────────────────────────────

class AuditService:
    """Enregistre les actions sensibles dans le journal d'audit."""

    @staticmethod
    def log(user, action: str, details: dict = None, ip_address: str = None):
        """
        Crée une entrée dans le journal d'audit.

        Paramètres :
        - user : l'utilisateur concerné (peut être None)
        - action : code de l'action (ex: 'LOGIN', 'TRANSFER_SENT')
        - details : données supplémentaires (JSON)
        - ip_address : adresse IP de la requête
        """
        from .models import AuditLog
        try:
            AuditLog.objects.create(
                user=user,
                action=action,
                ip_address=ip_address,
                details=details or {}
            )
            logger.debug(f"[AUDIT] {action} — user={user}")
        except Exception as e:
            logger.error(f"Impossible d'enregistrer l'audit log: {e}")

    @staticmethod
    def get_client_ip(request) -> str:
        """Extrait l'IP réelle depuis les headers (proxy-aware)."""
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            return x_forwarded_for.split(',')[0].strip()
        return request.META.get('REMOTE_ADDR')
