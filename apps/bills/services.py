"""
Service paiement factures : débit wallet atomique + traçabilité Transaction type BILL.
"""
import logging
from decimal import Decimal
from django.db import transaction
from django.core.exceptions import ValidationError

logger = logging.getLogger('apps.bills')
from apps.transactions.money import fmt_bif as _b


@transaction.atomic
def pay_bill(user, biller_code: str, reference_number: str, amount: Decimal, pin: str):
    """Paie une facture depuis le wallet de l'utilisateur."""
    from apps.bills.models import Biller, BillPayment
    from apps.transactions.models import Transaction
    from apps.transactions.services import calculate_fee
    from apps.authentication.services import AuditService, SMSService
    from apps.wallet.models import Wallet

    if amount <= 0:
        raise ValidationError("Le montant doit être positif.")
    if not user.check_pin(pin):
        raise ValidationError("PIN incorrect.")
    if user.is_blocked:
        raise ValidationError("Compte bloqué.")
    try:
        biller = Biller.objects.get(code=biller_code, is_active=True)
    except Biller.DoesNotExist:
        raise ValidationError(f"Fournisseur inconnu : {biller_code}.")
    fee = calculate_fee(amount)
    total = amount + fee
    wallet = Wallet.objects.select_for_update().get(user=user)
    if wallet.balance < total:
        raise ValidationError(f"Solde insuffisant. Requis: {_b(total)}.")
    wallet.balance -= total
    wallet.save(update_fields=['balance'])
    payment = BillPayment.objects.create(
        user=user, biller=biller, reference_number=reference_number, amount=amount
    )
    txn = Transaction.objects.create(
        sender=user, receiver=None, amount=amount, fee=fee,
        transaction_type=Transaction.TransactionType.BILL,
        status=Transaction.Status.SUCCESS,
        description=f"Facture {biller.name} ref {reference_number}",
        metadata={'biller': biller_code, 'bill_ref': reference_number, 'payment_id': payment.id},
    )
    SMSService.send_async(
        user.phone_number,
        f"Swisderm Pay: Facture {biller.name} {_b(amount)} payée. Réf: {reference_number}."
    )
    AuditService.log(user=user, action='BILL_PAID', details={'biller': biller_code, 'amount': str(amount)})
    return txn
