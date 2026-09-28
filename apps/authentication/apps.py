from django.apps import AppConfig


class AuthenticationConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.authentication'
    verbose_name = 'Authentification'

    def ready(self):
        """Connecte les signaux à la création d'un utilisateur."""
        import apps.authentication.signals  # noqa: F401
