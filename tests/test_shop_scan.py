"""Tests scan & paiement auto Swisderm (ajout seul)."""
import pytest
from decimal import Decimal
from django.contrib.auth import get_user_model

User = get_user_model()
pytestmark = pytest.mark.django_db


def _user(phone, pin='1234', balance=50000):
    u = User.objects.create(phone_number=phone, first_name='T', last_name='U', is_phone_verified=True)
    u.set_password('pass12345')
    u.set_pin(pin)
    u.save()
    u.wallet.balance = Decimal(balance)
    u.wallet.save(update_fields=['balance'])
    u.refresh_from_db()
    return u


def test_scan_pay_order_auto_et_idempotent():
    from apps.merchant.models import MerchantProfile
    from apps.shop.models import Product, ProductCategory
    from apps.shop.services import create_order, pay_qr_auto
    client = _user('+25762999001')
    muser = _user('+25762999002', pin='4321', balance=0)
    mp, _ = MerchantProfile.objects.get_or_create(owner=muser, defaults={
        'company_name': 'Swisderm SARL', 'trade_name': 'SwisdermT', 'status': 'ACTIVE',
        'is_primary': True, 'bank_name': 'CRDB'})
    mp.status = 'ACTIVE'
    mp.save()
    cat, _ = ProductCategory.objects.get_or_create(name='SoinsT', slug='soinst')
    Product.objects.get_or_create(sku='LAIT-T001', defaults=dict(
        merchant=mp, name='Lait', price=Decimal('5000'), stock_quantity=10, status='ACTIVE'))
    order = create_order(client, 'SwisdermT', [{'sku': 'LAIT-T001', 'qty': 1}])
    assert order.status == 'PENDING'
    avant = client.wallet.balance
    r = pay_qr_auto(client, f'SWISDERM:{mp.id}:{order.order_number}', '1234', None, 'key-t1')
    assert r['order'].status == 'PAID'
    client.wallet.refresh_from_db()
    assert client.wallet.balance < avant
    solde_apres = client.wallet.balance
    # double-clic téléphone -> pas de 2e débit
    r2 = pay_qr_auto(client, f'SWISDERM:{mp.id}:{order.order_number}', '1234', None, 'key-t1')
    assert r2['order'].status == 'PAID'
    client.wallet.refresh_from_db()
    assert client.wallet.balance == solde_apres
