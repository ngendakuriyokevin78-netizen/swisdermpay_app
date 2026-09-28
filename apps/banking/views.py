"""Vues bancaires (ajout seul)."""
import logging
from decimal import Decimal
from django.core.exceptions import ValidationError
from rest_framework.views import APIView
from rest_framework.generics import ListAPIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, AllowAny
from .models import BankPartner, BankTransfer
from .serializers import (BankPartnerSerializer, BankTransferSerializer,
                          BankDepositSerializer, BankWithdrawSerializer)
from .services import bank_deposit, bank_withdraw, bank_webhook

logger = logging.getLogger('apps.banking.views')


class BankListView(ListAPIView):
    """GET /api/banking/banks/ — banques en collaboration."""
    permission_classes = [IsAuthenticated]
    serializer_class = BankPartnerSerializer
    queryset = BankPartner.objects.exclude(status='INACTIVE').order_by('-is_default', 'name')
    pagination_class = None


class BankDepositView(APIView):
    """POST /api/banking/deposit/ {bank_code, account_number, amount}."""
    permission_classes = [IsAuthenticated]

    def post(self, request):
        s = BankDepositSerializer(data=request.data)
        if not s.is_valid():
            return Response({'success': False, 'details': s.errors}, status=400)
        try:
            t = bank_deposit(request.user, s.validated_data['bank_code'],
                             s.validated_data['account_number'],
                             Decimal(str(s.validated_data['amount'])))
            return Response({'success': True, 'transfer': BankTransferSerializer(t).data})
        except ValidationError as e:
            return Response({'success': False, 'error': e.message}, status=400)
        except Exception as e:
            logger.exception(e)
            return Response({'success': False, 'error': 'Erreur interne.'}, status=500)


class BankWithdrawView(APIView):
    """POST /api/banking/withdraw/ {bank_code, account_number, amount, pin}."""
    permission_classes = [IsAuthenticated]

    def post(self, request):
        s = BankWithdrawSerializer(data=request.data)
        if not s.is_valid():
            return Response({'success': False, 'details': s.errors}, status=400)
        try:
            t = bank_withdraw(request.user, s.validated_data['bank_code'],
                              s.validated_data['account_number'],
                              Decimal(str(s.validated_data['amount'])),
                              s.validated_data['pin'])
            return Response({'success': True, 'transfer': BankTransferSerializer(t).data})
        except ValidationError as e:
            return Response({'success': False, 'error': e.message}, status=400)
        except Exception as e:
            logger.exception(e)
            return Response({'success': False, 'error': 'Erreur interne.'}, status=500)


class MyBankTransfersView(ListAPIView):
    """GET /api/banking/my-transfers/."""
    permission_classes = [IsAuthenticated]
    serializer_class = BankTransferSerializer
    pagination_class = None

    def get_queryset(self):
        return BankTransfer.objects.filter(user=self.request.user).order_by('-initiated_at')[:50]


class BankWebhookView(APIView):
    """POST /api/banking/webhooks/<bank_code>/ — appelé par la banque."""
    permission_classes = [AllowAny]
    authentication_classes = []

    def post(self, request, bank_code):
        try:
            sig = request.headers.get('X-Signature', '')
            t = bank_webhook(bank_code, request.data, request.body, sig)
            return Response({'success': True, 'status': t.status})
        except ValidationError as e:
            return Response({'success': False, 'error': e.message}, status=400)


class FloatStatusView(APIView):
    """GET /api/banking/float/ — total e-money vs plafond + SOLDE BANQUE (tout contrôle)."""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        from .float_guard import float_status
        from .models import BankFloat, BankPartner
        from .factory import get_adapter
        from django.db.models import Sum
        from apps.wallet.models import Wallet
        st = float_status()
        # Détail par rôle (ajout seul : total clients / agents / admin)
        try:
            by_role = dict(Wallet.objects.values('user__role').annotate(s=Sum('balance')).values_list('user__role', 's'))
            st['total_clients'] = str(by_role.get('USER') or 0)
            st['total_agents'] = str(by_role.get('AGENT') or 0)
            st['total_admins'] = str(by_role.get('ADMIN') or 0)
        except Exception:
            pass
        plafonds = []
        for f in BankFloat.objects.select_related('bank'):
            solde_banque = ''
            try:
                info = get_adapter(f.bank).get_balance('*')
                solde_banque = str(info.available_balance)
            except Exception as e:
                logger.warning(f"Solde banque {f.bank.code} illisible: {e}")
            plafonds.append({'bank': f.bank.code, 'ceiling': str(f.ceiling),
                             'solde_banque': solde_banque})
        st['plafonds'] = plafonds
        st['banques'] = [{'code': b.code, 'name': b.name, 'is_default': b.is_default}
                         for b in BankPartner.objects.exclude(status='INACTIVE')]
        st['success'] = True
        return Response(st)


class FloatSetView(APIView):
    """POST /api/banking/float/set/ {bank_code, ceiling} — ADMIN seul."""
    permission_classes = [IsAuthenticated]

    def post(self, request):
        from decimal import Decimal as D
        from .models import BankPartner, BankFloat
        if request.user.role != 'ADMIN' and not request.user.is_staff:
            return Response({'success': False, 'error': 'Réservé ADMIN.'}, status=403)
        try:
            bank = BankPartner.objects.get(code__iexact=request.data.get('bank_code', 'CRDB'))
            ceiling = D(str(request.data.get('ceiling', '0')))
            if ceiling < 0:
                raise ValidationError("Plafond invalide.")
            from .float_guard import get_total_emoney
            if ceiling < get_total_emoney():
                return Response({'success': False,
                                 'error': f"Plafond {ceiling:,.0f} inférieur au total émis {get_total_emoney():,.0f}."},
                                status=400)
            f, _ = BankFloat.objects.update_or_create(
                bank=bank, defaults={'ceiling': ceiling, 'updated_by': request.user,
                                     'notes': request.data.get('notes', '')})
            return Response({'success': True, 'bank': bank.code, 'ceiling': str(f.ceiling)})
        except BankPartner.DoesNotExist:
            return Response({'success': False, 'error': 'Banque inconnue.'}, status=400)
        except ValidationError as e:
            return Response({'success': False, 'error': e.message}, status=400)
