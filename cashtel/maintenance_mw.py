"""
Middleware maintenance — AJOUT SEUL.
Bloque les écritures financières pendant une coupure (503 + fin prévue),
sauf ADMIN et sauf lecture (GET) et sauf les routes maintenance elles-mêmes.
"""
import logging
from django.http import JsonResponse

logger = logging.getLogger('cashtel')

BLOCKED_PREFIXES = (
    '/api/transfer/', '/api/shop/orders/', '/api/shop/scan-pay/',
    '/api/agent/', '/api/bills/', '/api/banking/', '/api/interop/send/',
    '/api/interop/ussd/', '/api/interop/sms/',
)
ALWAYS_OPEN = (
    '/api/auth/maintenance/status/', '/api/auth/maintenance/set/',
    '/api/auth/maintenance/clear/', '/api/docs/', '/api/redoc/',
    '/admin/', '/m/',
)


class MaintenanceMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.method in ('POST', 'PUT', 'PATCH', 'DELETE'):
            path = request.path or ''
            if path.startswith(BLOCKED_PREFIXES) and not path.startswith(ALWAYS_OPEN):
                try:
                    from apps.authentication.models import MaintenanceWindow
                    mw = MaintenanceWindow.current()
                except Exception:
                    mw = None
                if mw:
                    user = getattr(request, 'user', None)
                    is_admin = bool(user and user.is_authenticated and (
                        getattr(user, 'role', '') == 'ADMIN' or getattr(user, 'is_staff', False)))
                    if not is_admin:
                        logger.warning(f"[MAINTENANCE] bloqué {path} ({mw.reason})")
                        return JsonResponse({
                            'success': False,
                            'error': 'Service interrompu pour réparation.',
                            'maintenance': True,
                            'reason': mw.reason,
                            'ends_at': mw.ends_at,
                        }, status=503)
        return self.get_response(request)
