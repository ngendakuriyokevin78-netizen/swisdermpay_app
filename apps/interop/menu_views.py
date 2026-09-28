"""
Menu *300# modifiable sans code source — AJOUT SEUL.
- GET /api/interop/ussd-menu/ (public : affiche code + options actives)
- PUT /api/interop/ussd-menu/ (ADMIN : change code, libellés, activation)
Lit/écrit UssdConfig + UssdMenuOption (visibles aussi dans /admin/).
"""
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import AllowAny, IsAuthenticated


def _dump():
    from apps.interop.models import UssdConfig, UssdMenuOption
    code = UssdConfig.current_code()
    opts = [{'key': o.key, 'parent': o.parent, 'label': o.label,
             'enabled': o.enabled, 'order': o.order}
            for o in UssdMenuOption.objects.order_by('parent', 'order', 'key')]
    return code, opts


class UssdMenuReadView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    def get(self, request):
        code, opts = _dump()
        return Response({'success': True, 'short_code': code, 'options': opts})


class UssdMenuWriteView(APIView):
    permission_classes = [IsAuthenticated]

    def put(self, request):
        from apps.interop.models import UssdConfig, UssdMenuOption
        from apps.authentication.services import AuditService
        u = request.user
        if not (getattr(u, 'role', '') == 'ADMIN' or getattr(u, 'is_staff', False)):
            return Response({'success': False, 'error': 'Réservé ADMIN.'}, status=403)
        data = request.data if isinstance(request.data, dict) else {}
        if 'short_code' in data:
            code = str(data['short_code']).strip()[:20] or '*300#'
            UssdConfig.objects.create(short_code=code,
                                      help_text=str(data.get('help_text', ''))[:255])
        for item in (data.get('options') or [])[:30]:
            try:
                o = UssdMenuOption.objects.get(key=str(item.get('key')))
            except UssdMenuOption.DoesNotExist:
                continue
            if 'label' in item:
                o.label = str(item['label'])[:60]
            if 'enabled' in item:
                o.enabled = bool(item['enabled'])
            if 'order' in item:
                try:
                    o.order = int(item['order'])
                except (TypeError, ValueError):
                    pass
            o.save(update_fields=['label', 'enabled', 'order'])
        AuditService.log(user=u, action='USSD_MENU_UPDATED',
                         details={'short_code': data.get('short_code'), 'n': len(data.get('options') or [])})
        code, opts = _dump()
        return Response({'success': True, 'message': 'Menu *300# mis à jour sans code source.',
                         'short_code': code, 'options': opts})
