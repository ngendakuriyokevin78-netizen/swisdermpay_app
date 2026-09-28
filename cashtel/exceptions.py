"""
Gestionnaire d'exceptions personnalisé pour Cash Tel.
Retourne toujours du JSON avec un format cohérent.
"""
from rest_framework.views import exception_handler
from rest_framework.response import Response
import logging

logger = logging.getLogger('cashtel')


def custom_exception_handler(exc, context):
    """
    Transforme toutes les exceptions DRF en réponse JSON normalisée.
    Format : {"success": false, "error": "...", "details": {...}}
    """
    response = exception_handler(exc, context)

    if response is not None:
        # Normalise le format de réponse
        error_data = {
            'success': False,
            'error': _extract_error_message(response.data),
            'details': response.data if isinstance(response.data, dict) else {},
        }
        response.data = error_data

        logger.warning(
            f"[API Error] {context['view'].__class__.__name__} "
            f"— {exc.__class__.__name__}: {exc}"
        )

    return response


def _extract_error_message(data):
    """Extrait un message d'erreur lisible depuis les données DRF."""
    if isinstance(data, dict):
        if 'detail' in data:
            return str(data['detail'])
        # Prend le premier champ en erreur
        for key, value in data.items():
            if isinstance(value, list) and value:
                return f"{key}: {value[0]}"
        return "Une erreur est survenue."
    elif isinstance(data, list) and data:
        return str(data[0])
    return str(data)
