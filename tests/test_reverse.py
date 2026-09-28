"""Tests remboursement + blocage compte (ajout seul)."""
import pytest
from decimal import Decimal
from django.contrib.auth import get_user_model

User = get_user_model()
pytestmark = pytest.mark.django_db


def _user(phone, pin='1234', balance=50000, role='USER'):
    u = User.objects.create(phone_number=phone, first_name='T', last_name='U',
                            is_phone_verified=True, role=role)
    u.set_password('pass12345')
    u.set_pin(pin)
    u.save()
    u.wallet.balance = Decimal(balance)
    u.wallet.save(update_fields=['balance'])
    u.refresh_from_db()
    return u


def test_reverse_restitue_origine():
    from apps.transactions.services import process_transfer, reverse_transfer
    admin = _user('+25762999601', balance=0, role='ADMIN')
    admin.is_staff = True
    admin.save()
    alice = _user('+25762999602', balance=50000)
    bob = _user('+25762999603', balance=0)
    txn = process_transfer(alice, '+25762999603', Decimal('10000'), '1234')
    comp = reverse_transfer(admin, str(txn.reference), 'erreur numéro')
    assert comp.receiver.phone_number == '+25762999602'
    alice.wallet.refresh_from_db()
    bob.wallet.refresh_from_db()
    assert bob.wallet.balance == Decimal('0')
    assert alice.wallet.balance == Decimal('50000') - txn.fee
    txn.refresh_from_db()
    assert txn.status == 'REVERSED'
    from django.core.exceptions import ValidationError
    with pytest.raises(ValidationError, match='remboursé'):
        reverse_transfer(admin, str(txn.reference))


def test_block_unblock_client_et_agent():
    from apps.agent.services import process_cashin
    from django.core.exceptions import ValidationError
    admin = _user('+25762999701', balance=0, role='ADMIN')
    client = _user('+25762999702', balance=0)
    agent = _user('+25762999703', balance=0, role='AGENT')
    # blocage client : cashin refuse
    client.is_blocked = True
    client.save()
    with pytest.raises(ValidationError):
        process_cashin(agent, '+25762999702', Decimal('1000'))
    client.is_blocked = False
    client.save()
    # blocage effectif via vue : wallet gelé
    client.wallet.status = 'FROZEN'
    client.wallet.save()
    with pytest.raises(ValidationError, match='non actif'):
        process_cashin(agent, '+25762999702', Decimal('1000'))
