"""Tests circuit EN ATTENTE multi-lignes (ajout seul)."""
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


def test_multi_pending_create_sans_debit():
    from apps.transactions.pending_services import create_pending_transfer
    a = _user('+25762999011')
    _user('+25762999012', balance=0)
    _user('+25762999013', balance=0)
    avant = a.wallet.balance
    t1 = create_pending_transfer(a, '+25762999012', Decimal('5000'))
    t2 = create_pending_transfer(a, '+25762999013', Decimal('3000'))
    assert t1.status == 'PENDING' and t2.status == 'PENDING'
    a.wallet.refresh_from_db()
    assert a.wallet.balance == avant  # aucun débit à la création


def test_pending_modify_validate():
    from apps.transactions.pending_services import (
        create_pending_transfer, modify_pending_transfer, validate_pending_transfer)
    a = _user('+25762999021')
    _user('+25762999022', balance=0)
    _user('+25762999023', balance=0)
    t = create_pending_transfer(a, '+25762999022', Decimal('4000'))
    t = modify_pending_transfer(a, str(t.reference), receiver_phone='+25762999023', amount=Decimal('4500'))
    assert Decimal(str(t.amount)) == Decimal('4500')
    assert t.receiver.phone_number == '+25762999023'
    avant_a = a.wallet.balance
    txn = validate_pending_transfer(a, str(t.reference), '1234')
    assert txn.status == 'SUCCESS'
    a.wallet.refresh_from_db()
    assert a.wallet.balance < avant_a  # débit seulement à la validation


def test_pending_cancel_sans_debit():
    from apps.transactions.pending_services import create_pending_transfer, cancel_pending_transfer
    a = _user('+25762999031')
    _user('+25762999032', balance=0)
    avant = a.wallet.balance
    t = create_pending_transfer(a, '+25762999032', Decimal('2000'))
    c = cancel_pending_transfer(a, str(t.reference), 'erreur numero')
    assert c.status == 'FAILED'
    assert c.metadata.get('cancelled') is True
    a.wallet.refresh_from_db()
    assert a.wallet.balance == avant


def test_qr_auto_reste_immediat():
    from apps.transactions.services import process_qr_transfer
    a = _user('+25762999041')
    b = _user('+25762999042', balance=0)
    txn = process_qr_transfer(a, b.wallet.qr_data + ':1000', Decimal('1000'), '1234')
    assert txn.status == 'SUCCESS'  # QR avec montant obligatoire
