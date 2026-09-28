"""
Vues API pour les transactions Cash Tel.
- TransferByPhoneView : POST /api/transfer/send/
- TransferByQRView    : POST /api/transfer/qr/
- TransactionListView : GET  /api/transactions/
- FeeGridView         : GET  /api/transfer/fees/
"""
import logging
from decimal import Decimal
from django.core.exceptions import ValidationError
from rest_framework.views import APIView
from rest_framework.generics import ListAPIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from drf_yasg.utils import swagger_auto_schema
from drf_yasg import openapi

from .serializers import (
    TransferByPhoneSerializer, TransferByQRSerializer,
    TransactionSerializer, FeeSerializer
)
from .services import process_transfer, process_qr_transfer, get_user_transactions, calculate_fee, reverse_transfer
from .models import Transaction, Fee

logger = logging.getLogger('apps.transactions')


# ── Transfert par Numéro ──────────────────────────────────────────────────────

class TransferByPhoneView(APIView):
    """
    POST /api/transfer/send/
    Effectue un transfert P2P vers un numéro de téléphone.
    """
    permission_classes = [IsAuthenticated]

    @swagger_auto_schema(
        request_body=TransferByPhoneSerializer,
        responses={
            200: openapi.Response('Transfert réussi', TransactionSerializer),
            400: 'Solde insuffisant / PIN incorrect / Données invalides',
        },
        operation_summary="Transfert par numéro",
        operation_description=(
            "Transfère un montant vers un autre utilisateur Cash Tel par numéro de téléphone.\n\n"
            "Les frais sont calculés automatiquement selon la grille tarifaire."
        )
    )
    def post(self, request):
        serializer = TransferByPhoneSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(
                {'success': False, 'error': 'Données invalides', 'details': serializer.errors},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            txn = process_transfer(
                sender=request.user,
                receiver_phone=serializer.validated_data['receiver_phone'],
                amount=Decimal(str(serializer.validated_data['amount'])),
                pin=serializer.validated_data['pin'],
            )
            return Response({
                'success': True,
                'message': 'Transfert effectué avec succès.',
                'transaction': TransactionSerializer(txn).data,
            })
        except ValidationError as e:
            return Response(
                {'success': False, 'error': e.message},
                status=status.HTTP_400_BAD_REQUEST
            )
        except Exception as e:
            logger.exception(f"Erreur inattendue transfert: {e}")
            return Response(
                {'success': False, 'error': 'Une erreur interne est survenue.'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


# ── Transfert par QR Code ─────────────────────────────────────────────────────

class TransferByQRView(APIView):
    """
    POST /api/transfer/qr/
    Effectue un transfert après scan d'un QR Code Cash Tel.
    """
    permission_classes = [IsAuthenticated]

    @swagger_auto_schema(
        request_body=TransferByQRSerializer,
        responses={
            200: openapi.Response('Transfert QR réussi', TransactionSerializer),
            400: 'QR invalide / PIN incorrect',
        },
        operation_summary="Transfert par QR Code",
        operation_description=(
            "Scanne un QR Code SwisdermPay (format: SWISDERMPAY:wallet_id:phone) et effectue le paiement.\n\n"
            "Le QR de chaque wallet est disponible sur GET /api/wallet/qr/"
        )
    )
    def post(self, request):
        serializer = TransferByQRSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(
                {'success': False, 'error': 'Données invalides', 'details': serializer.errors},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            raw_amount = serializer.validated_data.get('amount')
            txn = process_qr_transfer(
                sender=request.user,
                qr_data=serializer.validated_data['qr_data'],
                amount=Decimal(str(raw_amount)) if raw_amount is not None else None,
                pin=serializer.validated_data['pin'],
            )
            return Response({
                'success': True,
                'message': 'Paiement QR effectué avec succès.',
                'transaction': TransactionSerializer(txn).data,
            })
        except ValidationError as e:
            return Response(
                {'success': False, 'error': e.message},
                status=status.HTTP_400_BAD_REQUEST
            )
        except Exception as e:
            logger.exception(f"Erreur QR transfer: {e}")
            return Response(
                {'success': False, 'error': 'Une erreur interne est survenue.'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


# ── Historique des Transactions ───────────────────────────────────────────────

class TransactionListView(ListAPIView):
    """
    GET /api/transactions/
    Retourne l'historique complet de l'utilisateur connecté.
    Filtrable par type et statut. Paginé par 20.
    """
    permission_classes = [IsAuthenticated]
    serializer_class = TransactionSerializer

    @swagger_auto_schema(
        manual_parameters=[
            openapi.Parameter('type', openapi.IN_QUERY,
                              description='Filtrer par type: TRANSFER, DEPOSIT, WITHDRAWAL, BILL',
                              type=openapi.TYPE_STRING),
            openapi.Parameter('status', openapi.IN_QUERY,
                              description='Filtrer par statut: PENDING, SUCCESS, FAILED',
                              type=openapi.TYPE_STRING),
        ],
        operation_summary="Historique des transactions",
    )
    def get_queryset(self):
        qs = get_user_transactions(self.request.user)

        txn_type = self.request.query_params.get('type')
        txn_status = self.request.query_params.get('status')

        if txn_type:
            qs = qs.filter(transaction_type=txn_type.upper())
        if txn_status:
            qs = qs.filter(status=txn_status.upper())

        return qs


# ── Grille des Frais ──────────────────────────────────────────────────────────

class FeeGridView(ListAPIView):
    """
    GET /api/transfer/fees/
    Retourne la grille tarifaire publique.
    """
    permission_classes = [IsAuthenticated]
    serializer_class = FeeSerializer
    queryset = Fee.objects.filter(is_active=True).order_by('min_amount')
    pagination_class = None

    @swagger_auto_schema(operation_summary="Grille des frais")
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)


# ── Simulation des Frais ──────────────────────────────────────────────────────

class SimulateFeeView(APIView):
    """
    GET /api/transfer/simulate/?amount=5000
    Simule les frais pour un montant donné.
    """
    permission_classes = [IsAuthenticated]

    @swagger_auto_schema(
        manual_parameters=[
            openapi.Parameter('amount', openapi.IN_QUERY,
                              description='Montant en BIF', type=openapi.TYPE_NUMBER, required=True),
        ],
        operation_summary="Simuler les frais",
    )
    def get(self, request):
        amount_str = request.query_params.get('amount')
        try:
            amount = Decimal(amount_str)
            if amount <= 0:
                raise ValueError
        except (TypeError, ValueError):
            return Response(
                {'success': False, 'error': 'Montant invalide.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        fee = calculate_fee(amount)
        return Response({
            'success': True,
            'amount': str(amount),
            'fee': str(fee),
            'total': str(amount + fee),
            'currency': 'BIF',
        })


class ReverseTransferView(APIView):
    """
    POST /api/transfer/reverse/ {reference, reason} — ADMIN seul.
    Restitue le montant au compte d'origine après erreur de numéro.
    """
    permission_classes = [IsAuthenticated]

    def post(self, request):
        if request.user.role != 'ADMIN' and not request.user.is_staff:
            return Response({'success': False, 'error': 'Réservé ADMIN.'}, status=403)
        ref = (request.data.get('reference') or '').strip()
        reason = (request.data.get('reason') or '').strip()
        if not ref:
            return Response({'success': False, 'error': 'Référence requise.'}, status=400)
        try:
            compensation = reverse_transfer(request.user, ref, reason)
            return Response({'success': True,
                             'message': 'Montant restitué au compte d origine (frais non remboursés).',
                             'transaction': TransactionSerializer(compensation).data})
        except ValidationError as e:
            return Response({'success': False, 'error': e.message}, status=400)
        except Exception as e:
            logger.exception(e)
            return Response({'success': False, 'error': 'Erreur interne.'}, status=500)


class AdminAllTransactionsView(ListAPIView):
    """
    GET /api/transactions/all/ — ADMIN seul.
    Toutes les transactions clients + agents avec soldes des deux parties.
    """
    permission_classes = [IsAuthenticated]
    serializer_class = TransactionSerializer

    def get_queryset(self):
        if self.request.user.role != 'ADMIN' and not self.request.user.is_staff:
            return Transaction.objects.none()
        qs = Transaction.objects.select_related('sender', 'receiver').order_by('-created_at')
        ttype = self.request.query_params.get('type')
        phone = self.request.query_params.get('phone')
        if ttype:
            qs = qs.filter(transaction_type=ttype.upper())
        if phone:
            from django.db.models import Q
            qs = qs.filter(Q(sender__phone_number__icontains=phone) |
                           Q(receiver__phone_number__icontains=phone))
        return qs

    def list(self, request, *args, **kwargs):
        if request.user.role != 'ADMIN' and not request.user.is_staff:
            return Response({'success': False, 'error': 'Réservé ADMIN.'}, status=403)
        return super().list(request, *args, **kwargs)
