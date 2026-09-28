"""
Contacts — AJOUT SEUL.
- normalize_phone() : +257XXXXXXXX compatible carnets Android/iPhone.
- POST /api/auth/contacts/resolve/ {phones:[...]} -> noms des inscrits.
- GET  /api/auth/contacts/recent/ -> 10 derniers destinataires de l'expéditeur.
Aucune modification de User / Transaction existants.
"""
import re
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from drf_yasg.utils import swagger_auto_schema
from rest_framework import serializers
from cashtel.throttles import StrictUserThrottle


def normalize_phone(raw: str) -> str:
    p = (raw or '').strip().replace(' ', '').replace('-', '').replace('(', '').replace(')', '')
    if p.startswith('+'):
        return p
    if p.startswith('00257'):
        return '+' + p[2:]
    if p.startswith('257') and len(p) >= 11:
        return '+' + p
    digits = re.sub(r'\D', '', p)
    if len(digits) == 8:  # ex 62000001 -> +25762000001
        return '+257' + digits
    if digits.startswith('257') and len(digits) >= 11:
        return '+' + digits
    return p or raw


class ResolveSerializer(serializers.Serializer):
    phones = serializers.ListField(child=serializers.CharField(max_length=30), max_length=30, min_length=1)


class ContactResolveView(APIView):
    permission_classes = [IsAuthenticated]
    throttle_classes = [StrictUserThrottle]

    @swagger_auto_schema(request_body=ResolveSerializer, operation_summary="Résoudre noms des numéros")
    def post(self, request):
        from apps.authentication.models import User
        s = ResolveSerializer(data=request.data)
        if not s.is_valid():
            return Response({'success': False, 'details': s.errors}, status=400)
        out = []
        for raw in s.validated_data['phones'][:50]:
            norm = normalize_phone(raw)
            try:
                u = User.objects.get(phone_number=norm, is_active=True)
                out.append({'phone': norm, 'input': raw, 'registered': True,
                            'full_name': u.get_full_name(), 'role': u.role})
            except User.DoesNotExist:
                out.append({'phone': norm, 'input': raw, 'registered': False,
                            'full_name': None, 'role': None})
        return Response({'success': True, 'contacts': out})


class RecentContactsView(APIView):
    permission_classes = [IsAuthenticated]

    @swagger_auto_schema(operation_summary="Derniers destinataires (avec noms)")
    def get(self, request):
        from apps.transactions.models import Transaction
        txns = Transaction.objects.filter(
            sender=request.user,
            transaction_type=Transaction.TransactionType.TRANSFER,
        ).select_related('receiver').order_by('-created_at')[:50]
        seen, out = set(), []
        for t in txns:
            if not t.receiver:
                continue
            ph = t.receiver.phone_number
            if ph in seen:
                continue
            seen.add(ph)
            out.append({'phone': ph, 'full_name': t.receiver.get_full_name()})
            if len(out) >= 10:
                break
        return Response({'success': True, 'recents': out})


class LookupOneView(APIView):
    """GET /api/auth/contacts/lookup/?phone=+257... -> nom si inscrit (pour affichage live)."""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        from apps.authentication.models import User
        raw = request.query_params.get('phone', '')
        norm = normalize_phone(raw)
        try:
            u = User.objects.get(phone_number=norm, is_active=True)
            return Response({'success': True, 'phone': norm, 'registered': True,
                             'full_name': u.get_full_name()})
        except User.DoesNotExist:
            return Response({'success': True, 'phone': norm, 'registered': False, 'full_name': None})


class ImportSerializer(serializers.Serializer):
    """Carnet du téléphone : [{name, phones:[...]}] — 200 max, sans stockage serveur."""
    contacts = serializers.ListField(child=serializers.DictField(), max_length=200)


class ContactImportView(APIView):
    """
    POST /api/auth/contacts/import/
    Importe le carnet (nom local + numéros) et renvoie la correspondance Cash Tel.
    Sans migration : rien stocké en base, traitement à la volée.
    """
    permission_classes = [IsAuthenticated]
    throttle_classes = [StrictUserThrottle]

    @swagger_auto_schema(request_body=ImportSerializer, operation_summary="Importer carnet + correspondance")
    def post(self, request):
        from apps.authentication.models import User
        s = ImportSerializer(data=request.data)
        if not s.is_valid():
            return Response({'success': False, 'details': s.errors}, status=400)
        out = []
        for entry in s.validated_data['contacts'][:200]:
            local_name = str(entry.get('name') or entry.get('display_name') or '').strip()[:100]
            raw_phones = entry.get('phones') or entry.get('tel') or []
            if isinstance(raw_phones, str):
                raw_phones = [raw_phones]
            for raw in (raw_phones or [])[:5]:
                norm = normalize_phone(str(raw))
                if not norm or len(norm) < 8:
                    continue
                try:
                    u = User.objects.get(phone_number=norm, is_active=True)
                    out.append({'local_name': local_name, 'phone': norm,
                                'registered': True, 'cashTel_name': u.get_full_name()})
                except User.DoesNotExist:
                    out.append({'local_name': local_name, 'phone': norm,
                                'registered': False, 'cashTel_name': None})
                if len(out) >= 300:
                    break
        registered = sum(1 for c in out if c['registered'])
        return Response({'success': True, 'total': len(out),
                         'registered': registered, 'contacts': out})
