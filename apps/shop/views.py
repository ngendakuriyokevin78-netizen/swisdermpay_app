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
                          OrderSerializer, ScanPaySerializer, FreePaySerializer, BonusGrantSerializer,
                          PackageSerializer, PackageCreateSerializer, ProductCreateSerializer,
                          OrderPackageSerializer, MerchantPublicSerializer)
from .services import create_order, pay_order_auto, pay_qr_auto, pay_free, grant_client_bonus
from apps.merchant.models import MerchantProfile

logger = logging.getLogger('apps.shop')


class MerchantListView(ListAPIView):
    """GET /api/shop/merchants/ — public pour l'app téléphone (choisir boutique)."""
    permission_classes = [AllowAny]
    serializer_class = MerchantPublicSerializer
    queryset = MerchantProfile.objects.filter(status='ACTIVE').order_by('-is_primary', 'trade_name')
    pagination_class = None


class ProductListView(ListAPIView):
    """GET /api/shop/products/?merchant=Swisderm&search=nom — catalogue téléphone."""
    permission_classes = [AllowAny]
    serializer_class = ProductSerializer
    pagination_class = None

    def get_queryset(self):
        from django.db.models import Q
        qs = Product.objects.filter(status='ACTIVE').select_related('merchant').prefetch_related('images')
        merchant = self.request.query_params.get('merchant')
        if merchant:
            qs = qs.filter(merchant__trade_name__iexact=merchant)
        search = (self.request.query_params.get('search') or '').strip()
        if search:
            qs = qs.filter(Q(name__icontains=search) | Q(sku__icontains=search))
        return qs[:100]


class PackageListView(ListAPIView):
    """GET /api/shop/packages/?merchant=Swisderm — liste select packages (public)."""
    permission_classes = [AllowAny]
    pagination_class = None

    def list(self, request, *args, **kwargs):
        from .models import Package
        qs = Package.objects.filter(status='ACTIVE').select_related('merchant').prefetch_related('items__product')
        merchant = request.query_params.get('merchant')
        if merchant:
            qs = qs.filter(merchant__trade_name__iexact=merchant)
        search = (request.query_params.get('search') or '').strip()
        if search:
            qs = qs.filter(name__icontains=search)
        out = []
        for p in qs[:100]:
            try:
                img = request.build_absolute_uri(p.image.url) if p.image else None
            except Exception:
                img = None
            out.append({'id': str(p.id), 'name': p.name, 'description': p.description,
                        'price': str(p.price), 'stock_quantity': p.stock_quantity, 'status': p.status,
                        'merchant_name': p.merchant.trade_name, 'image_url': img,
                        'items': [{'sku': i.product.sku, 'name': i.product.name, 'qty': i.quantity} for i in p.items.all()]})
        return Response({'success': True, 'results': out})


class ProductImageUploadView(APIView):
    """POST /api/shop/admin/products/<sku>/images/ (multipart image) — ADMIN seul, ajout seul."""
    permission_classes = [IsAuthenticated]

    @swagger_auto_schema(operation_summary="Ajouter une image produit (ADMIN)")
    def post(self, request, sku):
        if request.user.role != 'ADMIN' and not request.user.is_staff:
            return Response({'success': False, 'error': 'Réservé ADMIN.'}, status=403)
        from .models import Product, ProductImage
        try:
            product = Product.objects.get(sku=sku)
        except Product.DoesNotExist:
            return Response({'success': False, 'error': f'Produit introuvable : {sku}.'}, status=404)
        img = request.FILES.get('image')
        if not img:
            return Response({'success': False, 'error': 'Fichier image requis (champ image).'}, status=400)
        try:
            order = ProductImage.objects.filter(product=product).count()
            pi = ProductImage.objects.create(product=product, image=img, sort_order=order)
            url = request.build_absolute_uri(pi.image.url)
            return Response({'success': True, 'message': f'Image ajoutée à {sku}.',
                             'image_url': url, 'total': order + 1})
        except Exception as e:
            logger.exception(e)
            return Response({'success': False, 'error': 'Erreur interne.'}, status=500)


class ProductRegisterView(APIView):
    """POST /api/shop/admin/products/ — ADMIN enregistre un produit Swisderm."""
    permission_classes = [IsAuthenticated]

    @swagger_auto_schema(request_body=ProductCreateSerializer, operation_summary="Enregistrer produit (ADMIN)")
    def post(self, request):
        if request.user.role != 'ADMIN' and not request.user.is_staff:
            return Response({'success': False, 'error': 'Réservé ADMIN.'}, status=403)
        from decimal import Decimal
        s = ProductCreateSerializer(data=request.data)
        if not s.is_valid():
            return Response({'success': False, 'details': s.errors}, status=400)
        try:
            from .services import register_product
            p = register_product(s.validated_data['merchant_code'], s.validated_data['sku'],
                                 s.validated_data['name'], Decimal(str(s.validated_data['price'])),
                                 s.validated_data.get('stock_quantity', 0), s.validated_data.get('description', ''))
            return Response({'success': True, 'message': f"Produit {p.sku} enregistré.", 'sku': p.sku})
        except ValidationError as e:
            return Response({'success': False, 'error': e.message}, status=400)
        except Exception as e:
            logger.exception(e)
            return Response({'success': False, 'error': 'Erreur interne.'}, status=500)


class PackageRegisterView(APIView):
    """POST /api/shop/admin/packages/ — ADMIN enregistre un package avec contenu."""
    permission_classes = [IsAuthenticated]

    @swagger_auto_schema(request_body=PackageCreateSerializer, operation_summary="Enregistrer package (ADMIN)")
    def post(self, request):
        if request.user.role != 'ADMIN' and not request.user.is_staff:
            return Response({'success': False, 'error': 'Réservé ADMIN.'}, status=403)
        from decimal import Decimal
        s = PackageCreateSerializer(data=request.data)
        if not s.is_valid():
            return Response({'success': False, 'details': s.errors}, status=400)
        try:
            from .services import register_package
            pkg = register_package(s.validated_data['merchant_code'], s.validated_data['name'],
                                   Decimal(str(s.validated_data['price'])),
                                   s.validated_data.get('stock_quantity', 0),
                                   s.validated_data.get('description', ''), s.validated_data.get('items', []))
            return Response({'success': True, 'message': f"Package {pkg.name} enregistré.", 'id': str(pkg.id)})
        except ValidationError as e:
            return Response({'success': False, 'error': e.message}, status=400)
        except Exception as e:
            logger.exception(e)
            return Response({'success': False, 'error': 'Erreur interne.'}, status=500)


class OrderPackageView(APIView):
    """POST /api/shop/orders-package/ {package_id, qty} — commande package existant."""
    permission_classes = [IsAuthenticated]

    @swagger_auto_schema(request_body=OrderPackageSerializer, operation_summary="Commander package")
    def post(self, request):
        s = OrderPackageSerializer(data=request.data)
        if not s.is_valid():
            return Response({'success': False, 'details': s.errors}, status=400)
        try:
            from .services import create_order_with_package
            order = create_order_with_package(request.user, s.validated_data.get('merchant_code', ''),
                                              s.validated_data['package_id'], s.validated_data.get('qty', 1))
            return Response({'success': True, 'order': OrderSerializer(order).data})
        except ValidationError as e:
            return Response({'success': False, 'error': e.message}, status=400)
        except Exception as e:
            logger.exception(e)
            return Response({'success': False, 'error': 'Erreur interne.'}, status=500)


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
            from apps.transactions.money import fmt_bif as _bif
            return Response({'success': True, 'message': f"Payé {_bif(order.total)} chez {order.merchant.trade_name}.",
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


class FreePayView(APIView):
    """
    POST /api/shop/free-pay/ {receiver_phone, designation, amount, pin} — AJOUT SEUL.
    Achat/service libre SANS produit enregistré : simple désignation.
    Ancien flux SKU inchangé.
    """
    permission_classes = [IsAuthenticated]

    @swagger_auto_schema(request_body=FreePaySerializer, operation_summary="Achat libre (désignation)")
    def post(self, request):
        from decimal import Decimal
        s = FreePaySerializer(data=request.data)
        if not s.is_valid():
            return Response({'success': False, 'details': s.errors}, status=400)
        try:
            txn = pay_free(
                request.user,
                s.validated_data['receiver_phone'],
                s.validated_data['designation'],
                Decimal(str(s.validated_data['amount'])),
                s.validated_data['pin'],
            )
            from apps.transactions.serializers import TransactionSerializer
            from apps.transactions.money import fmt_bif as _bif2
            return Response({'success': True,
                             'message': f"Payé {_bif2(txn.amount)} : {s.validated_data['designation']}.",
                             'transaction': TransactionSerializer(txn).data})
        except ValidationError as e:
            return Response({'success': False, 'error': e.message}, status=400)
        except Exception as e:
            logger.exception(e)
            return Response({'success': False, 'error': 'Erreur interne.'}, status=500)


class AdminShopStatsView(APIView):
    """
    GET /api/shop/admin-stats/?period=week|month|all — ADMIN seul, AJOUT SEUL.
    Stats boutiques/business pour bonus : tout est enregistré (boutique, désignation,
    client, montants). Agrégation en Python (sans migration, compatible SQLite/PG).
    """
    permission_classes = [IsAuthenticated]

    @swagger_auto_schema(operation_summary="Stats boutiques pour bonus (ADMIN)")
    def get(self, request):
        if request.user.role != 'ADMIN' and not request.user.is_staff:
            return Response({'success': False, 'error': 'Réservé ADMIN.'}, status=403)
        from datetime import timedelta
        from django.utils import timezone
        from apps.transactions.models import Transaction
        from collections import defaultdict
        from decimal import Decimal
        period = (request.query_params.get('period') or 'week').lower()
        days = {'today': 1, 'week': 7, 'month': 30, 'all': 3650}.get(period, 7)
        since = timezone.now() - timedelta(days=days)
        txns = list(Transaction.objects.filter(
            status=Transaction.Status.SUCCESS, created_at__gte=since
        ).select_related('sender', 'receiver').order_by('-created_at')[:5000])
        pays = [t for t in txns if isinstance(t.metadata, dict) and t.metadata.get('kind') == 'MERCHANT_PAY']
        by_biz = defaultdict(lambda: {'total': Decimal('0'), 'nb': 0})
        by_client = defaultdict(lambda: {'total': Decimal('0'), 'nb': 0, 'name': ''})
        by_desig = defaultdict(lambda: {'total': Decimal('0'), 'nb': 0})
        biz_phones = {}
        for t in pays:
            meta = t.metadata or {}
            biz = (meta.get('merchant') or '').strip() or (t.receiver.phone_number if t.receiver else '?')
            desig = (meta.get('designation') or meta.get('order_number') or t.description or '').strip()[:60] or 'Achat'
            amt = t.amount or Decimal('0')
            by_biz[biz]['total'] += amt
            by_biz[biz]['nb'] += 1
            if t.receiver:
                biz_phones[biz] = t.receiver.phone_number
            if t.sender:
                k = t.sender.phone_number
                by_client[k]['total'] += amt
                by_client[k]['nb'] += 1
                by_client[k]['name'] = t.sender.get_full_name()
            by_desig[desig.lower()]['total'] += amt
            by_desig[desig.lower()]['nb'] += 1
        top_biz = sorted([{'business': k, 'phone': biz_phones.get(k, ''), 'total': str(v['total']), 'nb': v['nb']} for k, v in by_biz.items()], key=lambda x: float(x['total']), reverse=True)[:20]
        top_clients = sorted([{'phone': k, 'name': v['name'], 'total': str(v['total']), 'nb': v['nb']} for k, v in by_client.items()], key=lambda x: float(x['total']), reverse=True)[:20]
        top_desig = sorted([{'designation': k, 'total': str(v['total']), 'nb': v['nb']} for k, v in by_desig.items()], key=lambda x: float(x['total']), reverse=True)[:20]
        try:
            merch = [{'business': (m.trade_name or m.company_name), 'revenue': str(m.total_revenue or 0), 'status': m.status} for m in MerchantProfile.objects.order_by('-total_revenue')[:20]]
        except Exception:
            merch = []
        return Response({'success': True, 'period': period, 'days': days,
                         'purchases_count': len(pays),
                         'top_business': top_biz, 'top_clients': top_clients,
                         'top_designations': top_desig, 'merchants_revenue': merch})


class BonusGrantView(APIView):
    """
    POST /api/shop/bonus/grant/ {client_phone, amount, reason} — ADMIN siège seul.
    Crédit bonus/remise frais au gros acheteur. Visible dans son historique.
    """
    permission_classes = [IsAuthenticated]

    @swagger_auto_schema(request_body=BonusGrantSerializer, operation_summary="Accorder bonus client (siège)")
    def post(self, request):
        if request.user.role != 'ADMIN' and not request.user.is_staff:
            return Response({'success': False, 'error': 'Réservé siège Swisderm (ADMIN).'}, status=403)
        from decimal import Decimal
        s = BonusGrantSerializer(data=request.data)
        if not s.is_valid():
            return Response({'success': False, 'details': s.errors}, status=400)
        try:
            txn = grant_client_bonus(
                request.user,
                s.validated_data['client_phone'],
                Decimal(str(s.validated_data['amount'])),
                s.validated_data.get('reason', ''),
            )
            from apps.transactions.serializers import TransactionSerializer
            from apps.transactions.money import fmt_bif as _bif3
            return Response({'success': True,
                             'message': f"Bonus {_bif3(txn.amount)} accordé à {s.validated_data['client_phone']}.",
                             'transaction': TransactionSerializer(txn).data})
        except ValidationError as e:
            return Response({'success': False, 'error': e.message}, status=400)
        except Exception as e:
            logger.exception(e)
            return Response({'success': False, 'error': 'Erreur interne.'}, status=500)
