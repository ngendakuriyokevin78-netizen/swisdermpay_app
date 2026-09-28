"""Vues interop (ajout seul)."""
import logging
from decimal import Decimal
from django.core.exceptions import ValidationError
from rest_framework.views import APIView
from rest_framework.generics import ListAPIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, AllowAny
from .models import ExternalProvider, ExternalTransfer
from .serializers import (ProviderSerializer, ExternalTransferSerializer,
                          InteropSendSerializer, InteropReceiveSerializer)
from .services import interop_send, interop_receive, interop_webhook

logger = logging.getLogger('apps.interop.views')


class ProviderListView(ListAPIView):
    """GET /api/interop/providers/ — opérateurs en collaboration."""
    permission_classes = [IsAuthenticated]
    serializer_class = ProviderSerializer
    queryset = ExternalProvider.objects.exclude(status='INACTIVE').order_by('name')
    pagination_class = None


class InteropSendView(APIView):
    """POST /api/interop/send/ {provider_code, external_phone, amount, pin}."""
    permission_classes = [IsAuthenticated]

    def post(self, request):
        s = InteropSendSerializer(data=request.data)
        if not s.is_valid():
            return Response({'success': False, 'details': s.errors}, status=400)
        try:
            from django.contrib.auth import get_user_model as _gum
            agent = None
            if s.validated_data.get('agent_phone'):
                try:
                    agent = _gum().objects.get(phone_number=s.validated_data['agent_phone'])
                except Exception:
                    return Response({'success': False, 'error': 'Agent facilitateur introuvable.'}, status=400)
            t = interop_send(request.user, s.validated_data['provider_code'],
                             s.validated_data['external_phone'],
                             Decimal(str(s.validated_data['amount'])),
                             s.validated_data['pin'], agent=agent)
            return Response({'success': True, 'transfer': ExternalTransferSerializer(t).data})
        except ValidationError as e:
            return Response({'success': False, 'error': e.message}, status=400)
        except Exception as e:
            logger.exception(e)
            return Response({'success': False, 'error': 'Erreur interne.'}, status=500)


class InteropReceiveView(APIView):
    """POST /api/interop/receive/ {provider_code, external_phone, amount}."""
    permission_classes = [IsAuthenticated]

    def post(self, request):
        s = InteropReceiveSerializer(data=request.data)
        if not s.is_valid():
            return Response({'success': False, 'details': s.errors}, status=400)
        try:
            t = interop_receive(request.user, s.validated_data['provider_code'],
                                s.validated_data['external_phone'],
                                Decimal(str(s.validated_data['amount'])))
            return Response({'success': True, 'transfer': ExternalTransferSerializer(t).data})
        except ValidationError as e:
            return Response({'success': False, 'error': e.message}, status=400)
        except Exception as e:
            logger.exception(e)
            return Response({'success': False, 'error': 'Erreur interne.'}, status=500)


class MyInteropView(ListAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = ExternalTransferSerializer
    pagination_class = None

    def get_queryset(self):
        return ExternalTransfer.objects.filter(user=self.request.user).order_by('-initiated_at')[:50]


class InteropWebhookView(APIView):
    """POST /api/interop/webhooks/<provider_code>/ — appelé par l'opérateur."""
    permission_classes = [AllowAny]
    authentication_classes = []

    def post(self, request, provider_code):
        try:
            t = interop_webhook(provider_code, request.data, request.body,
                                request.headers.get('X-Signature', ''))
            return Response({'success': True, 'status': t.status})
        except ValidationError as e:
            return Response({'success': False, 'error': e.message}, status=400)


class SettlementReportView(APIView):
    """GET /api/interop/settlement/?year=2026&month=9 — rapport mensuel par opérateur."""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        from django.utils import timezone as tz
        from .services import settlement_report
        now = tz.now()
        try:
            year = int(request.query_params.get('year', now.year))
            month = int(request.query_params.get('month', now.month))
        except ValueError:
            return Response({'success': False, 'error': 'Mois invalide.'}, status=400)
        return Response({'success': True, 'year': year, 'month': month,
                         'rows': settlement_report(year, month)})


class SettlementMarkView(APIView):
    """POST /api/interop/settlement/mark/ {provider_code, year, month} — ADMIN après virement réel."""
    permission_classes = [IsAuthenticated]

    def post(self, request):
        from .services import mark_settled
        if request.user.role != 'ADMIN' and not request.user.is_staff:
            return Response({'success': False, 'error': 'Réservé ADMIN.'}, status=403)
        try:
            n = mark_settled(request.data.get('provider_code', ''),
                             int(request.data.get('year', 0)), int(request.data.get('month', 0)))
            return Response({'success': True, 'marked': n,
                             'message': f"{n} transfert(s) marqué(s) reversé(s)."})
        except (ValueError, TypeError):
            return Response({'success': False, 'error': 'Paramètres invalides.'}, status=400)
