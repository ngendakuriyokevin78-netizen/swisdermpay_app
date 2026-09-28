"""Sème le menu *300# par défaut (idempotent)."""
from django.core.management.base import BaseCommand


DEFAULTS = [
    ('root', '1', 'Envoyer', 1),
    ('root', '2', 'Attente', 2),
    ('root', '3', 'Valider', 3),
    ('root', '4', 'Solde', 4),
    ('root', '5', 'Annuler', 5),
    ('root', '9', 'Plus', 9),
    ('plus', '6', 'Histo', 6),
    ('plus', '7', 'Achat', 7),
    ('plus', '8', 'Retrait', 8),
    ('plus', '9', 'Compte', 9),
    ('compte', '1', 'Créer', 1),
    ('compte', '2', 'PIN', 2),
    ('compte', '3', 'Nom', 3),
]


class Command(BaseCommand):
    help = 'Sème UssdConfig + options menu *300# (idempotent)'

    def handle(self, *args, **kwargs):
        from apps.interop.models import UssdConfig, UssdMenuOption
        cfg, created = UssdConfig.objects.get_or_create(
            short_code='*300#',
            defaults={'help_text': 'Cash Tel : 1 Envoyer, 2 Attente, 3 Valider.'})
        n = 0
        for parent, key, label, order in DEFAULTS:
            _, c = UssdMenuOption.objects.get_or_create(
                key=key if parent == 'root' else f'{parent}:{key}',
                defaults={'parent': parent, 'label': label, 'order': order, 'enabled': True})
            n += c
        self.stdout.write(self.style.SUCCESS(f'USSD seed OK (config {"créée" if created else "existante"}, +{n} options)'))
