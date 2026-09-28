"""Serializers Boutique (ajout seul)."""
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
    qty = serializers.IntegerField(min_value=1, default=1)


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
    amount = serializers.DecimalField(max_digits=15, decimal_places=2, required=False,
                                      help_text="Requis seulement si QR sans montant (CASHTEL)")
    idempotency_key = serializers.CharField(required=False, allow_blank=True, default='',
                                            help_text="UUID généré par le téléphone, anti double-débit")

    def validate_pin(self, value):
        if not str(value).isdigit():
            raise serializers.ValidationError('PIN numérique.')
        return value
