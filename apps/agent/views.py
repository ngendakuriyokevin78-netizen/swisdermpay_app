"""
Vues API Agent : Cash In / Cash Out.
POST /api/agent/cashin/ — POST /api/agent/cashout/
"""
import logging
from decimal import Decimal
from django.core.exceptions import ValidationError
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from drf_yasg.utils import swagger_auto_schema
from .serializers import CashInSerializer, CashOutSerializer, WithdrawRequestSerializer, WithdrawConfirmSerializer
from .services import process_cashin, process_cashout
from .withdraw_services import request_withdrawal, confirm_withdrawal, cancel_withdrawal
from apps.transactions.serializers import TransactionSerializer

logger = logging.getLogger('apps.agent')


class CashInView(APIView):
    permission_classes = [IsAuthenticated]

    @swagger_auto_schema(request_body=CashInSerializer, operation_summary="Dépôt agent (Cash In)")
    def post(self, request):
        s = CashInSerializer(data=request.data)
        if not s.is_valid():
            return Response({'success': False, 'details': s.errors}, status=400)
        try:
            txn = process_cashin(request.user, s.validated_data['customer_phone'], Decimal(str(s.validated_data['amount'])))
            return Response({'success': True, 'message': 'Dépôt effectué.', 'transaction': TransactionSerializer(txn).data})
        except ValidationError as e:
            return Response({'success': False, 'error': e.message}, status=400)
        except Exception as e:
            logger.exception(e)
            return Response({'success': False, 'error': 'Erreur interne.'}, status=500)


class CashOutView(APIView):
    permission_classes = [IsAuthenticated]

    @swagger_auto_schema(request_body=CashOutSerializer, operation_summary="Retrait agent (Cash Out)")
    def post(self, request):
        s = CashOutSerializer(data=request.data)
        if not s.is_valid():
            return Response({'success': False, 'details': s.errors}, status=400)
        try:
            txn = process_cashout(
                request.user, s.validated_data['customer_phone'],
                Decimal(str(s.validated_data['amount'])), s.validated_data['pin']
            )
            return Response({'success': True, 'message': 'Retrait effectué.', 'transaction': TransactionSerializer(txn).data})
        except ValidationError as e:
            return Response({'success': False, 'error': e.message}, status=400)
        except Exception as e:
            logger.exception(e)
            return Response({'success': False, 'error': 'Erreur interne.'}, status=500)


# ── Retrait initié client (AJOUT SEUL — cashout agent existant inchangé) ─────

class WithdrawRequestView(APIView):
    """POST /api/agent/withdraw-request/ (client) : {amount, pin} -> {code}."""
    permission_classes = [IsAuthenticated]

    def post(self, request):
        from decimal import Decimal as D
        s = WithdrawRequestSerializer(data=request.data)
        if not s.is_valid():
            return Response({'success': False, 'details': s.errors}, status=400)
        try:
            req = request_withdrawal(request.user, D(str(s.validated_data['amount'])),
                                     s.validated_data['pin'],
                                     s.validated_data.get('idempotency_key', ''))
            return Response({'success': True, 'code': req.code,
                             'amount': str(req.amount), 'fee': str(req.fee),
                             'expires_at': req.expires_at,
                             'message': f"Montrez le code {req.code} à l'agent."})
        except ValidationError as e:
            return Response({'success': False, 'error': e.message}, status=400)
        except Exception as e:
            logger.exception(e)
            return Response({'success': False, 'error': 'Erreur interne.'}, status=500)


class WithdrawConfirmView(APIView):
    """POST /api/agent/withdraw-confirm/ (agent) : {code} -> cash remis."""
    permission_classes = [IsAuthenticated]

    def post(self, request):
        s = WithdrawConfirmSerializer(data=request.data)
        if not s.is_valid():
            return Response({'success': False, 'details': s.errors}, status=400)
        try:
            req = confirm_withdrawal(request.user, s.validated_data['code'])
            txn = req.transaction
            return Response({'success': True, 'message': 'Retrait effectué. Remettez le cash.',
                             'transaction': TransactionSerializer(txn).data if txn else None})
        except ValidationError as e:
            return Response({'success': False, 'error': e.message}, status=400)
        except Exception as e:
            logger.exception(e)
            return Response({'success': False, 'error': 'Erreur interne.'}, status=500)


class WithdrawCancelView(APIView):
    """POST /api/agent/withdraw-cancel/ (client) : {code}."""
    permission_classes = [IsAuthenticated]

    def post(self, request):
        s = WithdrawConfirmSerializer(data=request.data)
        if not s.is_valid():
            return Response({'success': False, 'details': s.errors}, status=400)
        try:
            cancel_withdrawal(request.user, s.validated_data['code'])
            return Response({'success': True, 'message': 'Demande annulée.'})
        except ValidationError as e:
            return Response({'success': False, 'error': e.message}, status=400)


class CommissionView(APIView):
    """GET /api/agent/commission/ (agent) : voit sa commission dans son compte."""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        from .commission import get_commission_overview
        if request.user.role != 'AGENT' and not request.user.is_staff:
            return Response({'success': False, 'error': 'Réservé aux agents.'}, status=403)
        return Response({'success': True, **get_commission_overview(request.user)})


class CommissionClaimView(APIView):
    """POST /api/agent/commission/claim/ {amount?} : verse la commission sur son wallet."""
    permission_classes = [IsAuthenticated]

    def post(self, request):
        from decimal import Decimal as D
        from .commission import claim_commission
        if request.user.role != 'AGENT' and not request.user.is_staff:
            return Response({'success': False, 'error': 'Réservé aux agents.'}, status=403)
        try:
            raw = request.data.get('amount') if isinstance(request.data, dict) else None
            claimed, remaining, wallet = claim_commission(request.user, D(str(raw)) if raw else None)
            return Response({'success': True, 'claimed': str(claimed),
                             'commission_balance': str(remaining),
                             'wallet_balance': str(wallet),
                             'message': f"{claimed:,.0f} BIF versés sur votre wallet."})
        except ValidationError as e:
            return Response({'success': False, 'error': e.message}, status=400)
        except Exception as e:
            logger.exception(e)
            return Response({'success': False, 'error': 'Erreur interne.'}, status=500)
