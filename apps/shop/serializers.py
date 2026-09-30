"""Serializers Boutique (ajout seul)."""
from decimal import Decimal
from rest_framework import serializers
from .models import Product, ProductCategory, Order, OrderItem
from apps.merchant.models import MerchantProfile


class ProductCategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = ProductCategory
        fields = ['id', 'name', 'slug', 'description', 'is_active']


class ProductSerializer(serializers.ModelSerializer):
    merchant_name = serializers.CharField(source='merchant.trade_name', read_only=True)
    qr_data = serializers.SerializerMethodField()

    class Meta:
        model = Product
        fields = ['id', 'sku', 'name', 'description', 'price', 'stock_quantity',
                  'status', 'merchant', 'merchant_name', 'category', 'qr_data']

    def get_qr_data(self, obj):
        code = str(obj.merchant_id)
        return f"SWISDERM:{code}:{obj.sku}:1"


class MerchantPublicSerializer(serializers.ModelSerializer):
    class Meta:
        model = MerchantProfile
        fields = ['id', 'company_name', 'trade_name', 'sector', 'status', 'is_primary']


class OrderItemInputSerializer(serializers.Serializer):
    sku = serializers.CharField()
    qty = serializers.DecimalField(max_digits=15, decimal_places=3, min_value=Decimal('0.001'), default=1)


class OrderCreateSerializer(serializers.Serializer):
    merchant_code = serializers.CharField(help_text="trade_name ou id marchand, ex: Swisderm")
    items = OrderItemInputSerializer(many=True)
    delivery_address = serializers.CharField(required=False, allow_blank=True, default='')
    delivery_phone = serializers.CharField(required=False, allow_blank=True, default='')
    notes = serializers.CharField(required=False, allow_blank=True, default='')


class OrderSerializer(serializers.ModelSerializer):
    items = serializers.SerializerMethodField()
    merchant_name = serializers.CharField(source='merchant.trade_name', read_only=True)
    qr_data = serializers.SerializerMethodField()

    class Meta:
        model = Order
        fields = ['order_number', 'merchant', 'merchant_name', 'subtotal', 'fee',
                  'total', 'status', 'items', 'qr_data', 'created_at', 'paid_at']

    def get_items(self, obj):
        return [{'sku': i.product.sku, 'name': i.product.name,
                 'qty': i.quantity, 'unit_price': str(i.unit_price),
                 'total': str(i.total_price)} for i in obj.items.all()]

    def get_qr_data(self, obj):
        return f"SWISDERM:{obj.merchant_id}:{obj.order_number}"


class ScanPaySerializer(serializers.Serializer):
    """Entrée unique du bouton Scan téléphone : QR + PIN + anti double-clic."""
    qr_data = serializers.CharField(help_text="Chaîne QR scannée : SWISDERM:... ou SWISDERMPAY:...")
    pin = serializers.CharField(min_length=4, max_length=4, write_only=True)
    amount = serializers.DecimalField(max_digits=18, decimal_places=3, required=False,
                                      help_text="Requis seulement si QR sans montant (CASHTEL)")
    idempotency_key = serializers.CharField(required=False, allow_blank=True, default='',
                                            help_text="UUID généré par le téléphone, anti double-débit")

    def validate_pin(self, value):
        if not str(value).isdigit():
            raise serializers.ValidationError('PIN numérique.')
        return value


class FreePaySerializer(serializers.Serializer):
    """Achat libre SANS catalogue : designation + montant + destinataire."""
    receiver_phone = serializers.CharField(help_text="Numéro marchand / prestataire / personne +257...")
    designation = serializers.CharField(max_length=200, help_text="Ex : Coiffure, Transport, Paiement service")
    amount = serializers.DecimalField(max_digits=18, decimal_places=3)
    pin = serializers.CharField(min_length=4, max_length=4, write_only=True)

    def validate_pin(self, value):
        if not str(value).isdigit() or len(str(value)) != 4:
            raise serializers.ValidationError('Code transfert 4 chiffres.')
        return value

    def validate_designation(self, value):
        v = (value or '').strip()
        if len(v) < 3:
            raise serializers.ValidationError('Désignation trop courte (3 lettres min).')
        return v


class BonusGrantSerializer(serializers.Serializer):
    """Bonus siège Swisderm pour gros acheteurs : crédit remise frais."""
    client_phone = serializers.CharField()
    amount = serializers.DecimalField(max_digits=18, decimal_places=3)
    reason = serializers.CharField(max_length=200, required=False, allow_blank=True, default='Bonus gros acheteur / remise frais')


class PackageItemSerializer(serializers.Serializer):
    sku = serializers.CharField()
    qty = serializers.DecimalField(max_digits=15, decimal_places=3, min_value=Decimal('0.001'), default=1)


class PackageSerializer(serializers.Serializer):
    """Lecture package pour liste select téléphone."""
    id = serializers.CharField(read_only=True)
    name = serializers.CharField(read_only=True)
    description = serializers.CharField(read_only=True)
    price = serializers.CharField(read_only=True)
    stock_quantity = serializers.DecimalField(max_digits=15, decimal_places=3, read_only=True)
    status = serializers.CharField(read_only=True)
    merchant_name = serializers.CharField(read_only=True)
    items = serializers.ListField(read_only=True)


class PackageCreateSerializer(serializers.Serializer):
    """Enregistrement package par ADMIN : nom + prix + contenu [{sku, qty}] + stock."""
    merchant_code = serializers.CharField(help_text="trade_name ou id, ex: Swisderm")
    name = serializers.CharField(max_length=200)
    description = serializers.CharField(required=False, allow_blank=True, default='')
    price = serializers.DecimalField(max_digits=18, decimal_places=3)
    stock_quantity = serializers.DecimalField(max_digits=15, decimal_places=3, min_value=0, default=0)
    items = PackageItemSerializer(many=True, required=False, default=list)


class ProductCreateSerializer(serializers.Serializer):
    """Enregistrement produit Swisderm par ADMIN."""
    merchant_code = serializers.CharField()
    sku = serializers.CharField(max_length=50)
    name = serializers.CharField(max_length=200)
    description = serializers.CharField(required=False, allow_blank=True, default='')
    price = serializers.DecimalField(max_digits=18, decimal_places=3)
    stock_quantity = serializers.DecimalField(max_digits=15, decimal_places=3, min_value=0, default=0)


class OrderPackageSerializer(serializers.Serializer):
    """Commande d'un package existant : même ligne produit + package."""
    merchant_code = serializers.CharField(required=False, allow_blank=True, default='')
    package_id = serializers.CharField()
    qty = serializers.DecimalField(max_digits=15, decimal_places=3, min_value=Decimal('0.001'), default=1)
