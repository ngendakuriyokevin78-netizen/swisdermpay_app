"""
Modèles E-Commerce Cash Tel.
- ProductCategory : catégories de produits (Soins visage, Corps, etc.)
- Product : produit Swisderm (ou partenaire)
- Order : commande client
- OrderItem : ligne de commande
"""
import uuid
from django.db import models
from django.conf import settings
from apps.transactions.money import fmt_bif as _b


# ── Catégories Produits ───────────────────────────────────────────────────────

class ProductCategory(models.Model):
    """Catégorie de produits cosmétiques Swisderm."""

    name = models.CharField(max_length=100, unique=True, verbose_name='Nom')
    slug = models.SlugField(max_length=100, unique=True)
    description = models.TextField(blank=True, verbose_name='Description')
    image = models.ImageField(
        upload_to='categories/', blank=True, null=True,
        verbose_name='Image'
    )
    is_active = models.BooleanField(default=True, verbose_name='Active')
    sort_order = models.PositiveSmallIntegerField(default=0, verbose_name='Ordre')

    class Meta:
        verbose_name = 'Catégorie Produit'
        verbose_name_plural = 'Catégories Produits'
        ordering = ['sort_order', 'name']

    def __str__(self):
        return self.name


# ── Produits ──────────────────────────────────────────────────────────────────

class Product(models.Model):
    """
    Produit cosmétique Swisderm (ou d'un marchand partenaire).
    Payable via le wallet Cash Tel.
    """

    class Status(models.TextChoices):
        ACTIVE = 'ACTIVE', 'En vente'
        OUT_OF_STOCK = 'OUT_OF_STOCK', 'Rupture de stock'
        DISCONTINUED = 'DISCONTINUED', 'Arrêté'

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    merchant = models.ForeignKey(
        'merchant.MerchantProfile', on_delete=models.CASCADE,
        related_name='products',
        verbose_name='Marchand'
    )
    category = models.ForeignKey(
        ProductCategory, on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='products',
        verbose_name='Catégorie'
    )

    name = models.CharField(max_length=200, verbose_name='Nom du produit')
    description = models.TextField(blank=True, verbose_name='Description')
    sku = models.CharField(
        max_length=50, unique=True,
        verbose_name='Référence (SKU)',
        help_text='Code produit unique'
    )
    price = models.DecimalField(
        max_digits=18, decimal_places=3,
        verbose_name='Prix (BIF)'
    )
    image = models.ImageField(
        upload_to='products/', blank=True, null=True,
        verbose_name='Image produit'
    )

    stock_quantity = models.DecimalField(
        max_digits=15, decimal_places=3, default=0,
        verbose_name='Stock disponible'
    )
    status = models.CharField(
        max_length=20, choices=Status.choices,
        default=Status.ACTIVE, verbose_name='Statut'
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Produit'
        verbose_name_plural = 'Produits'
        ordering = ['category', 'name']

    def __str__(self):
        return f"{self.name} — {_b(self.price)} [{self.merchant.trade_name}]"

    @property
    def is_available(self):
        return self.status == self.Status.ACTIVE and self.stock_quantity > 0


class ProductImage(models.Model):
    """Images multiples d'un produit (AJOUT SEUL — Product.image gardée comme principale)."""

    product = models.ForeignKey(
        Product, on_delete=models.CASCADE,
        related_name='images', verbose_name='Produit'
    )
    image = models.ImageField(upload_to='products/gallery/', verbose_name='Image')
    sort_order = models.PositiveSmallIntegerField(default=0, verbose_name='Ordre')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Image Produit'
        verbose_name_plural = 'Images Produits'
        ordering = ['sort_order', 'created_at']

    def __str__(self):
        return f"{self.product.sku} #{self.sort_order}"


# ── Packages / Coffrets Swisderm (AJOUT SEUL — nouvelles tables) ────────────

class Package(models.Model):
    """
    Coffret/package Swisderm enregistré par l'ADMIN : lot de produits à prix fixe.
    Ex : Coffret Visage (savon + crème) = 15000 BIF.
    """

    class Status(models.TextChoices):
        ACTIVE = 'ACTIVE', 'En vente'
        INACTIVE = 'INACTIVE', 'Inactif'

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    merchant = models.ForeignKey(
        'merchant.MerchantProfile', on_delete=models.CASCADE,
        related_name='packages', verbose_name='Marchand'
    )
    name = models.CharField(max_length=200, verbose_name='Nom du package')
    description = models.TextField(blank=True, verbose_name='Description')
    image = models.ImageField(
        upload_to='packages/', blank=True, null=True,
        verbose_name='Image package'
    )
    price = models.DecimalField(max_digits=18, decimal_places=3, verbose_name='Prix package (BIF)')
    stock_quantity = models.DecimalField(max_digits=15, decimal_places=3, default=0, verbose_name='Stock packages')
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.ACTIVE, verbose_name='Statut')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Package'
        verbose_name_plural = 'Packages'
        ordering = ['name']

    def __str__(self):
        return f"{self.name} — {_b(self.price)} [{self.merchant.trade_name}]"

    @property
    def is_available(self):
        return self.status == self.Status.ACTIVE and self.stock_quantity > 0


class PackageItem(models.Model):
    """Contenu d'un package : produit + quantité (pour décrémenter le stock)."""

    package = models.ForeignKey(Package, on_delete=models.CASCADE, related_name='items', verbose_name='Package')
    product = models.ForeignKey(Product, on_delete=models.PROTECT, related_name='package_items', verbose_name='Produit')
    quantity = models.DecimalField(max_digits=15, decimal_places=3, default=1, verbose_name='Quantité')

    class Meta:
        verbose_name = 'Ligne Package'
        verbose_name_plural = 'Lignes Packages'

    def __str__(self):
        return f"{self.package.name} : {self.product.name} x{self.quantity}"


# ── Commandes ─────────────────────────────────────────────────────────────────

class Order(models.Model):
    """
    Commande client payée via le wallet Cash Tel.
    """

    class Status(models.TextChoices):
        PENDING = 'PENDING', 'En attente de paiement'
        PAID = 'PAID', 'Payé'
        PREPARING = 'PREPARING', 'En préparation'
        SHIPPED = 'SHIPPED', 'Expédié'
        DELIVERED = 'DELIVERED', 'Livré'
        CANCELLED = 'CANCELLED', 'Annulé'
        REFUNDED = 'REFUNDED', 'Remboursé'

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    order_number = models.CharField(
        max_length=20, unique=True,
        verbose_name='Numéro de commande'
    )
    customer = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name='orders',
        verbose_name='Client'
    )
    merchant = models.ForeignKey(
        'merchant.MerchantProfile', on_delete=models.PROTECT,
        related_name='orders',
        verbose_name='Marchand'
    )

    # ── Montants ─────────────────────────────────────────────────────────────
    subtotal = models.DecimalField(
        max_digits=18, decimal_places=3,
        verbose_name='Sous-total (BIF)'
    )
    fee = models.DecimalField(
        max_digits=12, decimal_places=3, default=0,
        verbose_name='Frais Cash Tel (BIF)'
    )
    total = models.DecimalField(
        max_digits=18, decimal_places=3,
        verbose_name='Total (BIF)'
    )

    status = models.CharField(
        max_length=20, choices=Status.choices,
        default=Status.PENDING, verbose_name='Statut'
    )

    # ── Livraison ────────────────────────────────────────────────────────────
    delivery_address = models.TextField(blank=True, verbose_name='Adresse de livraison')
    delivery_phone = models.CharField(
        max_length=20, blank=True,
        verbose_name='Téléphone livraison'
    )
    notes = models.TextField(blank=True, verbose_name='Notes client')

    # ── Lien transaction ─────────────────────────────────────────────────────
    transaction = models.ForeignKey(
        'transactions.Transaction', on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='orders',
        verbose_name='Transaction de paiement'
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    paid_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = 'Commande'
        verbose_name_plural = 'Commandes'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['customer', '-created_at']),
            models.Index(fields=['merchant', 'status']),
        ]

    def __str__(self):
        return f"CMD-{self.order_number} — {_b(self.total)} [{self.status}]"


# ── Lignes de Commande ────────────────────────────────────────────────────────

class OrderItem(models.Model):
    """Ligne individuelle dans une commande."""

    order = models.ForeignKey(
        Order, on_delete=models.CASCADE,
        related_name='items',
        verbose_name='Commande'
    )
    product = models.ForeignKey(
        Product, on_delete=models.PROTECT,
        related_name='order_items',
        verbose_name='Produit'
    )
    quantity = models.DecimalField(max_digits=15, decimal_places=3, default=1, verbose_name='Quantité')
    unit_price = models.DecimalField(
        max_digits=18, decimal_places=3,
        verbose_name='Prix unitaire (BIF)',
        help_text='Prix au moment de la commande'
    )
    total_price = models.DecimalField(
        max_digits=18, decimal_places=3,
        verbose_name='Prix total (BIF)'
    )

    class Meta:
        verbose_name = 'Ligne de Commande'
        verbose_name_plural = 'Lignes de Commande'

    def __str__(self):
        return f"{self.product.name} x{self.quantity} — {_b(self.total_price)}"

    def save(self, *args, **kwargs):
        self.total_price = self.unit_price * self.quantity
        super().save(*args, **kwargs)
