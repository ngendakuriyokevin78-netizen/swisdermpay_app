"""Seed partenaires banques + opérateurs (idempotent, ajout seul)."""
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = 'Crée CRDB + Lumicash/eNoti(Bancobu)/eHela en mode mock (TESTING)'

    def handle(self, *args, **options):
        from apps.banking.models import BankPartner
        from apps.interop.models import ExternalProvider

        bank, _ = BankPartner.objects.get_or_create(
            code='CRDB', defaults={
                'name': 'CRDB Burundi', 'status': 'TESTING', 'is_default': True,
                'adapter_class': 'apps.banking.adapters.mock_adapter.MockBankAdapter'})
        self.stdout.write(self.style.SUCCESS(f"Banque: {bank.code} {bank.name}"))

        for code, name, adapter in [
            ('LUMICASH', 'LumiCash (Econet Leo)', 'apps.interop.adapters.mock_adapter.MockProviderAdapter'),
            ('ENOTI', 'Bancobu eNoti', 'apps.interop.adapters.mock_adapter.MockProviderAdapter'),
            ('EHELA', 'eHela', 'apps.interop.adapters.mock_adapter.MockProviderAdapter'),
        ]:
            p, _ = ExternalProvider.objects.get_or_create(
                code=code, defaults={'name': name, 'status': 'TESTING', 'adapter_class': adapter})
            self.stdout.write(self.style.SUCCESS(f"Operateur: {code}"))
