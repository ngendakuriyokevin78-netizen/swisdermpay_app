"""
Services métier Agent : Cash In (dépôt) et Cash Out (retrait).
Logique atomique avec commission agent de 30% des frais.
"""
import logging
from decimal import Decimal, ROUND_DOWN
from django.db import transaction
from django.core.exceptions import ValidationError
from apps.transactions.money import fmt_bif

logger = logging.getLogger('apps.agent')
COMMISSION_RATE = Decimal('0.30')


def _get_agent_profile(agent_user):
    """Vérifie rôle AGENT et retourne (ou crée) son profil."""
    if agent_user.role != 'AGENT' and not agent_user.is_staff:
        raise ValidationError("Seul un agent Cash Tel peut effectuer cette opération.")
    from .models import AgentProfile
    profile, _ = AgentProfile.objects.get_or_create(user=agent_user)
    return profile


@transaction.atomic
def process_cashin(agent_user, customer_phone: str, amount: Decimal):
    """L'agent crédite le wallet du client (argent physique -> électronique)."""
    from apps.authentication.models import User
    from apps.authentication.services import AuditService, SMSService
    from apps.transactions.models import Transaction
    from apps.wallet.models import Wallet

    if amount <= 0:
        raise ValidationError("Le montant doit être positif.")
    from apps.banking.float_guard import require_float
    require_float(Decimal(str(amount)), "cash-in agent")
    profile = _get_agent_profile(agent_user)
    try:
        customer = User.objects.get(phone_number=customer_phone, is_active=True)
    except User.DoesNotExist:
        raise ValidationError(f"Client introuvable : {customer_phone}.")
    if customer.is_blocked:
        raise ValidationError("Compte client bloqué.")
    wallet = Wallet.objects.select_for_update().get(user=customer)
    if wallet.status != Wallet.Status.ACTIVE:
        raise ValidationError("Wallet client non actif.")
    wallet.balance += amount
    wallet.save(update_fields=['balance'])
    txn = Transaction.objects.create(
        sender=agent_user, receiver=customer, amount=amount, fee=0,
        transaction_type=Transaction.TransactionType.DEPOSIT,
        status=Transaction.Status.SUCCESS,
        description=f"Dépôt agent {agent_user.phone_number} -> {customer_phone}",
        metadata={'agent': agent_user.phone_number},
    )
    SMSService.send_async(
        customer_phone,
        f"Swisderm Pay: Dépôt {fmt_bif(amount)} reçu. Nouveau solde: {fmt_bif(wallet.balance)}. Réf: {str(txn.reference)[:8].upper()}"
    )
    AuditService.log(user=agent_user, action='CASHIN', details={'customer': customer_phone, 'amount': str(amount)})
    logger.info(f"CashIn {amount} BIF agent {agent_user.phone_number} -> {customer_phone}")
    return txn


@transaction.atomic
def process_cashout(agent_user, customer_phone: str, amount: Decimal, pin: str):
    """Le client retire du cash : débit wallet + commission agent."""
    from apps.authentication.models import User
    from apps.authentication.services import AuditService, SMSService
    from apps.transactions.models import Transaction, Fee
    from apps.transactions.services import calculate_fee
    from apps.wallet.models import Wallet

    if amount <= 0:
        raise ValidationError("Le montant doit être positif.")
    profile = _get_agent_profile(agent_user)
    try:
        customer = User.objects.get(phone_number=customer_phone, is_active=True)
    except User.DoesNotExist:
        raise ValidationError(f"Client introuvable : {customer_phone}.")
    if not customer.check_pin(pin):
        # Anti-bruteforce aligné sur transferts : compteur + blocage + gel wallet
        from django.conf import settings as _settings
        from apps.wallet.models import Wallet as _Wallet
        customer.failed_pin_attempts += 1
        max_attempts = _settings.MAX_PIN_ATTEMPTS
        if customer.failed_pin_attempts >= max_attempts:
            customer.is_blocked = True
            try:
                customer.wallet.status = _Wallet.Status.FROZEN
                customer.wallet.save(update_fields=['status'])
            except _Wallet.DoesNotExist:
                pass
            except Exception:
                pass
            customer.save(update_fields=['failed_pin_attempts', 'is_blocked'])
            raise ValidationError(
                f"Compte bloqué après {max_attempts} tentatives de PIN incorrectes."
            )
        customer.save(update_fields=['failed_pin_attempts'])
        raise ValidationError("PIN client incorrect.")
    if customer.failed_pin_attempts > 0:
        customer.failed_pin_attempts = 0
        customer.save(update_fields=['failed_pin_attempts'])
    if customer.is_blocked:
        raise ValidationError("Compte client bloqué.")
    fee = calculate_fee(amount)
    total = amount + fee
    wallet = Wallet.objects.select_for_update().get(user=customer)
    if wallet.balance < total:
        raise ValidationError(
            f"Solde insuffisant. Requis: {fmt_bif(total)} | Dispo: {fmt_bif(wallet.balance)}"
        )
    wallet.balance -= total
    wallet.save(update_fields=['balance'])
    commission = (fee * COMMISSION_RATE).quantize(Decimal('0.001'), rounding=ROUND_DOWN)
    if commission > 0:
        profile.commission_balance += commission
        profile.save(update_fields=['commission_balance'])
    txn = Transaction.objects.create(
        sender=customer, receiver=agent_user, amount=amount, fee=fee,
        transaction_type=Transaction.TransactionType.WITHDRAWAL,
        status=Transaction.Status.SUCCESS,
        description=f"Retrait {customer_phone} via agent {agent_user.phone_number}",
        metadata={'agent': agent_user.phone_number, 'commission': str(commission)},
    )
    SMSService.send_async(
        customer_phone,
        f"Swisderm Pay: Retrait {fmt_bif(amount)} (frais {fmt_bif(fee)}). Solde: {fmt_bif(wallet.balance)}."
    )
    AuditService.log(user=agent_user, action='CASHOUT', details={'customer': customer_phone, 'amount': str(amount)})
    logger.info(f"CashOut {amount} BIF client {customer_phone} via {agent_user.phone_number}")
    return txn
