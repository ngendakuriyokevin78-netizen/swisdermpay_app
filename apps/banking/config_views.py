"""
Config API banques modifiable sans code source — AJOUT SEUL.
- GET /api/banking/partners-config/ (ADMIN : liste configs, secrets masqués)
- PUT /api/banking/partners-config/ (ADMIN : {code, api_base_url?, api_key?, api_secret?, webhook_secret?, adapter_class?, status?, min_transfer?, max_transfer?, daily_limit?})
Écrit BankPartner (déjà visible dans /admin/). Secrets : envoyez vide pour garder.
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


class BankConfigView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        from apps.banking.models import BankPartner
        if not _is_admin(request.user):
            return Response({'success': False, 'error': 'Réservé ADMIN.'}, status=403)
        out = [{'code': b.code, 'name': b.name, 'status': b.status,
                'is_default': b.is_default, 'api_base_url': b.api_base_url,
                'api_key_masked': _mask(b.api_key), 'api_secret_set': bool(b.api_secret),
                'webhook_secret_set': bool(b.webhook_secret),
                'adapter_class': b.adapter_class,
                'min_transfer': str(b.min_transfer), 'max_transfer': str(b.max_transfer),
                'daily_limit': str(b.daily_limit)}
               for b in BankPartner.objects.order_by('-is_default', 'name')]
        return Response({'success': True, 'banks': out})

    def put(self, request):
        from apps.banking.models import BankPartner
        from apps.authentication.services import AuditService
        if not _is_admin(request.user):
            return Response({'success': False, 'error': 'Réservé ADMIN.'}, status=403)
        data = request.data if isinstance(request.data, dict) else {}
        code = str(data.get('code') or '').strip()
        if not code:
            return Response({'success': False, 'error': 'Code banque requis.'}, status=400)
        try:
            b = BankPartner.objects.get(code=code)
        except BankPartner.DoesNotExist:
            return Response({'success': False, 'error': 'Banque introuvable.'}, status=404)
        changed = []
        for f in ('api_base_url', 'adapter_class', 'status', 'name', 'swift_code'):
            if f in data and data[f] is not None:
                setattr(b, f, str(data[f])[:255] if f != 'adapter_class' else str(data[f])[:100])
                changed.append(f)
        for f in ('api_key', 'api_secret', 'webhook_secret'):
            if data.get(f):  # vide = garder l'existant (secret non écrasé)
                setattr(b, f, str(data[f])[:255])
                changed.append(f)
        for f in ('min_transfer', 'max_transfer', 'daily_limit'):
            if data.get(f) is not None and str(data.get(f)) != '':
                try:
                    setattr(b, f, Decimal(str(data[f])))
                    changed.append(f)
                except (InvalidOperation, ValueError):
                    return Response({'success': False, 'error': f'Montant invalide : {f}.'}, status=400)
        if 'is_default' in data:
            b.is_default = bool(data['is_default'])
            changed.append('is_default')
        b.save()
        AuditService.log(user=request.user, action='BANK_CONFIG_UPDATED',
                         details={'bank': code, 'fields': changed})
        return Response({'success': True, 'message': f'{code} mis à jour sans code source.',
                         'updated': changed})

    def post(self, request):
        """Crée une nouvelle banque partenaire (ADMIN) — plusieurs banques possibles."""
        from apps.banking.models import BankPartner
        from apps.authentication.services import AuditService
        if not _is_admin(request.user):
            return Response({'success': False, 'error': 'Réservé ADMIN.'}, status=403)
        data = request.data if isinstance(request.data, dict) else {}
        code = str(data.get('code') or '').strip().upper()[:20]
        name = str(data.get('name') or code).strip()[:100]
        if not code:
            return Response({'success': False, 'error': 'Code banque requis (ex: BCB).'}, status=400)
        if BankPartner.objects.filter(code=code).exists():
            return Response({'success': False, 'error': f'{code} existe déjà (utilisez Enregistrer).'}, status=400)
        try:
            b = BankPartner.objects.create(
                code=code, name=name or code,
                swift_code=str(data.get('swift_code', ''))[:20],
                api_base_url=str(data.get('api_base_url', ''))[:255],
                api_key=str(data.get('api_key', ''))[:255],
                api_secret=str(data.get('api_secret', ''))[:255],
                webhook_secret=str(data.get('webhook_secret', ''))[:255],
                adapter_class=str(data.get('adapter_class') or 'apps.banking.adapters.mock_adapter.MockBankAdapter')[:100],
                status=str(data.get('status') or 'TESTING')[:20],
            )
        except Exception as e:
            return Response({'success': False, 'error': f'Création impossible : {e}.'}, status=400)
        AuditService.log(user=request.user, action='BANK_CREATED', details={'bank': code})
        return Response({'success': True, 'message': f'Banque {code} ajoutée.', 'code': b.code})
