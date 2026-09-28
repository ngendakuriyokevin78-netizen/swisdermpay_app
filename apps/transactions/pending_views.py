"""
Vues circuit EN ATTENTE — AJOUT SEUL.
Routes internet (JWT) pour l'expéditeur uniquement :
- POST /api/transfer/pending/create/   {receiver_phone, amount} -> PENDING, sans PIN, sans débit
- GET  /api/transfer/pending/list/     -> toutes ses lignes PENDING (plusieurs possibles)
- POST /api/transfer/pending/validate/ {reference, pin} -> SUCCESS + débit réel
- POST /api/transfer/pending/modify/   {reference, receiver_phone?, amount?}
- POST /api/transfer/pending/cancel/   {reference, reason?}
Le transfert automatique QR (POST /api/transfer/qr/ et /api/shop/scan-pay/)
reste inchangé = immédiat SUCCESS.
"""
import logging
from decimal import Decimal
from django.core.exceptions import ValidationError
from cashtel.throttles import StrictUserThrottle
from rest_framework.views import APIView
from rest_framework.generics import ListAPIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from drf_yasg.utils import swagger_auto_schema

from .serializers import TransactionSerializer
from .pending_serializers import (
    PendingCreateSerializer, PendingValidateSerializer,
    PendingModifySerializer, PendingCancelSerializer,
)
from .pending_services import (
    create_pending_transfer, list_pending_transfers,
    validate_pending_transfer, modify_pending_transfer,
    cancel_pending_transfer,
)

logger = logging.getLogger('apps.transactions.pending')


class PendingCreateView(APIView):
    permission_classes = [IsAuthenticated]

    @swagger_auto_schema(request_body=PendingCreateSerializer,
                         operation_summary="Créer transfert en attente (sans PIN, sans débit)")
    def post(self, request):
        s = PendingCreateSerializer(data=request.data)
        if not s.is_valid():
            return Response({'success': False, 'error': 'Données invalides',
                             'details': s.errors}, status=400)
        try:
            txn = create_pending_transfer(
                sender=request.user,
                receiver_phone=s.validated_data['receiver_phone'],
                amount=Decimal(str(s.validated_data['amount'])),
            )
            return Response({'success': True,
                             'message': 'Transfert mis en attente. Vérifiez montant et numéro puis validez.',
                             'transaction': TransactionSerializer(txn).data})
        except ValidationError as e:
            return Response({'success': False, 'error': e.message}, status=400)
        except Exception as e:
            logger.exception(e)
            return Response({'success': False, 'error': 'Erreur interne.'}, status=500)


class PendingListView(ListAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = TransactionSerializer
    pagination_class = None

    @swagger_auto_schema(operation_summary="Mes transferts en attente (plusieurs lignes)")
    def get_queryset(self):
        return list_pending_transfers(self.request.user)


class PendingValidateView(APIView):
    permission_classes = [IsAuthenticated]
    throttle_classes = [StrictUserThrottle]

    @swagger_auto_schema(request_body=PendingValidateSerializer,
                         operation_summary="Valider une ligne en attente (PIN + débit réel)")
    def post(self, request):
        s = PendingValidateSerializer(data=request.data)
        if not s.is_valid():
            return Response({'success': False, 'details': s.errors}, status=400)
        try:
            txn = validate_pending_transfer(
                sender=request.user,
                reference=s.validated_data['reference'],
                pin=s.validated_data['pin'],
            )
            return Response({'success': True, 'message': 'Transfert validé et envoyé.',
                             'transaction': TransactionSerializer(txn).data})
        except ValidationError as e:
            return Response({'success': False, 'error': e.message}, status=400)
        except Exception as e:
            logger.exception(e)
            return Response({'success': False, 'error': 'Erreur interne.'}, status=500)


class PendingModifyView(APIView):
    permission_classes = [IsAuthenticated]

    @swagger_auto_schema(request_body=PendingModifySerializer,
                         operation_summary="Modifier une ligne en attente (montant / numéro)")
    def post(self, request):
        s = PendingModifySerializer(data=request.data)
        if not s.is_valid():
            return Response({'success': False, 'details': s.errors}, status=400)
        try:
            txn = modify_pending_transfer(
                sender=request.user,
                reference=s.validated_data['reference'],
                receiver_phone=s.validated_data.get('receiver_phone') or None,
                amount=s.validated_data.get('amount'),
            )
            return Response({'success': True, 'message': 'Ligne en attente modifiée.',
                             'transaction': TransactionSerializer(txn).data})
        except ValidationError as e:
            return Response({'success': False, 'error': e.message}, status=400)
        except Exception as e:
            logger.exception(e)
            return Response({'success': False, 'error': 'Erreur interne.'}, status=500)


class PendingCancelView(APIView):
    permission_classes = [IsAuthenticated]

    @swagger_auto_schema(request_body=PendingCancelSerializer,
                         operation_summary="Annuler une ligne en attente (sans débit)")
    def post(self, request):
        s = PendingCancelSerializer(data=request.data)
        if not s.is_valid():
            return Response({'success': False, 'details': s.errors}, status=400)
        try:
            txn = cancel_pending_transfer(
                sender=request.user,
                reference=s.validated_data['reference'],
                reason=s.validated_data.get('reason', ''),
            )
            return Response({'success': True, 'message': 'Transfert en attente annulé.',
                             'transaction': TransactionSerializer(txn).data})
        except ValidationError as e:
            return Response({'success': False, 'error': e.message}, status=400)
        except Exception as e:
            logger.exception(e)
            return Response({'success': False, 'error': 'Erreur interne.'}, status=500)
