"""
Services métier pour les transactions Cash Tel.
Contient :
- calculate_fee() : moteur de calcul des frais par tranche
- process_transfer() : transfert P2P atomique (par numéro)
- process_qr_transfer() : transfert par scan QR Code
"""
import logging
from decimal import Decimal
from django.db import transaction
from django.core.exceptions import ValidationError
from django.conf import settings

from .models import Fee, Transaction

logger = logging.getLogger('apps.transactions')


# ── Moteur de Frais ───────────────────────────────────────────────────────────

def calculate_fee(amount: Decimal) -> Decimal:
    """
    Calcule les frais pour un montant donné en BIF.
    Cherche la tranche active correspondante dans la table Fee.

    Retourne 0 si aucune tranche ne correspond.
    """
    try:
        fee_config = Fee.objects.filter(
            is_active=True,
            min_amount__lte=amount,
            max_amount__gte=amount
        ).first()

        if not fee_config:
            logger.warning(f"Aucune tranche de frais pour {amount} BIF")
            return Decimal('0')

        if fee_config.fee_type == Fee.FeeType.FIXED:
            return fee_config.fee_value
        else:  # PERCENTAGE
            fee = (amount * fee_config.fee_value / 100).quantize(Decimal('1'))
            return fee

    except Exception as e:
        logger.error(f"Erreur calcul frais : {e}")
        return Decimal('0')


# ── Validation commune ────────────────────────────────────────────────────────

def _validate_transfer_prerequisites(sender, amount: Decimal):
    """
    Vérifie les prérequis communs avant tout transfert :
    - Compte non bloqué
    - Montant minimum respecté
    """
    if sender.is_blocked:
        raise ValidationError("Votre compte est bloqué. Contactez le support Cash Tel.")

    min_amount = Decimal(str(settings.MIN_TRANSFER_AMOUNT))
    if amount < min_amount:
        raise ValidationError(f"Montant minimum de transfert : {min_amount:,.0f} BIF")

    if amount <= 0:
        raise ValidationError("Le montant doit être positif.")


def _verify_pin(sender, pin: str):
    """
    Vérifie le PIN de l'expéditeur.
    Incrémente les échecs et bloque le compte si MAX_PIN_ATTEMPTS atteint.
    Lève ValidationError en cas d'échec.
    """
    from apps.wallet.models import Wallet

    if not sender.check_pin(pin):
        sender.failed_pin_attempts += 1
        max_attempts = settings.MAX_PIN_ATTEMPTS

        # Trace intrusion/vol (ajout seul, ne change pas le flux)
        try:
            from apps.authentication.services import AuditService as _Audit
            _Audit.log(user=sender, action='PIN_FAILED',
                       details={'phone': getattr(sender, 'phone_number', '')})
            if sender.failed_pin_attempts >= max_attempts:
                _Audit.log(user=sender, action='ACCOUNT_BLOCKED',
                           details={'reason': 'pin_transfer'})
        except Exception:
            pass

        if sender.failed_pin_attempts >= max_attempts:
            sender.is_blocked = True
            # Geler le wallet
            try:
                sender.wallet.status = Wallet.Status.FROZEN
                sender.wallet.save(update_fields=['status'])
            except Wallet.DoesNotExist:
                pass
            sender.save(update_fields=['failed_pin_attempts', 'is_blocked'])
            raise ValidationError(
                f"Compte bloqué après {max_attempts} tentatives de PIN incorrectes."
            )

        tentatives_restantes = max_attempts - sender.failed_pin_attempts
        sender.save(update_fields=['failed_pin_attempts'])
        raise ValidationError(
            f"PIN incorrect. {tentatives_restantes} tentative(s) restante(s)."
        )

    # PIN correct : réinitialise le compteur
    if sender.failed_pin_attempts > 0:
        sender.failed_pin_attempts = 0
        sender.save(update_fields=['failed_pin_attempts'])


def _execute_transfer(sender, receiver, amount: Decimal) -> tuple:
    """
    Exécute le débit/crédit atomique entre deux wallets.
    Retourne (fee, sender_wallet, receiver_wallet).
    Utilise SELECT FOR UPDATE pour éviter la double dépense.
    """
    from apps.wallet.models import Wallet

    fee = calculate_fee(amount)
    total_debit = amount + fee

    # Verrou sur les deux wallets (ordre déterministe par wallet_id)
    wallet_ids = sorted([sender.wallet.id, receiver.wallet.id])
    wallets = {w.id: w for w in Wallet.objects.select_for_update().filter(id__in=wallet_ids)}

    sender_wallet = wallets[sender.wallet.id]
    receiver_wallet = wallets[receiver.wallet.id]

    # Vérification statuts
    if sender_wallet.status != Wallet.Status.ACTIVE:
        raise ValidationError(f"Votre wallet est {sender_wallet.get_status_display().lower()}.")
    if receiver_wallet.status == Wallet.Status.SUSPENDED:
        raise ValidationError("Le wallet destinataire est suspendu.")

    # Vérification solde
    if sender_wallet.balance < total_debit:
        raise ValidationError(
            f"Solde insuffisant. Nécessaire : {total_debit:,.0f} BIF | "
            f"Disponible : {sender_wallet.balance:,.0f} BIF"
        )

    # Débit expéditeur / Crédit destinataire
    sender_wallet.balance -= total_debit
    receiver_wallet.balance += amount
    sender_wallet.save(update_fields=['balance'])
    receiver_wallet.save(update_fields=['balance'])

    return fee, sender_wallet, receiver_wallet


def _notify_transfer(sender, receiver, amount: Decimal, fee: Decimal, reference):
    """Envoie les SMS de notification de manière asynchrone."""
    from apps.authentication.services import SMSService
    SMSService.send_async(
        sender.phone_number,
        f"Swisderm Pay: Envoi {amount:,.0f} BIF à {receiver.get_full_name()}. "
        f"Frais: {fee:,.0f} BIF. Réf: {str(reference)[:8].upper()}"
    )
    SMSService.send_async(
        receiver.phone_number,
        f"Swisderm Pay: Reçu {amount:,.0f} BIF de {sender.get_full_name()}. "
        f"Réf: {str(reference)[:8].upper()}"
    )


# ── Transfert P2P par Numéro ──────────────────────────────────────────────────

def process_transfer(sender, receiver_phone: str, amount: Decimal, pin: str) -> Transaction:
    """
    Effectue un transfert P2P de manière atomique.
    Le PIN est vérifié HORS transaction pour que les échecs persistent
    même si le transfert échoue (évite rollback du compteur).
    Seul débit/crédit + création sont atomiques.
    """
    from apps.authentication.models import User
    from apps.authentication.services import AuditService

    _validate_transfer_prerequisites(sender, amount)
    _verify_pin(sender, pin)

    # Résolution destinataire
    try:
        receiver = User.objects.get(phone_number=receiver_phone, is_active=True)
    except User.DoesNotExist:
        raise ValidationError(f"Aucun utilisateur Cash Tel avec le numéro {receiver_phone}.")

    if sender.id == receiver.id:
        raise ValidationError("Vous ne pouvez pas vous transférer à vous-même.")

    with transaction.atomic():
        # Exécution atomique
        fee, _, _ = _execute_transfer(sender, receiver, amount)

        # Enregistrement en base
        txn = Transaction.objects.create(
            sender=sender,
            receiver=receiver,
            amount=amount,
            fee=fee,
            transaction_type=Transaction.TransactionType.TRANSFER,
            status=Transaction.Status.SUCCESS,
            description=f"Transfert de {sender.phone_number} vers {receiver.phone_number}",
        )

    # Notifications + audit
    _notify_transfer(sender, receiver, amount, fee, txn.reference)
    AuditService.log(
        user=sender,
        action='TRANSFER_SENT',
        details={
            'receiver': receiver_phone,
            'amount': str(amount),
            'fee': str(fee),
            'reference': str(txn.reference),
        }
    )

    logger.info(
        f"Transfert réussi: {sender.phone_number} → {receiver_phone} "
        f"| {amount} BIF (frais: {fee} BIF) | ref: {txn.reference}"
    )
    return txn


# ── Transfert par QR Code ─────────────────────────────────────────────────────

def process_qr_transfer(sender, qr_data: str, amount: Decimal = None, pin: str = '') -> Transaction:
    """
    Transfert par scan QR SwisdermPay.

    Formats acceptés :
      SWISDERMPAY:{wallet_id}:{phone}:{montant} (montant OBLIGATOIRE)
    Les QR sans montant (ancien format à 3 parties) sont REFUSÉS.
    """
    from apps.wallet.models import Wallet

    # Parsing du QR Code : 4 parties exigées, montant intégré obligatoire
    try:
        parts = qr_data.strip().split(':')
        if len(parts) != 4 or parts[0] not in ('SWISDERMPAY', 'CASHTEL'):
            raise ValueError
        _, wallet_id_str, receiver_phone = parts[0], parts[1], parts[2]
        embedded = Decimal(parts[3])
        if embedded <= 0:
            raise ValueError
    except (ValueError, IndexError):
        raise ValidationError(
            "QR sans montant refusé. Régénérez un QR avec montant "
            "(SWISDERMPAY:{wallet_id}:{phone}:{montant})."
        )

    if amount is not None:
        amount = Decimal(str(amount))
    final_amount = embedded
    if amount is not None and embedded != amount:
        raise ValidationError(
            f"Montant QR ({embedded:,.0f}) différent du montant saisi ({amount:,.0f}).")

    # Vérification cohérence wallet_id / téléphone
    try:
        target_wallet = Wallet.objects.get(wallet_id=wallet_id_str)
    except (Wallet.DoesNotExist, Exception):
        raise ValidationError("Wallet QR introuvable. QR Code peut-être expiré.")

    if target_wallet.user.phone_number != receiver_phone:
        raise ValidationError("QR Code invalide : incohérence wallet/téléphone.")

    # Délégation au transfert standard
    return process_transfer(
        sender=sender,
        receiver_phone=receiver_phone,
        amount=final_amount,
        pin=pin
    )


# ── Historique transactions ───────────────────────────────────────────────────

def get_user_transactions(user):
    """Retourne toutes les transactions de l'utilisateur (envoyées + reçues)."""
    from django.db.models import Q
    return Transaction.objects.filter(
        Q(sender=user) | Q(receiver=user)
    ).select_related('sender', 'receiver').order_by('-created_at')


def reverse_transfer(actor, reference: str, reason: str = ''):
    """
    REMBOURSEMENT après erreur de numéro (AJOUT SEUL).
    Réservé ADMIN : restitue le MONTANT au compte d'origine.
    - Seul un TRANSFER SUCCESS non déjà remboursé.
    - Les frais restent acquis à la plateforme (affiché clairement).
    - Atomique : débit destinataire + crédit expéditeur + 2 écritures.
    """
    from apps.authentication.services import AuditService, SMSService
    from apps.wallet.models import Wallet

    try:
        original = Transaction.objects.select_related('sender', 'receiver').get(reference=reference)
    except Transaction.DoesNotExist:
        raise ValidationError("Transaction introuvable.")
    if original.transaction_type != Transaction.TransactionType.TRANSFER:
        raise ValidationError("Seul un transfert P2P peut être remboursé.")
    if original.status != Transaction.Status.SUCCESS:
        raise ValidationError("Seul un transfert réussi peut être remboursé.")
    if original.metadata.get('reversed'):
        raise ValidationError("Déjà remboursé.")
    if not original.sender or not original.receiver:
        raise ValidationError("Parties manquantes.")

    with transaction.atomic():
        wallets = {w.id: w for w in Wallet.objects.select_for_update().filter(
            id__in=[original.sender.wallet.id, original.receiver.wallet.id])}
        dest_wallet = wallets[original.receiver.wallet.id]  # celui qui a reçu par erreur
        orig_wallet = wallets[original.sender.wallet.id]
        if dest_wallet.balance < original.amount:
            raise ValidationError(
                f"Remboursement impossible : le destinataire a déjà dépensé. "
                f"Solde {dest_wallet.balance:,.0f} < {original.amount:,.0f} BIF.")
        dest_wallet.balance -= original.amount
        orig_wallet.balance += original.amount
        dest_wallet.save(update_fields=['balance'])
        orig_wallet.save(update_fields=['balance'])

        compensation = Transaction.objects.create(
            sender=original.receiver, receiver=original.sender,
            amount=original.amount, fee=0,
            transaction_type=Transaction.TransactionType.TRANSFER,
            status=Transaction.Status.SUCCESS,
            description=f"Remboursement erreur numéro (ref {str(original.reference)[:8].upper()})",
            metadata={'kind': 'REFUND', 'reverses': str(original.reference), 'reason': reason},
        )
        original.status = Transaction.Status.REVERSED
        meta = dict(original.metadata or {})
        meta.update({'reversed': True, 'refund_ref': str(compensation.reference), 'reason': reason})
        original.metadata = meta
        original.save(update_fields=['status', 'metadata'])

    SMSService.send_async(
        original.sender.phone_number,
        f"Swisderm Pay: Remboursement {original.amount:,.0f} BIF reçu (erreur numéro).")
    SMSService.send_async(
        original.receiver.phone_number,
        f"Swisderm Pay: {original.amount:,.0f} BIF prélevés pour remboursement (erreur numéro).")
    AuditService.log(user=actor, action='TRANSFER_REVERSED',
                     details={'reference': str(original.reference), 'reason': reason})
    logger.info(f"Remboursement {original.reference} par {actor.phone_number}")
    return compensation
