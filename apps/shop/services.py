"""
Service Boutique Cash Tel / Swisderm (AJOUT SEUL — ne modifie rien d'existant).
- create_order() : panier -> commande PENDING, sans toucher au wallet
- pay_order_auto() : scan QR commande/produit -> transfert automatique
  client -> marchand en réutilisant apps.transactions.services.process_transfer
- parse_shop_qr() : comprend SWISDERM:{merchant_code}:{order_number}
  et SWISDERM:{merchant_code}:{sku}:{qty} + P2P SWISDERMPAY:... (legacy CASHTEL:... accepté)
"""
import logging
import uuid
from decimal import Decimal
from django.db import transaction
from django.core.exceptions import ValidationError
from django.utils import timezone

logger = logging.getLogger('apps.shop')


def _gen_order_number() -> str:
    return f"CMD-{timezone.now().strftime('%y%m%d')}-{uuid.uuid4().hex[:6].upper()}"


def parse_shop_qr(qr_data: str) -> dict:
    """
    Parse un QR scanné au téléphone.
    Retours :
      {'kind': 'ORDER', 'merchant_code': ..., 'order_number': ...}
      {'kind': 'PRODUCT', 'merchant_code': ..., 'sku': ..., 'qty': ...}
      {'kind': 'P2P', 'raw': 'SWISDERMPAY:...'} -> délégué à l'existant
    """
    raw = (qr_data or '').strip()
    if raw.startswith('SWISDERMPAY:') or raw.startswith('CASHTEL:'):
        return {'kind': 'P2P', 'raw': raw}
    if not raw.startswith('SWISDERM:'):
        raise ValidationError("QR invalide. Attendu SWISDERM:... ou SWISDERMPAY:...")
    parts = raw.split(':')
    # SWISDERM:{merchant_code}:{order_number}
    if len(parts) == 3:
        _, merchant_code, order_number = parts
        return {'kind': 'ORDER', 'merchant_code': merchant_code, 'order_number': order_number}
    # SWISDERM:{merchant_code}:{sku}:{qty}
    if len(parts) == 4:
        _, merchant_code, sku, qty = parts
        try:
            qty = int(qty)
        except ValueError:
            raise ValidationError("Quantité QR invalide.")
        return {'kind': 'PRODUCT', 'merchant_code': merchant_code, 'sku': sku, 'qty': qty}
    raise ValidationError("Format QR Swisderm invalide.")


def create_order(customer, merchant_code: str, items: list, delivery_address: str = '',
                 delivery_phone: str = '', notes: str = ''):
    """
    items = [{'sku': 'LAIT-500', 'qty': 2}, ...]
    Crée une commande PENDING. Ne débite rien. Idempotent via order_number généré.
    """
    from apps.merchant.models import MerchantProfile
    from .models import Product, Order, OrderItem

    try:
        merchant = MerchantProfile.objects.get(id=merchant_code, status='ACTIVE') \
            if len(str(merchant_code)) > 20 else \
            MerchantProfile.objects.get(trade_name__iexact=str(merchant_code), status='ACTIVE')
    except MerchantProfile.DoesNotExist:
        # fallback : code = trade_name ou id
        try:
            merchant = MerchantProfile.objects.get(trade_name__iexact=str(merchant_code))
        except MerchantProfile.DoesNotExist:
            raise ValidationError(f"Marchand introuvable : {merchant_code}.")
        if merchant.status != 'ACTIVE':
            raise ValidationError("Marchand suspendu.")

    if not items:
        raise ValidationError("Panier vide.")

    with transaction.atomic():
        order = Order.objects.create(
            order_number=_gen_order_number(),
            customer=customer,
            merchant=merchant,
            subtotal=Decimal('0'),
            fee=Decimal('0'),
            total=Decimal('0'),
            delivery_address=delivery_address,
            delivery_phone=delivery_phone,
            notes=notes,
            status=Order.Status.PENDING,
        )
        subtotal = Decimal('0')
        for line in items:
            try:
                product = Product.objects.get(sku=line['sku'], merchant=merchant)
            except Product.DoesNotExist:
                raise ValidationError(f"Produit introuvable : {line.get('sku')}.")
            qty = int(line.get('qty', 1))
            if qty <= 0:
                raise ValidationError("Quantité invalide.")
            if not product.is_available or product.stock_quantity < qty:
                raise ValidationError(f"Stock insuffisant : {product.name}.")
            OrderItem.objects.create(
                order=order, product=product, quantity=qty,
                unit_price=product.price, total_price=product.price * qty,
            )
            subtotal += product.price * qty
        # Frais via grille existante (sans la dupliquer)
        from apps.transactions.services import calculate_fee
        fee = calculate_fee(subtotal)
        order.subtotal = subtotal
        order.fee = fee
        order.total = subtotal  # client paie subtotal, frais débités en plus comme P2P
        order.save(update_fields=['subtotal', 'fee', 'total'])
    return order


@transaction.atomic
def _decrement_stock(order):
    """Décrémente le stock après paiement réussi (lignes verrouillées)."""
    for item in order.items.select_related('product').select_for_update():
        product = item.product
        if product.stock_quantity < item.quantity:
            raise ValidationError(f"Rupture : {product.name}.")
        product.stock_quantity -= item.quantity
        product.save(update_fields=['stock_quantity'])


def pay_order_auto(customer, order_number: str, pin: str, idempotency_key: str = ''):
    """
    TRANSFERT AUTOMATIQUE après scan : client -> wallet marchand.
    - Vérifie PIN via process_transfer existant (blocage 3 essais conservé)
    - Anti double-paiement : si order déjà PAID, renvoie sans re-débiter
    - Anti double-clic téléphone : idempotency via metadata
    """
    from .models import Order
    from apps.transactions.services import process_transfer

    try:
        order = Order.objects.select_related('merchant__owner', 'customer').get(order_number=order_number)
    except Order.DoesNotExist:
        raise ValidationError("Commande introuvable.")

    if order.customer_id != customer.id:
        raise ValidationError("Cette commande n'est pas la vôtre.")
    if order.status in ('PAID', 'PREPARING', 'SHIPPED', 'DELIVERED'):
        return order  # déjà payée -> idempotent, pas de 2e débit
    if order.status in ('CANCELLED', 'REFUNDED'):
        raise ValidationError("Commande annulée.")

    merchant_phone = order.merchant.owner.phone_number
    # Idempotence téléphone : même idempotency_key déjà utilisée ?
    if idempotency_key and order.transaction and order.transaction.metadata.get('idempotency_key') == idempotency_key:
        return order

    # Débit/crédit via le moteur existant (vérifie PIN, solde, frais, SMS, audit)
    txn = process_transfer(
        sender=customer,
        receiver_phone=merchant_phone,
        amount=Decimal(str(order.subtotal)),
        pin=pin,
    )
    # Enrichit la transaction SANS changer son type (reste TRANSFER -> pas de migration cassante)
    meta = dict(txn.metadata or {})
    meta.update({
        'kind': 'MERCHANT_PAY',
        'order_number': order.order_number,
        'merchant': order.merchant.trade_name or order.merchant.company_name,
        'idempotency_key': idempotency_key or str(txn.reference),
    })
    txn.metadata = meta
    txn.description = f"Achat Swisderm {order.order_number} : {order.merchant.trade_name}"
    txn.save(update_fields=['metadata', 'description'])

    order.transaction = txn
    order.status = Order.Status.PAID
    order.paid_at = timezone.now()
    order.save(update_fields=['transaction', 'status', 'paid_at'])
    _decrement_stock(order)

    # Chiffre d'affaires marchand (hors transaction financière)
    merchant = order.merchant
    merchant.total_revenue = (merchant.total_revenue or Decimal('0')) + order.subtotal
    merchant.save(update_fields=['total_revenue'])

    logger.info(f"Paiement auto OK {order.order_number} : {customer.phone_number} -> {merchant_phone}")
    return order


def pay_qr_auto(customer, qr_data: str, pin: str, amount_override=None, idempotency_key: str = ''):
    """
    Point d'entrée unique du bouton 'Scanner & Payer' sur téléphone.
    - QR ORDER -> pay_order_auto (montant du QR, ignore amount_override)
    - QR PRODUCT -> crée commande mono-produit puis paie
    - QR CASHTEL -> délègue à process_qr_transfer existant
    """
    parsed = parse_shop_qr(qr_data)
    if parsed['kind'] == 'P2P':
        from apps.transactions.services import process_qr_transfer
        amt = Decimal(str(amount_override)) if amount_override else None
        return {'kind': 'P2P', 'transaction': process_qr_transfer(
            customer, parsed['raw'], amt, pin)}
    if parsed['kind'] == 'ORDER':
        order = pay_order_auto(customer, parsed['order_number'], pin, idempotency_key)
        return {'kind': 'ORDER', 'order': order}
    # PRODUCT : achat express 1 produit scanné en rayon
    order = create_order(customer, parsed['merchant_code'],
                         [{'sku': parsed['sku'], 'qty': parsed['qty']}])
    order = pay_order_auto(customer, order.order_number, pin, idempotency_key)
    return {'kind': 'ORDER', 'order': order}
