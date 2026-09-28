"""Tests retrait initié client (ajout seul)."""
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


def test_withdraw_client_initie_puis_agent_confirme():
    from apps.agent.withdraw_services import request_withdrawal, confirm_withdrawal
    client = _user('+25762999101', balance=50000)
    agent = _user('+25762999102', pin='0000', balance=0, role='AGENT')
    req = request_withdrawal(client, Decimal('10000'), '1234', 'idem-w1')
    assert len(req.code) == 6
    assert req.status == 'PENDING'
    avant = client.wallet.balance
    req2 = confirm_withdrawal(agent, req.code)
    assert req2.status == 'COMPLETED'
    client.wallet.refresh_from_db()
    assert client.wallet.balance == avant - req.amount - req.fee
    # re-confirmation idempotente : pas de 2e débit
    confirm_withdrawal(agent, req.code)
    client.wallet.refresh_from_db()
    assert client.wallet.balance == avant - req.amount - req.fee


def test_withdraw_pin_incorrect_et_code_invalide():
    from django.core.exceptions import ValidationError
    from apps.agent.withdraw_services import request_withdrawal, confirm_withdrawal
    client = _user('+25762999111', balance=50000)
    agent = _user('+25762999112', pin='0000', balance=0, role='AGENT')
    with pytest.raises(ValidationError, match='PIN'):
        request_withdrawal(client, Decimal('1000'), '9999')
    with pytest.raises(ValidationError, match='Code'):
        confirm_withdrawal(agent, '000000')
