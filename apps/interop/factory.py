"""Résolution d'adaptateur opérateur (ajout seul)."""
import logging
from django.utils.module_loading import import_string

logger = logging.getLogger('apps.interop')


def get_provider_adapter(provider):
    path = provider.adapter_class or 'apps.interop.adapters.mock_adapter.MockProviderAdapter'
    try:
        cls = import_string(path)
    except Exception as e:
        logger.error(f"Adaptateur introuvable {path}: {e}")
        from .adapters.mock_adapter import MockProviderAdapter
        cls = MockProviderAdapter
    return cls(provider)
