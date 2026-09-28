"""Tests ponts banque + interop mock (ajout seul)."""
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


def _seed():
    from apps.banking.models import BankPartner
    from apps.interop.models import ExternalProvider
    BankPartner.objects.get_or_create(code='CRDB', defaults={
        'name': 'CRDB', 'status': 'TESTING', 'is_default': True,
        'adapter_class': 'apps.banking.adapters.mock_adapter.MockBankAdapter'})
    ExternalProvider.objects.get_or_create(code='LUMICASH', defaults={
        'name': 'LumiCash', 'status': 'TESTING',
        'adapter_class': 'apps.interop.adapters.mock_adapter.MockProviderAdapter'})


def test_bank_deposit_et_withdraw_mock():
    from apps.banking.services import bank_deposit, bank_withdraw
    _seed()
    u = _user('+25762999201', balance=20000)
    t = bank_deposit(u, 'CRDB', '12345', Decimal('10000'))
    assert t.status == 'COMPLETED'
    u.wallet.refresh_from_db()
    assert u.wallet.balance == Decimal('30000')
    t2 = bank_withdraw(u, 'CRDB', '12345', Decimal('5000'), '1234')
    assert t2.status == 'COMPLETED'
    u.wallet.refresh_from_db()
    assert u.wallet.balance < Decimal('30000') - Decimal('5000') + Decimal('1')


def test_interop_send_receive_mock():
    from apps.interop.services import interop_send, interop_receive
    _seed()
    u = _user('+25762999211', balance=50000)
    t = interop_send(u, 'LUMICASH', '+25762000099', Decimal('5000'), '1234')
    assert t.status == 'COMPLETED'
    u.wallet.refresh_from_db()
    assert u.wallet.balance < Decimal('50000') - Decimal('5000') + Decimal('1')
    avant = u.wallet.balance
    t2 = interop_receive(u, 'LUMICASH', '+25762000099', Decimal('3000'))
    assert t2.status == 'COMPLETED'
    u.wallet.refresh_from_db()
    assert u.wallet.balance == avant + Decimal('3000')
