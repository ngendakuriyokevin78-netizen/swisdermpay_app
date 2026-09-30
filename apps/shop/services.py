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
            qty = Decimal(str(line.get('qty', 1)))
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


def pay_free(customer, receiver_phone: str, designation: str, amount, pin: str):
    """
    Achat libre SANS catalogue (AJOUT SEUL) : désignation + montant + destinataire.
    - Pas de Product/SKU/stock requis. Idéal : service, coiffure, transport,
      paiement pour une autre personne.
    - Réutilise process_transfer (PIN transfert, frais, SMS, audit) puis enrichit
      la description/metadata kind=FREE_PAY. Compté dans Envoyés + Achats du résumé.
    """
    from apps.transactions.services import process_transfer
    from decimal import Decimal as _D
    amount = _D(str(amount))
    txn = process_transfer(
        sender=customer,
        receiver_phone=receiver_phone,
        amount=amount,
        pin=pin,
    )
    meta = dict(txn.metadata or {})
    meta.update({'kind': 'MERCHANT_PAY', 'subkind': 'FREE_PAY', 'designation': (designation or '').strip()})
    txn.metadata = meta
    from apps.transactions.money import fmt_bif as _bif
    txn.description = f"Achat libre : {(designation or '').strip()} ({_bif(amount)})"
    txn.save(update_fields=['metadata', 'description'])
    logger.info(f"Achat libre OK : {customer.phone_number} -> {receiver_phone} | {designation}")
    return txn


def grant_client_bonus(admin_user, client_phone: str, amount, reason: str = ''):
    """
    Bonus / remise frais pour gros acheteurs, accordé au siège Swisderm (AJOUT SEUL).
    - ADMIN seul (vérifié dans la vue).
    - Crédit direct wallet client (type DEPOSIT, kind=BONUS), sans toucher au moteur de frais.
    - Visible dans Historique + Transactions (reçus).
    """
    from decimal import Decimal as _D
    from django.db import transaction as _tx
    from django.core.exceptions import ValidationError as _VE
    from apps.authentication.models import User as _User
    from apps.authentication.services import AuditService as _Audit, SMSService as _SMS
    from apps.transactions.models import Transaction as _Txn
    from apps.wallet.models import Wallet as _Wallet
    amount = _D(str(amount))
    if amount <= 0:
        raise _VE("Montant bonus positif requis.")
    if amount > _D("1000000"):
        raise _VE("Montant bonus trop élevé (max 1 000 000 BIF par accord).")
    reason = (reason or '').strip() or 'Bonus gros acheteur / remise frais'
    try:
        client = _User.objects.get(phone_number=client_phone, is_active=True)
    except _User.DoesNotExist:
        raise _VE(f"Client introuvable : {client_phone}.")
    if client.is_blocked:
        raise _VE("Compte client bloqué.")
    with _tx.atomic():
        wallet = _Wallet.objects.select_for_update().get(user=client)
        if wallet.status != _Wallet.Status.ACTIVE:
            raise _VE("Wallet client non actif.")
        wallet.balance += amount
        wallet.save(update_fields=['balance'])
        txn = _Txn.objects.create(
            sender=admin_user, receiver=client, amount=amount, fee=0,
            transaction_type=_Txn.TransactionType.DEPOSIT,
            status=_Txn.Status.SUCCESS,
            description=f"Bonus Swisderm (siège) : {reason}",
            metadata={'kind': 'BONUS', 'subkind': 'FEE_DISCOUNT', 'reason': reason,
                      'granted_by': admin_user.phone_number, 'granted_at': str(wallet.balance)},
        )
    try:
        _SMS.send_async(client_phone, f"Swisderm Pay: Bonus {_bif(amount)} reçu ({reason}). Nouveau solde: {_bif(wallet.balance)}.")
    except Exception:
        pass
    try:
        _Audit.log(user=admin_user, action='BONUS_GRANTED', details={'client': client_phone, 'amount': str(amount), 'reason': reason})
    except Exception:
        pass
    logger.info(f"Bonus OK {amount} BIF siège {admin_user.phone_number} -> {client_phone} ({reason})")
    return txn


def _resolve_merchant(merchant_code: str):
    """Retrouve le marchand actif par trade_name ou id (robuste aux doublons : primary d'abord)."""
    from apps.merchant.models import MerchantProfile
    from django.core.exceptions import ValidationError as _VE
    code = str(merchant_code or '').strip()
    if len(code) > 20:
        try:
            return MerchantProfile.objects.get(id=code)
        except (MerchantProfile.DoesNotExist, ValueError, TypeError):
            pass
    m = MerchantProfile.objects.filter(trade_name__iexact=code, status='ACTIVE').order_by('-is_primary', '-created_at').first()
    if m:
        return m
    m = MerchantProfile.objects.filter(trade_name__iexact=code).order_by('-is_primary', '-created_at').first()
    if m:
        if m.status != 'ACTIVE':
            raise _VE("Marchand suspendu.")
        return m
    raise _VE(f"Marchand introuvable : {merchant_code}.")


def register_product(merchant_code: str, sku: str, name: str, price, stock_quantity: int = 0, description: str = ''):
    """Enregistre un produit Swisderm par l'ADMIN (ajout seul)."""
    from .models import Product
    from django.core.exceptions import ValidationError as _VE
    from decimal import Decimal as _D
    merchant = _resolve_merchant(merchant_code)
    sku = (sku or '').strip()
    if not sku:
        raise _VE("SKU requis.")
    if Product.objects.filter(sku=sku).exists():
        raise _VE(f"SKU déjà existant : {sku}.")
    price = _D(str(price))
    if price <= 0:
        raise _VE("Prix positif requis.")
    return Product.objects.create(
        merchant=merchant, sku=sku, name=(name or '').strip(), description=description or '',
        price=price, stock_quantity=_D(str(stock_quantity or 0)), status=Product.Status.ACTIVE,
    )


def register_package(merchant_code: str, name: str, price, stock_quantity: int = 0, description: str = '', items: list = None):
    """Enregistre un package/coffret par l'ADMIN avec son contenu [{sku, qty}]."""
    from .models import Product, Package, PackageItem
    from django.core.exceptions import ValidationError as _VE
    from decimal import Decimal as _D
    merchant = _resolve_merchant(merchant_code)
    name = (name or '').strip()
    if len(name) < 3:
        raise _VE("Nom package trop court.")
    price = _D(str(price))
    if price <= 0:
        raise _VE("Prix package positif requis.")
    pkg = Package.objects.create(
        merchant=merchant, name=name, description=description or '', price=price,
        stock_quantity=_D(str(stock_quantity or 0)), status=Package.Status.ACTIVE,
    )
    for line in (items or []):
        try:
            product = Product.objects.get(sku=line['sku'], merchant=merchant)
        except Product.DoesNotExist:
            pkg.delete()
            raise _VE(f"Produit introuvable : {line.get('sku')}. Enregistrez-le d'abord.")
        PackageItem.objects.create(package=pkg, product=product, quantity=_D(str(line.get('qty', 1))))
    return pkg


def create_order_with_package(customer, merchant_code: str, package_id: str, qty: int = 1):
    """
    Commande d'un package existant (même ligne produit + package).
    Crée une commande PENDING au prix du package, lignes = contenu réel (stock).
    """
    from .models import Order, OrderItem, Package
    from django.core.exceptions import ValidationError as _VE
    from decimal import Decimal as _D
    qty = _D(str(qty or 1))
    if qty <= 0:
        raise _VE("Quantité invalide.")
    try:
        pkg = Package.objects.select_related('merchant').prefetch_related('items__product').get(id=package_id)
    except (Package.DoesNotExist, ValueError, TypeError):
        raise _VE("Package introuvable.")
    if merchant_code and pkg.merchant.trade_name.lower() != str(merchant_code).lower() and str(pkg.merchant_id) != str(merchant_code):
        pass  # on accepte tout marchand actif, le filtre n'est qu'indicatif
    if pkg.status != Package.Status.ACTIVE:
        raise _VE("Package inactif.")
    if pkg.stock_quantity < qty:
        raise _VE(f"Stock package insuffisant : {pkg.name}.")
    with transaction.atomic():
        order = Order.objects.create(
            order_number=_gen_order_number(), customer=customer, merchant=pkg.merchant,
            subtotal=pkg.price * qty, fee=_D('0'), total=pkg.price * qty, status=Order.Status.PENDING,
            notes=f"Package : {pkg.name} x{qty}",
        )
        from apps.transactions.services import calculate_fee
        fee = calculate_fee(order.subtotal)
        order.fee = fee
        order.save(update_fields=['fee'])
        for line in pkg.items.all():
            need = line.quantity * qty
            if not line.product.is_available or line.product.stock_quantity < need:
                raise _VE(f"Stock insuffisant : {line.product.name}.")
            OrderItem.objects.create(order=order, product=line.product, quantity=need,
                                     unit_price=line.product.price, total_price=line.product.price * need)
        pkg.stock_quantity -= qty
        pkg.save(update_fields=['stock_quantity'])
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
