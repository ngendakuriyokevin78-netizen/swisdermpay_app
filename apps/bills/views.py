"""Vues API Bills."""
import logging
from decimal import Decimal
from django.core.exceptions import ValidationError
from rest_framework.views import APIView
from rest_framework.generics import ListAPIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from drf_yasg.utils import swagger_auto_schema
from .models import Biller
from .serializers import BillerSerializer, PayBillSerializer
from .services import pay_bill
from apps.transactions.serializers import TransactionSerializer

logger = logging.getLogger('apps.bills')


class BillerListView(ListAPIView):
    """GET /api/bills/billers/ — liste fournisseurs."""
    permission_classes = [IsAuthenticated]
    serializer_class = BillerSerializer
    queryset = Biller.objects.filter(is_active=True)
    pagination_class = None


class PayBillView(APIView):
    """POST /api/bills/pay/ — paie une facture."""
    permission_classes = [IsAuthenticated]

    @swagger_auto_schema(request_body=PayBillSerializer, operation_summary="Payer facture")
    def post(self, request):
        s = PayBillSerializer(data=request.data)
        if not s.is_valid():
            return Response({'success': False, 'details': s.errors}, status=400)
        try:
            txn = pay_bill(
                request.user, s.validated_data['biller_code'],
                s.validated_data['reference_number'],
                Decimal(str(s.validated_data['amount'])), s.validated_data['pin']
            )
            return Response({'success': True, 'transaction': TransactionSerializer(txn).data})
        except ValidationError as e:
            return Response({'success': False, 'error': e.message}, status=400)
        except Exception as e:
            logger.exception(e)
            return Response({'success': False, 'error': 'Erreur interne.'}, status=500)
