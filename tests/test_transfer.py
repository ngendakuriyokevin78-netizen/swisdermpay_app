"""
Tests pytest pour transfert et solde Cash Tel.
Lancer : pytest -v
"""
import pytest
from decimal import Decimal
from django.contrib.auth import get_user_model

User = get_user_model()
pytestmark = pytest.mark.django_db


def _make_user(phone, pin='1234', balance=50000):
    """Crée user vérifié + crédite wallet."""
    u = User.objects.create(
        phone_number=phone, first_name='Test', last_name='User',
        is_phone_verified=True,
    )
    u.set_password('pass12345')
    u.set_pin(pin)
    u.save()
    u.wallet.balance = Decimal(balance)
    u.wallet.save(update_fields=['balance'])
    u.refresh_from_db()
    return u


def test_transfer_reussit():
    from apps.transactions.services import process_transfer
    alice = _make_user('+25762000001')
    bob = _make_user('+25762000002', balance=0)
    solde_avant = alice.wallet.balance
    txn = process_transfer(alice, '+25762000002', Decimal('10000'), '1234')
    assert txn.status == 'SUCCESS'
    alice.wallet.refresh_from_db()
    bob.wallet.refresh_from_db()
    assert bob.wallet.balance == Decimal('10000')
    assert alice.wallet.balance == solde_avant - Decimal('10000') - txn.fee


def test_solde_insuffisant():
    from django.core.exceptions import ValidationError
    from apps.transactions.services import process_transfer
    alice = _make_user('+25762000011', balance=500)
    _make_user('+25762000012', balance=0)
    with pytest.raises(ValidationError, match='Solde insuffisant'):
        process_transfer(alice, '+25762000012', Decimal('10000'), '1234')


def test_pin_incorrect_bloque_apres_3():
    from apps.transactions.services import process_transfer
    from django.core.exceptions import ValidationError
    alice = _make_user('+25762000021')
    bob = _make_user('+25762000022', balance=0)
    for _ in range(3):
        with pytest.raises(ValidationError):
            process_transfer(alice, '+25762000022', Decimal('1000'), '0000')
    alice.refresh_from_db()
    assert alice.is_blocked is True


def test_transfert_qr():
    from apps.transactions.services import process_qr_transfer
    alice = _make_user('+25762000031')
    bob = _make_user('+25762000032', balance=0)
    bob.wallet.refresh_from_db()
    qr = bob.wallet.qr_data + ':5000'
    assert qr.startswith('SWISDERMPAY:')
    txn = process_qr_transfer(alice, qr, Decimal('5000'), '1234')
    assert txn.receiver.phone_number == '+25762000032'
    bob.wallet.refresh_from_db()
    assert bob.wallet.balance == Decimal('5000')


def test_qr_invalide():
    from django.core.exceptions import ValidationError
    from apps.transactions.services import process_qr_transfer
    alice = _make_user('+25762000041')
    with pytest.raises(ValidationError, match='QR sans montant refusé'):
        process_qr_transfer(alice, 'FAKE:xxx', Decimal('1000'), '1234')


def test_cashin_cashout_agent():
    from apps.agent.services import process_cashin, process_cashout
    agent = _make_user('+25762000051', balance=0)
    agent.role = 'AGENT'
    agent.save()
    client = _make_user('+25762000052', balance=0)
    process_cashin(agent, '+25762000052', Decimal('20000'))
    client.wallet.refresh_from_db()
    assert client.wallet.balance == Decimal('20000')
    process_cashout(agent, '+25762000052', Decimal('5000'), '1234')
    client.wallet.refresh_from_db()
    assert client.wallet.balance < Decimal('20000') - Decimal('5000') + Decimal('1')
