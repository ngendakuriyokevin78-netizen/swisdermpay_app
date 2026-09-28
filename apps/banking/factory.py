"""Résolution d'adaptateur bancaire (ajout seul)."""
import logging
from django.utils.module_loading import import_string

logger = logging.getLogger('apps.banking')


def get_adapter(bank_partner):
    """Instancie l'adaptateur configuré dans BankPartner.adapter_class."""
    path = bank_partner.adapter_class or 'apps.banking.adapters.mock_adapter.MockBankAdapter'
    try:
        cls = import_string(path)
    except Exception as e:
        logger.error(f"Adaptateur introuvable {path}: {e}")
        from .adapters.mock_adapter import MockBankAdapter
        cls = MockBankAdapter
    return cls(bank_partner)
