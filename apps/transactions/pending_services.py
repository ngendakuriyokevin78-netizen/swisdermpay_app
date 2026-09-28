"""
Circuit transfert EN ATTENTE — AJOUT SEUL (ne modifie rien d'existant).
- process_transfer() et process_qr_transfer() restent intacts = transfert automatique immédiat.
- Ce module réutilise : _validate_transfer_prerequisites, _verify_pin,
  _execute_transfer, _notify_transfer, calculate_fee (importés, non dupliqués).
- Règle validée avec le client : seul l'EXPEDITEUR crée / voit / modifie /
  valide / annule sa ligne PENDING. PIN demandé UNIQUEMENT à la validation.
- Aucune migration : on réutilise Transaction(status=PENDING) puis
  SUCCESS à la validation, FAILED + metadata.cancelled=True à l'annulation.
- Aucun mouvement de solde à la création / modification / annulation.
  Débit/crédit uniquement dans validate_pending_transfer().
"""
import logging
from decimal import Decimal
from django.db import transaction
from django.core.exceptions import ValidationError
from django.utils import timezone

from .models import Transaction
from .services import (
    calculate_fee,
    _validate_transfer_prerequisites,
    _verify_pin,
    _execute_transfer,
    _notify_transfer,
)

logger = logging.getLogger('apps.transactions.pending')

KIND = 'PENDING_P2P'


def _resolve_receiver(receiver_phone: str):
    from apps.authentication.models import User
    try:
        return User.objects.get(phone_number=receiver_phone, is_active=True)
    except User.DoesNotExist:
        raise ValidationError(f"Aucun utilisateur Cash Tel avec le numéro {receiver_phone}.")


def _get_owned_pending(sender, reference: str) -> Transaction:
    try:
        txn = Transaction.objects.select_related('sender', 'receiver').get(
            reference=reference,
            transaction_type=Transaction.TransactionType.TRANSFER,
        )
    except Transaction.DoesNotExist:
        raise ValidationError("Transfert en attente introuvable.")
    if txn.sender_id != sender.id:
        raise ValidationError("Vous n'êtes pas l'expéditeur de ce transfert.")
    if txn.status != Transaction.Status.PENDING:
        raise ValidationError(f"Ce transfert n'est plus modifiable (statut {txn.status}).")
    # Sécurité : seules les lignes créées via ce circuit sont modifiables ici.
    # Les anciens PENDING éventuels sans kind restent visibles mais non valides
    # via ce circuit s'ils n'ont pas de sender (garde-fou).
    if not txn.sender:
        raise ValidationError("Transfert invalide.")
    return txn


def create_pending_transfer(sender, receiver_phone: str, amount: Decimal) -> Transaction:
    """Crée une ligne PENDING sans débiter. PIN non demandé ici."""
    _validate_transfer_prerequisites(sender, amount)
    receiver = _resolve_receiver(receiver_phone)
    if sender.id == receiver.id:
        raise ValidationError("Vous ne pouvez pas vous transférer à vous-même.")

    fee = calculate_fee(amount)

    # Contrôle solde prévisionnel (lecture seule, sans verrou) pour UX.
    try:
        balance = sender.wallet.balance
        if balance < (amount + fee):
            raise ValidationError(
                f"Solde insuffisant pour mettre en attente. Nécessaire : {amount + fee:,.0f} BIF | "
                f"Disponible : {balance:,.0f} BIF"
            )
    except AttributeError:
        pass

    from apps.authentication.services import AuditService
    txn = Transaction.objects.create(
        sender=sender,
        receiver=receiver,
        amount=amount,
        fee=fee,
        transaction_type=Transaction.TransactionType.TRANSFER,
        status=Transaction.Status.PENDING,
        description=f"Transfert en attente de {sender.phone_number} vers {receiver_phone}",
        metadata={
            'kind': KIND,
            'channel': 'APP_ONLINE',
            'created_via': 'pending_create',
            'modifications': 0,
        },
    )
    AuditService.log(user=sender, action='TRANSFER_PENDING_CREATED', details={
        'receiver': receiver_phone, 'amount': str(amount),
        'fee': str(fee), 'reference': str(txn.reference),
    })
    logger.info(f"Pending créé {txn.reference} : {sender.phone_number} -> {receiver_phone} {amount} BIF")
    return txn


def list_pending_transfers(sender):
    """Lignes PENDING de l'expéditeur connecté (pour l'app internet)."""
    from django.db.models import Q
    return Transaction.objects.filter(
        sender=sender,
        transaction_type=Transaction.TransactionType.TRANSFER,
        status=Transaction.Status.PENDING,
    ).select_related('sender', 'receiver').order_by('-created_at')


def validate_pending_transfer(sender, reference: str, pin: str) -> Transaction:
    """Valide = exécute le débit/crédit réel puis passe SUCCESS. PIN ici uniquement."""
    from apps.authentication.services import AuditService

    # Charge la ligne de l'expéditeur puis valide le montant stocké.
    txn = _get_owned_pending(sender, reference)
    _validate_transfer_prerequisites(sender, txn.amount)
    _verify_pin(sender, pin)

    # Recharge le receveur frais (numéro peut avoir été modifié entre-temps)
    from apps.authentication.models import User
    try:
        receiver = User.objects.get(pk=txn.receiver_id, is_active=True)
    except User.DoesNotExist:
        raise ValidationError("Destinataire introuvable ou désactivé.")

    with transaction.atomic():
        # Verrou anti double-validation sur la ligne
        locked = Transaction.objects.select_for_update().get(pk=txn.pk)
        if locked.status != Transaction.Status.PENDING:
            raise ValidationError(f"Déjà traité (statut {locked.status}).")
        fee, _, _ = _execute_transfer(sender, receiver, locked.amount)
        locked.fee = fee
        locked.status = Transaction.Status.SUCCESS
        meta = dict(locked.metadata or {})
        meta.update({'kind': KIND, 'validated_at': timezone.now().isoformat(), 'validated_via': 'pending_validate'})
        locked.metadata = meta
        locked.description = f"Transfert de {sender.phone_number} vers {receiver.phone_number} (validé depuis attente)"
        locked.save(update_fields=['fee', 'status', 'metadata', 'description'])
        txn = locked

    _notify_transfer(sender, receiver, txn.amount, txn.fee, txn.reference)
    AuditService.log(user=sender, action='TRANSFER_PENDING_VALIDATED', details={
        'reference': str(txn.reference), 'amount': str(txn.amount), 'fee': str(txn.fee),
    })
    logger.info(f"Pending validé {txn.reference}")
    return txn


def modify_pending_transfer(sender, reference: str, receiver_phone=None, amount=None) -> Transaction:
    """Modifie montant et/ou destinataire d'une ligne PENDING. Sans PIN, sans débit."""
    from apps.authentication.services import AuditService
    txn = _get_owned_pending(sender, reference)

    changed = {}
    if amount is not None:
        amount = Decimal(str(amount))
        _validate_transfer_prerequisites(sender, amount)
        txn.amount = amount
        txn.fee = calculate_fee(amount)
        changed['amount'] = str(amount)
    if receiver_phone:
        receiver = _resolve_receiver(receiver_phone)
        if sender.id == receiver.id:
            raise ValidationError("Vous ne pouvez pas vous transférer à vous-même.")
        txn.receiver = receiver
        changed['receiver'] = receiver_phone

    if not changed:
        raise ValidationError("Rien à modifier (fournissez receiver_phone et/ou amount).")

    meta = dict(txn.metadata or {})
    meta['modifications'] = int(meta.get('modifications', 0)) + 1
    meta['last_modified_at'] = timezone.now().isoformat()
    txn.metadata = meta
    txn.description = f"Transfert en attente (modifié) de {sender.phone_number} vers {txn.receiver.phone_number}"
    txn.save(update_fields=['amount', 'fee', 'receiver', 'metadata', 'description'])
    AuditService.log(user=sender, action='TRANSFER_PENDING_MODIFIED', details={
        'reference': str(txn.reference), **changed,
    })
    logger.info(f"Pending modifié {txn.reference} : {changed}")
    return txn


def cancel_pending_transfer(sender, reference: str, reason: str = '') -> Transaction:
    """Annule une ligne PENDING -> FAILED + metadata.cancelled. Aucun débit."""
    from apps.authentication.services import AuditService
    from apps.authentication.services import SMSService
    txn = _get_owned_pending(sender, reference)

    txn.status = Transaction.Status.FAILED
    meta = dict(txn.metadata or {})
    meta.update({'kind': KIND, 'cancelled': True,
                 'cancelled_at': timezone.now().isoformat(), 'cancel_reason': reason})
    txn.metadata = meta
    txn.save(update_fields=['status', 'metadata'])
    AuditService.log(user=sender, action='TRANSFER_PENDING_CANCELLED', details={
        'reference': str(txn.reference), 'reason': reason,
    })
    SMSService.send_async(
        sender.phone_number,
        f"Swisderm Pay: Transfert en attente {txn.amount:,.0f} BIF vers "
        f"{txn.receiver.phone_number if txn.receiver else '?'} annulé. Réf: {str(txn.reference)[:8].upper()}"
    )
    logger.info(f"Pending annulé {txn.reference}")
    return txn
