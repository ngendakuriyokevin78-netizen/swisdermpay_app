"""Tests commission agent visible + claim (ajout seul)."""
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


def test_agent_voit_sa_commission_cashout_et_claim():
    from apps.agent.services import process_cashout
    from apps.agent.commission import get_commission_overview, claim_commission
    from apps.transactions.models import Fee
    Fee.objects.get_or_create(min_amount=100, max_amount=10000000,
                              defaults={'fee_value': 500, 'fee_type': 'FIXED', 'is_active': True})
    agent = _user('+25762999501', pin='0000', balance=0, role='AGENT')
    client = _user('+25762999502', balance=50000)
    process_cashout(agent, '+25762999502', Decimal('10000'), '1234')
    ov = get_commission_overview(agent)
    assert Decimal(ov['commission_balance']) > 0
    assert len(ov['history']) >= 1
    avant = agent.wallet.balance
    claimed, remaining, wallet = claim_commission(agent)
    assert claimed > 0 and remaining == 0
    assert wallet == avant + claimed


def test_interop_credite_agent_facilitateur():
    from apps.interop.models import ExternalProvider
    from apps.interop.services import interop_send
    from apps.agent.commission import get_commission_overview
    p, _ = ExternalProvider.objects.get_or_create(code='LUMICASH', defaults={
        'name': 'LumiCash', 'status': 'TESTING',
        'adapter_class': 'apps.interop.adapters.mock_adapter.MockProviderAdapter'})
    agent = _user('+25762999511', pin='0000', balance=0, role='AGENT')
    client = _user('+25762999512', balance=100000)
    t = interop_send(client, 'LUMICASH', '+25762000099', Decimal('10000'), '1234', agent=agent)
    assert t.agent_share > 0 and t.agent_id == agent.id
    ov = get_commission_overview(agent)
    assert Decimal(ov['commission_balance']) >= t.agent_share
