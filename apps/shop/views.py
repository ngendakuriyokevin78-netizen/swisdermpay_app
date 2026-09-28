"""Vues Boutique : catalogue + commande + SCAN & PAIEMENT AUTO (ajout seul)."""
import logging
from decimal import Decimal
from django.core.exceptions import ValidationError
from rest_framework.views import APIView
from rest_framework.generics import ListAPIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, AllowAny
from drf_yasg.utils import swagger_auto_schema

from .models import Product, ProductCategory, Order
from .serializers import (ProductSerializer, ProductCategorySerializer, OrderCreateSerializer,
                          OrderSerializer, ScanPaySerializer, MerchantPublicSerializer)
from .services import create_order, pay_order_auto, pay_qr_auto
from apps.merchant.models import MerchantProfile

logger = logging.getLogger('apps.shop')


class MerchantListView(ListAPIView):
    """GET /api/shop/merchants/ — public pour l'app téléphone (choisir boutique)."""
    permission_classes = [AllowAny]
    serializer_class = MerchantPublicSerializer
    queryset = MerchantProfile.objects.filter(status='ACTIVE').order_by('-is_primary', 'trade_name')
    pagination_class = None


class ProductListView(ListAPIView):
    """GET /api/shop/products/?merchant=Swisderm — catalogue téléphone."""
    permission_classes = [AllowAny]
    serializer_class = ProductSerializer
    pagination_class = None

    def get_queryset(self):
        qs = Product.objects.filter(status='ACTIVE').select_related('merchant')
        merchant = self.request.query_params.get('merchant')
        if merchant:
            qs = qs.filter(merchant__trade_name__iexact=merchant)
        return qs[:100]


class OrderCreateView(APIView):
    """POST /api/shop/orders/ — crée commande PENDING (le QR est retourné pour payer)."""
    permission_classes = [IsAuthenticated]

    @swagger_auto_schema(request_body=OrderCreateSerializer, operation_summary="Créer commande Swisderm")
    def post(self, request):
        s = OrderCreateSerializer(data=request.data)
        if not s.is_valid():
            return Response({'success': False, 'details': s.errors}, status=400)
        try:
            order = create_order(request.user, s.validated_data['merchant_code'],
                                 s.validated_data['items'],
                                 s.validated_data.get('delivery_address', ''),
                                 s.validated_data.get('delivery_phone', ''),
                                 s.validated_data.get('notes', ''))
            return Response({'success': True, 'order': OrderSerializer(order).data})
        except ValidationError as e:
            return Response({'success': False, 'error': e.message}, status=400)
        except Exception as e:
            logger.exception(e)
            return Response({'success': False, 'error': 'Erreur interne.'}, status=500)


class ScanPayView(APIView):
    """
    POST /api/shop/scan-pay/ — LE TRANSFERT AUTOMATIQUE téléphone.
    Body : {qr_data, pin, amount?, idempotency_key?}
    Le client scanne en rayon/caisse -> montant auto -> 1 appel -> débité/crédité.
    """
    permission_classes = [IsAuthenticated]

    @swagger_auto_schema(request_body=ScanPaySerializer, operation_summary="Scanner & payer (auto)")
    def post(self, request):
        s = ScanPaySerializer(data=request.data)
        if not s.is_valid():
            return Response({'success': False, 'details': s.errors}, status=400)
        try:
            result = pay_qr_auto(
                request.user,
                s.validated_data['qr_data'],
                s.validated_data['pin'],
                s.validated_data.get('amount'),
                s.validated_data.get('idempotency_key', ''),
            )
            if result['kind'] == 'P2P':
                from apps.transactions.serializers import TransactionSerializer
                return Response({'success': True, 'message': 'Transfert effectué.',
                                 'transaction': TransactionSerializer(result['transaction']).data})
            order = result['order']
            return Response({'success': True, 'message': f"Payé {order.total:,.0f} BIF chez {order.merchant.trade_name}.",
                             'order': OrderSerializer(order).data})
        except ValidationError as e:
            return Response({'success': False, 'error': e.message}, status=400)
        except Exception as e:
            logger.exception(e)
            return Response({'success': False, 'error': 'Erreur interne.'}, status=500)


class MyOrdersView(ListAPIView):
    """GET /api/shop/my-orders/ — historique achats du téléphone."""
    permission_classes = [IsAuthenticated]
    serializer_class = OrderSerializer
    pagination_class = None

    def get_queryset(self):
        return Order.objects.filter(customer=self.request.user).prefetch_related(
            'items__product').order_by('-created_at')[:50]
