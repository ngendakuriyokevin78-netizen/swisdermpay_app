"""Initialise l'application Celery au démarrage de Django."""
from .celery_app import app as celery_app

__all__ = ('celery_app',)
