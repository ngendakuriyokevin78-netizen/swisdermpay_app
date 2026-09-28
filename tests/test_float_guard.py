"""Tests garde-fou float cantonné (ajout seul)."""
import pytest
from decimal import Decimal
from django.contrib.auth import get_user_model

User = get_user_model()
pytestmark = pytest.mark.django_db


def _user(phone, pin='1234', balance=0):
    u = User.objects.create(phone_number=phone, first_name='T', last_name='U', is_phone_verified=True)
    u.set_password('pass12345')
    u.set_pin(pin)
    u.save()
    u.wallet.balance = Decimal(balance)
    u.wallet.save(update_fields=['balance'])
    u.refresh_from_db()
    return u


def test_emission_bloquee_sans_plafond():
    from django.core.exceptions import ValidationError
    from apps.banking.models import BankFloat
    from apps.banking.float_guard import require_float
    BankFloat.objects.all().delete()  # aucun plafond -> fail-safe
    with pytest.raises(ValidationError, match='aucun plafond'):
        require_float(Decimal('1000'))


def test_emission_bloquee_si_depassement():
    from django.core.exceptions import ValidationError
    from apps.banking.models import BankPartner, BankFloat
    from apps.banking.float_guard import require_float, get_total_emoney
    from apps.agent.services import process_cashin
    bank = BankPartner.objects.get(code='CRDB')
    # plafond juste au total actuel -> tout nouvel e-money refusé
    BankFloat.objects.update_or_create(bank=bank, defaults={'ceiling': get_total_emoney()})
    agent = _user('+25762999301', pin='0000', balance=0)
    agent.role = 'AGENT'
    agent.save()
    client = _user('+25762999302', balance=0)
    with pytest.raises(ValidationError, match='plafond'):
        process_cashin(agent, '+25762999302', Decimal('5000'))


def test_emission_ok_dans_plafond():
    from apps.banking.models import BankPartner, BankFloat
    from apps.banking.float_guard import get_total_emoney
    from apps.agent.services import process_cashin
    bank = BankPartner.objects.get(code='CRDB')
    BankFloat.objects.update_or_create(
        bank=bank, defaults={'ceiling': get_total_emoney() + Decimal('1000000')})
    agent = _user('+25762999311', pin='0000', balance=0)
    agent.role = 'AGENT'
    agent.save()
    _user('+25762999312', balance=0)
    process_cashin(agent, '+25762999312', Decimal('10000'))
