"""
Services interopérabilité (AJOUT SEUL).
Cash Tel ↔ LumiCash / eNoti (Bancobu) / eHela via adaptateurs (mock par défaut).
- interop_send() : Cash Tel → opérateur (débite wallet)
- interop_receive() : opérateur → Cash Tel (demande, créditée au webhook/succès)
- interop_webhook() : callback opérateur, idempotent
"""
import logging
import uuid
from decimal import Decimal
from django.db import transaction
from django.core.exceptions import ValidationError
from django.utils import timezone

logger = logging.getLogger('apps.interop.services')


def _ref(prefix: str) -> str:
    return f"{prefix}-{timezone.now().strftime('%y%m%d')}-{uuid.uuid4().hex[:8].upper()}"


def _get_provider(code: str):
    from .models import ExternalProvider
    try:
        return ExternalProvider.objects.get(code__iexact=code)
    except ExternalProvider.DoesNotExist:
        raise ValidationError(f"Opérateur inconnu : {code}.")


def _provider_fee(provider, amount: Decimal) -> Decimal:
    return (provider.fee_fixed or Decimal('0')) + (
        amount * (provider.fee_percentage or Decimal('0')) / 100).quantize(Decimal('1'))


def split_fee(provider, fee: Decimal) -> tuple:
    """Partage fee selon config opérateur (total 100%). Retourne (provider, platform, agent)."""
    fee = Decimal(str(fee))
    p = Decimal(str(provider.fee_split_provider or 0))
    l = Decimal(str(provider.fee_split_platform or 0))
    a = Decimal(str(provider.fee_split_agent or 0))
    total = p + l + a
    if total <= 0 or fee <= 0:
        return Decimal('0'), Decimal('0'), Decimal('0')
    provider_share = (fee * p / total).quantize(Decimal('1'))
    agent_share = (fee * a / total).quantize(Decimal('1'))
    platform_share = fee - provider_share - agent_share  # résidu -> plateforme, somme exacte
    return provider_share, platform_share, agent_share


@transaction.atomic
def interop_send(user, provider_code: str, external_phone: str, amount: Decimal, pin: str, agent=None):
    """Cash Tel → Lumicash/eNoti(Bancobu)/eHela. agent optionnel : reçoit agent_share sur son compte."""
    from .models import ExternalTransfer
    from .factory import get_provider_adapter
    from apps.wallet.models import Wallet
    from apps.transactions.models import Transaction
    from apps.authentication.services import AuditService, SMSService

    amount = Decimal(str(amount))
    if not user.check_pin(pin):
        raise ValidationError("PIN incorrect.")
    if user.is_blocked:
        raise ValidationError("Compte bloqué.")
    provider = _get_provider(provider_code)
    if provider.status == 'INACTIVE':
        raise ValidationError("Opérateur inactif.")
    if amount < provider.min_transfer or amount > provider.max_transfer:
        raise ValidationError(
            f"Limites {provider.code} : {provider.min_transfer:,.0f}–{provider.max_transfer:,.0f} BIF.")
    fee = _provider_fee(provider, amount)
    wallet = Wallet.objects.select_for_update().get(user=user)
    if wallet.balance < amount + fee:
        raise ValidationError("Solde insuffisant.")
    wallet.balance -= (amount + fee)
    wallet.save(update_fields=['balance'])

    transfer = ExternalTransfer.objects.create(
        reference=_ref('EXT-SND'), user=user, provider=provider,
        external_phone=external_phone, direction=ExternalTransfer.Direction.SEND,
        amount=amount, fee=fee, status=ExternalTransfer.Status.PROCESSING)
    adapter = get_provider_adapter(provider)
    result = adapter.send_money(external_phone, amount, transfer.reference, f"Envoi {user.phone_number}")
    transfer.external_reference = result.external_reference
    transfer.provider_response = result.raw_response
    if not result.success:
        wallet.balance += (amount + fee)  # rembourse
        wallet.save(update_fields=['balance'])
        transfer.status = ExternalTransfer.Status.FAILED
        transfer.error_message = result.message
        transfer.save()
        raise ValidationError(f"{provider.code} : {result.message or 'échec'}. Remboursé.")
    Transaction.objects.create(
        sender=user, receiver=None, amount=amount, fee=fee,
        transaction_type=Transaction.TransactionType.TRANSFER,
        status=Transaction.Status.SUCCESS,
        description=f"Envoi {provider.code} {external_phone}",
        metadata={'provider': provider.code, 'ext_ref': result.external_reference})
    provider_share, platform_share, agent_share = split_fee(provider, fee)
    transfer.status = ExternalTransfer.Status.COMPLETED
    transfer.completed_at = timezone.now()
    transfer.provider_share = provider_share
    transfer.platform_share = platform_share
    transfer.agent_share = agent_share
    if agent is not None:
        from apps.agent.models import AgentProfile
        transfer.agent = agent
        if agent_share > 0:
            prof, _ = AgentProfile.objects.get_or_create(user=agent)
            prof.commission_balance = (prof.commission_balance or Decimal('0')) + agent_share
            prof.save(update_fields=['commission_balance'])
    transfer.save()
    SMSService.send_async(user.phone_number, f"Swisderm Pay: Envoi {provider.code} {amount:,.0f} BIF OK.")
    AuditService.log(user=user, action='INTEROP_SEND',
                     details={'provider': provider.code, 'amount': str(amount), 'fee': str(fee),
                              'provider_share': str(provider_share), 'platform_share': str(platform_share),
                              'agent_share': str(agent_share),
                              'agent': agent.phone_number if agent is not None else ''})
    return transfer


@transaction.atomic
def interop_receive(user, provider_code: str, external_phone: str, amount: Decimal):
    """Opérateur → Cash Tel : crée la demande puis crédite si succès immédiat (mock)."""
    from .models import ExternalTransfer, ReconciliationRecord
    from .factory import get_provider_adapter
    from apps.wallet.models import Wallet
    from apps.transactions.models import Transaction

    amount = Decimal(str(amount))
    provider = _get_provider(provider_code)
    if provider.status == 'INACTIVE':
        raise ValidationError("Opérateur inactif.")
    from apps.banking.float_guard import require_float
    require_float(amount, f"réception {provider.code}")
    transfer = ExternalTransfer.objects.create(
        reference=_ref('EXT-RCV'), user=user, provider=provider,
        external_phone=external_phone, direction=ExternalTransfer.Direction.RECEIVE,
        amount=amount, status=ExternalTransfer.Status.PROCESSING)
    adapter = get_provider_adapter(provider)
    result = adapter.request_money(external_phone, amount, transfer.reference, '')
    transfer.external_reference = result.external_reference
    transfer.provider_response = result.raw_response
    if not result.success:
        transfer.status = ExternalTransfer.Status.FAILED
        transfer.error_message = result.message
        transfer.save()
        raise ValidationError(f"{provider.code} : {result.message or 'échec'}.")
    wallet = Wallet.objects.select_for_update().get(user=user)
    wallet.balance += amount
    wallet.save(update_fields=['balance'])
    Transaction.objects.create(
        sender=None, receiver=user, amount=amount, fee=0,
        transaction_type=Transaction.TransactionType.DEPOSIT,
        status=Transaction.Status.SUCCESS,
        description=f"Réception {provider.code} {external_phone}",
        metadata={'provider': provider.code, 'ext_ref': result.external_reference})
    transfer.status = ExternalTransfer.Status.COMPLETED
    transfer.completed_at = timezone.now()
    transfer.save()
    ReconciliationRecord.objects.create(
        provider=provider, transfer=transfer, internal_amount=amount,
        external_amount=amount, difference=0, status='MATCHED')
    return transfer


def interop_webhook(provider_code: str, payload: dict, raw_body: bytes, signature: str):
    """Callback opérateur (crédit différé). Idempotent sur external_reference."""
    from .models import ExternalTransfer
    from .factory import get_provider_adapter
    provider = _get_provider(provider_code)
    adapter = get_provider_adapter(provider)
    if not adapter.verify_webhook(raw_body, signature or ''):
        raise ValidationError("Signature webhook invalide.")
    ext_ref = payload.get('external_reference') or payload.get('reference') or ''
    if not ext_ref:
        raise ValidationError("Référence manquante.")
    try:
        transfer = ExternalTransfer.objects.get(external_reference=ext_ref)
    except ExternalTransfer.DoesNotExist:
        raise ValidationError("Transfert introuvable.")
    if transfer.status == ExternalTransfer.Status.COMPLETED:
        return transfer
    transfer.status = ExternalTransfer.Status.COMPLETED if payload.get('status') != 'FAILED' else ExternalTransfer.Status.FAILED
    transfer.provider_response = {**(transfer.provider_response or {}), 'webhook': payload}
    if transfer.status == ExternalTransfer.Status.COMPLETED:
        transfer.completed_at = timezone.now()
    transfer.save()
    return transfer


def settlement_report(year: int, month: int) -> list:
    """Rapport mensuel par opérateur : totaux + splits + non reversé."""
    from django.db.models import Count, Sum
    from .models import ExternalTransfer
    qs = ExternalTransfer.objects.filter(
        status=ExternalTransfer.Status.COMPLETED,
        completed_at__year=year, completed_at__month=month)
    rows = qs.values('provider__code', 'provider__name').annotate(
        nb=Count('id'), montant=Sum('amount'), frais=Sum('fee'),
        part_operateur=Sum('provider_share'), part_plateforme=Sum('platform_share'),
        part_agents=Sum('agent_share')).order_by('provider__code')
    return list(rows)


def mark_settled(provider_code: str, year: int, month: int) -> int:
    """Marque reversés les transferts COMPLETED du mois (après virement réel)."""
    from .models import ExternalTransfer
    return ExternalTransfer.objects.filter(
        provider__code__iexact=provider_code,
        status=ExternalTransfer.Status.COMPLETED,
        completed_at__year=year, completed_at__month=month,
        settled=False).update(settled=True)
