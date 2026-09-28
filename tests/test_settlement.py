"""Tests split frais interop + settlement (ajout seul)."""
import pytest
from decimal import Decimal
from django.contrib.auth import get_user_model

User = get_user_model()
pytestmark = pytest.mark.django_db


def _user(phone, pin='1234', balance=100000):
    u = User.objects.create(phone_number=phone, first_name='T', last_name='U', is_phone_verified=True)
    u.set_password('pass12345')
    u.set_pin(pin)
    u.save()
    u.wallet.balance = Decimal(balance)
    u.wallet.save(update_fields=['balance'])
    u.refresh_from_db()
    return u


def test_split_somme_egale_fee():
    from apps.interop.models import ExternalProvider
    from apps.interop.services import interop_send, settlement_report, mark_settled
    from django.utils import timezone
    p, _ = ExternalProvider.objects.get_or_create(code='LUMICASH', defaults={
        'name': 'LumiCash', 'status': 'TESTING',
        'adapter_class': 'apps.interop.adapters.mock_adapter.MockProviderAdapter'})
    p.fee_percentage = Decimal('1')
    p.fee_fixed = Decimal('200')
    p.fee_split_provider = Decimal('50')
    p.fee_split_platform = Decimal('35')
    p.fee_split_agent = Decimal('15')
    p.save()
    u = _user('+25762999401')
    t = interop_send(u, 'LUMICASH', '+25762000099', Decimal('10000'), '1234')
    assert t.fee == Decimal('300')  # 200 + 1% de 10000
    assert t.provider_share + t.platform_share + t.agent_share == t.fee
    assert t.provider_share == Decimal('150')
    assert t.agent_share == Decimal('45')
    now = timezone.now()
    rows = settlement_report(now.year, now.month)
    row = [r for r in rows if r['provider__code'] == 'LUMICASH']
    assert row and row[0]['frais'] >= Decimal('300')
    n = mark_settled('LUMICASH', now.year, now.month)
    assert n >= 1
    t.refresh_from_db()
    assert t.settled is True
