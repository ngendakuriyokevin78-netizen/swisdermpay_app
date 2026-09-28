"""
Config API entreprises partenaires modifiable sans code source — AJOUT SEUL.
- GET /api/interop/providers-config/ (ADMIN : configs, secrets masqués)
- PUT /api/interop/providers-config/ (ADMIN : {code, api_base_url?, api_key?, api_secret?, merchant_id?, webhook_url?, webhook_secret?, adapter_class?, status?})
Écrit ExternalProvider (déjà visible dans /admin/). Vide = garder le secret.
"""
from decimal import Decimal, InvalidOperation
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated


def _is_admin(u):
    return bool(u and u.is_authenticated and (getattr(u, 'role', '') == 'ADMIN' or getattr(u, 'is_staff', False)))


def _mask(s: str) -> str:
    s = s or ''
    if len(s) <= 4:
        return '****' if s else ''
    return s[:2] + '****' + s[-2:]


class ProviderConfigView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        from apps.interop.models import ExternalProvider
        if not _is_admin(request.user):
            return Response({'success': False, 'error': 'Réservé ADMIN.'}, status=403)
        out = [{'code': p.code, 'name': p.name, 'provider_type': p.provider_type,
                'status': p.status, 'api_base_url': p.api_base_url,
                'api_key_masked': _mask(p.api_key), 'api_secret_set': bool(p.api_secret),
                'merchant_id': p.merchant_id, 'webhook_url': p.webhook_url,
                'webhook_secret_set': bool(p.webhook_secret),
                'adapter_class': p.adapter_class,
                'fee_percentage': str(p.fee_percentage), 'fee_fixed': str(p.fee_fixed)}
               for p in ExternalProvider.objects.order_by('name')]
        return Response({'success': True, 'providers': out})

    def put(self, request):
        from apps.interop.models import ExternalProvider
        from apps.authentication.services import AuditService
        if not _is_admin(request.user):
            return Response({'success': False, 'error': 'Réservé ADMIN.'}, status=403)
        data = request.data if isinstance(request.data, dict) else {}
        code = str(data.get('code') or '').strip()
        if not code:
            return Response({'success': False, 'error': 'Code entreprise requis.'}, status=400)
        try:
            p = ExternalProvider.objects.get(code=code)
        except ExternalProvider.DoesNotExist:
            return Response({'success': False, 'error': 'Entreprise introuvable.'}, status=404)
        changed = []
        for f in ('api_base_url', 'merchant_id', 'webhook_url', 'adapter_class', 'status', 'name'):
            if data.get(f) is not None:
                setattr(p, f, str(data[f])[:255] if f != 'adapter_class' else str(data[f])[:100])
                changed.append(f)
        for f in ('api_key', 'api_secret', 'webhook_secret'):
            if data.get(f):  # vide = garder
                setattr(p, f, str(data[f])[:255])
                changed.append(f)
        for f in ('fee_percentage', 'fee_fixed', 'min_transfer', 'max_transfer'):
            if data.get(f) is not None and str(data.get(f)) != '':
                try:
                    setattr(p, f, Decimal(str(data[f])))
                    changed.append(f)
                except (InvalidOperation, ValueError):
                    return Response({'success': False, 'error': f'Montant invalide : {f}.'}, status=400)
        p.save()
        AuditService.log(user=request.user, action='PROVIDER_CONFIG_UPDATED',
                         details={'provider': code, 'fields': changed})
        return Response({'success': True, 'message': f'{code} mis à jour sans code source.',
                         'updated': changed})

    def post(self, request):
        """Crée une nouvelle entreprise e-money (ADMIN) — plusieurs partenaires possibles."""
        from apps.interop.models import ExternalProvider
        from apps.authentication.services import AuditService
        if not _is_admin(request.user):
            return Response({'success': False, 'error': 'Réservé ADMIN.'}, status=403)
        data = request.data if isinstance(request.data, dict) else {}
        code = str(data.get('code') or '').strip().upper()[:20]
        name = str(data.get('name') or code).strip()[:100]
        if not code:
            return Response({'success': False, 'error': 'Code requis (ex: LUMICASH).'}, status=400)
        if ExternalProvider.objects.filter(code=code).exists():
            return Response({'success': False, 'error': f'{code} existe déjà.'}, status=400)
        try:
            p = ExternalProvider.objects.create(
                code=code, name=name or code,
                provider_type=str(data.get('provider_type') or 'MOBILE_MONEY')[:20],
                api_base_url=str(data.get('api_base_url', ''))[:255],
                api_key=str(data.get('api_key', ''))[:255],
                api_secret=str(data.get('api_secret', ''))[:255],
                merchant_id=str(data.get('merchant_id', ''))[:100],
                webhook_url=str(data.get('webhook_url', ''))[:255],
                webhook_secret=str(data.get('webhook_secret', ''))[:255],
                adapter_class=str(data.get('adapter_class') or 'apps.interop.adapters.mock_adapter.MockProviderAdapter')[:100],
                status=str(data.get('status') or 'TESTING')[:20],
            )
        except Exception as e:
            return Response({'success': False, 'error': f'Création impossible : {e}.'}, status=400)
        AuditService.log(user=request.user, action='PROVIDER_CREATED', details={'provider': code})
        return Response({'success': True, 'message': f'Entreprise {code} ajoutée.', 'code': p.code})
