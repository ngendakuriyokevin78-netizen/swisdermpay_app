"""
Services bancaires Cash Tel (AJOUT SEUL).
Banque ↔ Wallet via adaptateurs (mock par défaut, CRDB quand accord signé).
- bank_deposit() : Banque → Wallet (crédite après succès adaptateur)
- bank_withdraw() : Wallet → Banque (débite puis envoie)
- bank_webhook() : callback banque, idempotent
"""
import logging
import uuid
from decimal import Decimal
from django.db import transaction
from django.core.exceptions import ValidationError
from apps.transactions.money import fmt_bif as _b
from django.utils import timezone

logger = logging.getLogger('apps.banking.services')


def _ref(prefix: str) -> str:
    return f"{prefix}-{timezone.now().strftime('%y%m%d')}-{uuid.uuid4().hex[:8].upper()}"


def _get_bank(code: str):
    from .models import BankPartner
    try:
        return BankPartner.objects.get(code__iexact=code)
    except BankPartner.DoesNotExist:
        raise ValidationError(f"Banque inconnue : {code}.")
    return None


@transaction.atomic
def bank_deposit(user, bank_code: str, account_number: str, amount: Decimal):
    """Banque → Wallet. Crédite le wallet si l'adaptateur répond succès."""
    from .models import BankAccount, BankTransfer
    from .factory import get_adapter
    from apps.wallet.models import Wallet
    from apps.transactions.models import Transaction
    from apps.authentication.services import AuditService, SMSService

    amount = Decimal(str(amount))
    bank = _get_bank(bank_code)
    if bank.status == 'INACTIVE':
        raise ValidationError("Banque inactive.")
    if amount < bank.min_transfer or amount > bank.max_transfer:
        raise ValidationError(
            f"Montant hors limites : {_b(bank.min_transfer)}–{_b(bank.max_transfer)}.")
    from .float_guard import require_float
    require_float(amount, f"dépôt {bank.code}")

    account, _ = BankAccount.objects.get_or_create(
        user=user, bank=bank, account_number=account_number,
        defaults={'account_name': user.get_full_name()})

    transfer = BankTransfer.objects.create(
        reference=_ref('BNK-DEP'), user=user, bank_account=account,
        direction=BankTransfer.Direction.DEPOSIT, amount=amount,
        status=BankTransfer.Status.PROCESSING)
    adapter = get_adapter(bank)
    result = adapter.initiate_deposit(account_number, amount, transfer.reference,
                                      f"Dépôt {user.phone_number}")
    transfer.bank_reference = result.bank_reference
    transfer.bank_response = result.raw_response
    if not result.success:
        transfer.status = BankTransfer.Status.FAILED
        transfer.error_message = result.message
        transfer.save()
        raise ValidationError(f"Banque : {result.message or 'échec'}.")

    wallet = Wallet.objects.select_for_update().get(user=user)
    if wallet.status != Wallet.Status.ACTIVE:
        raise ValidationError("Wallet non actif.")
    wallet.balance += amount
    wallet.save(update_fields=['balance'])
    Transaction.objects.create(
        sender=None, receiver=user, amount=amount, fee=0,
        transaction_type=Transaction.TransactionType.DEPOSIT,
        status=Transaction.Status.SUCCESS,
        description=f"Dépôt bancaire {bank.code} {account_number}",
        metadata={'bank': bank.code, 'bank_ref': result.bank_reference,
                  'bank_transfer': str(transfer.id)})
    transfer.status = BankTransfer.Status.COMPLETED
    transfer.completed_at = timezone.now()
    transfer.save()
    SMSService.send_async(user.phone_number, f"Swisderm Pay: Dépôt {bank.code} {_b(amount)} reçu.")
    AuditService.log(user=user, action='BANK_DEPOSIT', details={'bank': bank.code, 'amount': str(amount)})
    return transfer


@transaction.atomic
def bank_withdraw(user, bank_code: str, account_number: str, amount: Decimal, pin: str):
    """Wallet → Banque. Débite puis envoie via adaptateur. Rembourse si banque échoue."""
    from .models import BankAccount, BankTransfer
    from .factory import get_adapter
    from apps.wallet.models import Wallet
    from apps.transactions.models import Transaction
    from apps.transactions.services import calculate_fee
    from apps.authentication.services import AuditService, SMSService

    amount = Decimal(str(amount))
    if not user.check_pin(pin):
        raise ValidationError("PIN incorrect.")
    if user.is_blocked:
        raise ValidationError("Compte bloqué.")
    bank = _get_bank(bank_code)
    if bank.status == 'INACTIVE':
        raise ValidationError("Banque inactive.")

    fee = calculate_fee(amount)
    wallet = Wallet.objects.select_for_update().get(user=user)
    if wallet.balance < amount + fee:
        raise ValidationError("Solde insuffisant.")
    wallet.balance -= (amount + fee)
    wallet.save(update_fields=['balance'])

    account, _ = BankAccount.objects.get_or_create(
        user=user, bank=bank, account_number=account_number,
        defaults={'account_name': user.get_full_name()})
    transfer = BankTransfer.objects.create(
        reference=_ref('BNK-WIT'), user=user, bank_account=account,
        direction=BankTransfer.Direction.WITHDRAW, amount=amount, fee=fee,
        status=BankTransfer.Status.PROCESSING)
    adapter = get_adapter(bank)
    result = adapter.initiate_withdrawal(account_number, amount, transfer.reference,
                                         f"Retrait {user.phone_number}")
    transfer.bank_reference = result.bank_reference
    transfer.bank_response = result.raw_response
    if not result.success:
        # rollback financier : recrédite
        wallet.balance += (amount + fee)
        wallet.save(update_fields=['balance'])
        transfer.status = BankTransfer.Status.FAILED
        transfer.error_message = result.message
        transfer.save()
        raise ValidationError(f"Banque : {result.message or 'échec'}. Remboursé.")
    Transaction.objects.create(
        sender=user, receiver=None, amount=amount, fee=fee,
        transaction_type=Transaction.TransactionType.WITHDRAWAL,
        status=Transaction.Status.SUCCESS,
        description=f"Retrait bancaire {bank.code} {account_number}",
        metadata={'bank': bank.code, 'bank_ref': result.bank_reference})
    transfer.status = BankTransfer.Status.COMPLETED
    transfer.completed_at = timezone.now()
    transfer.save()
    SMSService.send_async(user.phone_number, f"Swisderm Pay: Retrait {bank.code} {_b(amount)} envoyé.")
    AuditService.log(user=user, action='BANK_WITHDRAW', details={'bank': bank.code, 'amount': str(amount)})
    return transfer


def bank_webhook(bank_code: str, payload: dict, raw_body: bytes, signature: str):
    """Callback banque (ex: confirmation différée). Idempotent sur bank_reference."""
    from .models import BankTransfer
    from .factory import get_adapter
    bank = _get_bank(bank_code)
    adapter = get_adapter(bank)
    if not adapter.verify_webhook_signature(raw_body, signature or ''):
        raise ValidationError("Signature webhook invalide.")
    ref = payload.get('bank_reference') or payload.get('reference') or ''
    if not ref:
        raise ValidationError("Référence manquante.")
    try:
        transfer = BankTransfer.objects.get(bank_reference=ref)
    except BankTransfer.DoesNotExist:
        raise ValidationError("Transfert introuvable.")
    if transfer.status == BankTransfer.Status.COMPLETED:
        return transfer  # idempotent
    if payload.get('status') == 'FAILED':
        transfer.status = BankTransfer.Status.FAILED
        transfer.error_message = payload.get('message', '')
    else:
        transfer.status = BankTransfer.Status.COMPLETED
        transfer.completed_at = timezone.now()
    transfer.bank_response = {**(transfer.bank_response or {}), 'webhook': payload}
    transfer.save()
    return transfer
