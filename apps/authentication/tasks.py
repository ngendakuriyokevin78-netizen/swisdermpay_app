"""
Tâches Celery pour l'authentification.
Envoi asynchrone de SMS pour ne pas bloquer les requêtes HTTP.
"""
from celery import shared_task
import logging

logger = logging.getLogger('apps.authentication')


@shared_task(name='authentication.send_sms', bind=True, max_retries=3)
def send_sms_task(self, phone: str, message: str):
    """
    Envoie un SMS de manière asynchrone.
    Retente 3 fois en cas d'échec (backoff exponentiel).
    """
    try:
        from .services import SMSService
        SMSService.send(phone, message)
        logger.info(f"SMS envoyé avec succès à {phone}")
    except Exception as exc:
        logger.error(f"Échec envoi SMS à {phone}: {exc}")
        # Réessai avec délai exponentiel
        raise self.retry(exc=exc, countdown=2 ** self.request.retries)
