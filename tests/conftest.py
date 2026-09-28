"""Fixture globale : plafond float très haut pour les anciens tests (ajout seul)."""
import pytest
from decimal import Decimal


@pytest.fixture(autouse=True)
def _high_float_ceiling(db):
    from apps.banking.models import BankPartner, BankFloat
    bank, _ = BankPartner.objects.get_or_create(
        code='CRDB', defaults={
            'name': 'CRDB', 'status': 'TESTING',
            'adapter_class': 'apps.banking.adapters.mock_adapter.MockBankAdapter'})
    BankFloat.objects.update_or_create(
        bank=bank, defaults={'ceiling': Decimal('1000000000000')})
