"""
Service retrait initié client (AJOUT SEUL — ne modifie pas process_cashout).
Flow :
  1. Client sur /m/ : POST withdraw-request {amount, pin} -> code 6 chiffres (30 min)
  2. Client montre code à l'agent
  3. Agent : POST withdraw-confirm {code} -> débit wallet + cash remis
PIN vérifié à l'étape 1 via check_pin (même règle que transferts).
Débit/frais/commission identiques à process_cashout (30% frais à l'agent).
"""
import logging
import secrets
from datetime import timedelta
from decimal import Decimal
from django.db import transaction
from django.core.exceptions import ValidationError
from django.utils import timezone

logger = logging.getLogger('apps.agent.withdraw')

COMMISSION_RATE = Decimal('0.30')
CODE_EXPIRY_MINUTES = 30


def _gen_code() -> str:
    return f"{secrets.randbelow(900000) + 100000}"


def request_withdrawal(customer, amount: Decimal, pin: str, idempotency_key: str = ''):
    """Étape 1 (client) : vérifie PIN + solde, crée la demande avec code."""
    from apps.transactions.services import calculate_fee
    from apps.wallet.models import Wallet
    from .models import WithdrawalRequest

    amount = Decimal(str(amount))
    if amount <= 0:
        raise ValidationError("Le montant doit être positif.")
    if customer.is_blocked:
        raise ValidationError("Compte bloqué.")
    if not customer.check_pin(pin):
        raise ValidationError("PIN incorrect.")

    # Idempotence téléphone (double-clic) : même clé -> renvoie la demande existante
    if idempotency_key:
        existing = WithdrawalRequest.objects.filter(
            customer=customer, idempotency_key=idempotency_key,
            status=WithdrawalRequest.Status.PENDING).first()
        if existing and existing.expires_at > timezone.now():
            return existing

    fee = calculate_fee(amount)
    try:
        wallet = customer.wallet
    except Wallet.DoesNotExist:
        raise ValidationError("Wallet introuvable.")
    if wallet.status != Wallet.Status.ACTIVE:
        raise ValidationError("Wallet non actif.")
    if wallet.balance < amount + fee:
        raise ValidationError(
            f"Solde insuffisant. Requis: {(amount + fee):,.0f} BIF | Dispo: {wallet.balance:,.0f} BIF")

    for _ in range(5):  # code unique
        code = _gen_code()
        if not WithdrawalRequest.objects.filter(code=code).exists():
            break
    else:
        raise ValidationError("Réessayez.")

    req = WithdrawalRequest.objects.create(
        customer=customer, amount=amount, fee=fee, code=code,
        idempotency_key=idempotency_key or '',
        expires_at=timezone.now() + timedelta(minutes=CODE_EXPIRY_MINUTES),
    )
    logger.info(f"Demande retrait {amount} BIF {customer.phone_number} code {code}")
    return req


@transaction.atomic
def confirm_withdrawal(agent_user, code: str):
    """Étape 2 (agent) : vérifie code, débite, crée Transaction WITHDRAWAL."""
    from apps.authentication.services import AuditService, SMSService
    from apps.transactions.models import Transaction
    from apps.wallet.models import Wallet
    from .models import AgentProfile, WithdrawalRequest

    if agent_user.role != 'AGENT' and not agent_user.is_staff:
        raise ValidationError("Seul un agent peut confirmer.")
    code = (code or '').strip()
    try:
        req = WithdrawalRequest.objects.select_for_update().get(code=code)
    except WithdrawalRequest.DoesNotExist:
        raise ValidationError("Code invalide.")
    if req.status == WithdrawalRequest.Status.COMPLETED:
        return req  # idempotent : agent re-scanne -> pas de 2e débit
    if req.status != WithdrawalRequest.Status.PENDING:
        raise ValidationError(f"Demande {req.get_status_display().lower()}.")
    if timezone.now() > req.expires_at:
        req.status = WithdrawalRequest.Status.EXPIRED
        req.save(update_fields=['status'])
        raise ValidationError("Code expiré. Créez une nouvelle demande.")

    customer = req.customer
    if customer.is_blocked:
        raise ValidationError("Compte client bloqué.")
    wallet = Wallet.objects.select_for_update().get(user=customer)
    total = req.amount + req.fee
    if wallet.balance < total:
        raise ValidationError("Solde client insuffisant.")
    wallet.balance -= total
    wallet.save(update_fields=['balance'])

    profile, _ = AgentProfile.objects.get_or_create(user=agent_user)
    commission = (req.fee * COMMISSION_RATE).quantize(Decimal('1'))
    if commission > 0:
        profile.commission_balance += commission
        profile.save(update_fields=['commission_balance'])

    txn = Transaction.objects.create(
        sender=customer, receiver=agent_user, amount=req.amount, fee=req.fee,
        transaction_type=Transaction.TransactionType.WITHDRAWAL,
        status=Transaction.Status.SUCCESS,
        description=f"Retrait initié client {customer.phone_number} via agent {agent_user.phone_number}",
        metadata={'agent': agent_user.phone_number, 'commission': str(commission),
                  'code': req.code, 'kind': 'CLIENT_INITIATED'},
    )
    req.status = WithdrawalRequest.Status.COMPLETED
    req.agent = agent_user
    req.transaction = txn
    req.completed_at = timezone.now()
    req.save(update_fields=['status', 'agent', 'transaction', 'completed_at'])

    SMSService.send_async(
        customer.phone_number,
        f"Swisderm Pay: Retrait {req.amount:,.0f} BIF (frais {req.fee:,.0f}). Solde: {wallet.balance:,.0f} BIF.")
    AuditService.log(user=agent_user, action='WITHDRAW_CONFIRMED',
                     details={'customer': customer.phone_number, 'amount': str(req.amount), 'code': req.code})
    logger.info(f"Retrait {req.amount} BIF {customer.phone_number} via {agent_user.phone_number}")
    return req


def cancel_withdrawal(customer, code: str):
    """Client annule sa demande en attente."""
    from .models import WithdrawalRequest
    try:
        req = WithdrawalRequest.objects.get(code=code, customer=customer)
    except WithdrawalRequest.DoesNotExist:
        raise ValidationError("Demande introuvable.")
    if req.status != WithdrawalRequest.Status.PENDING:
        raise ValidationError("Demande déjà traitée.")
    req.status = WithdrawalRequest.Status.CANCELLED
    req.save(update_fields=['status'])
    return req
