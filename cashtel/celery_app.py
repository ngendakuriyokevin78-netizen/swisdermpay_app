"""
Configuration Celery pour Cash Tel.
Gère les tâches asynchrones : envoi SMS, nettoyage OTP, etc.
"""
import os
from celery import Celery

# Définit le module de settings Django pour Celery
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'cashtel.settings')

app = Celery('cashtel')

# Charge la config depuis Django settings (préfixe CELERY_)
app.config_from_object('django.conf:settings', namespace='CELERY')

# Découverte automatique des tâches dans tous les apps installés
app.autodiscover_tasks()


@app.task(bind=True, ignore_result=True)
def debug_task(self):
    """Tâche de debug pour vérifier que Celery fonctionne."""
    print(f'Requête : {self.request!r}')
