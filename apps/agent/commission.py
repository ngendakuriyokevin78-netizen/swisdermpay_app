"""
Commission agent visible + réclamable (AJOUT SEUL).
- get_commission_overview() : soldes + historique des gains
- claim_commission() : transfère commission_balance -> wallet (atomique)
Sources : cashout/withdraw (metadata.commission), interop agent_share crédité.
"""
import logging
from decimal import Decimal
from django.db import transaction
from django.core.exceptions import ValidationError

logger = logging.getLogger('apps.agent.commission')


def get_commission_overview(agent_user: dict) -> dict:
    from django.db.models import Q, Sum
    from .models import AgentProfile
    from apps.transactions.models import Transaction
    from apps.interop.models import ExternalTransfer

    try:
        profile = agent_user.agent_profile
        commission_balance = profile.commission_balance
    except Exception:
        commission_balance = Decimal('0')
    try:
        wallet_balance = agent_user.wallet.balance
    except Exception:
        wallet_balance = Decimal('0')

    history = []
    txns = Transaction.objects.filter(
        Q(receiver=agent_user, transaction_type='WITHDRAWAL') |
        Q(metadata__agent=agent_user.phone_number)
    ).order_by('-created_at')[:20]
    for t in txns:
        meta = t.metadata or {}
        history.append({
            'date': t.created_at,
            'type': 'cashout' if t.receiver_id == agent_user.id else 'opération',
            'amount': str(t.amount),
            'commission': str(meta.get('commission', '0')),
            'reference': str(t.reference),
        })
    facilitated = ExternalTransfer.objects.filter(
        agent=agent_user, status='COMPLETED').order_by('-completed_at')[:20]
    for e in facilitated:
        history.append({
            'date': e.completed_at or e.initiated_at,
            'type': f"interop {e.provider.code}",
            'amount': str(e.amount),
            'commission': str(e.agent_share),
            'reference': e.reference,
        })
    pool = ExternalTransfer.objects.filter(
        agent__isnull=True, status='COMPLETED').aggregate(s=Sum('agent_share'))['s'] or Decimal('0')
    return {
        'commission_balance': str(commission_balance),
        'wallet_balance': str(wallet_balance),
        'pool_agents_non_attribue': str(pool),
        'history': sorted(history, key=lambda h: str(h['date']), reverse=True)[:20],
    }


@transaction.atomic
def claim_commission(agent_user, amount: Decimal = None):
    """Transfère tout ou partie de commission_balance vers le wallet agent."""
    from .models import AgentProfile
    from apps.wallet.models import Wallet
    from apps.authentication.services import AuditService

    profile, _ = AgentProfile.objects.select_for_update().get_or_create(user=agent_user)
    balance = profile.commission_balance or Decimal('0')
    if balance <= 0:
        raise ValidationError("Aucune commission à récupérer.")
    if amount is None:
        amount = balance
    amount = Decimal(str(amount))
    if amount <= 0 or amount > balance:
        raise ValidationError("Montant invalide.")
    wallet = Wallet.objects.select_for_update().get(user=agent_user)
    if wallet.status != Wallet.Status.ACTIVE:
        raise ValidationError("Wallet non actif.")
    profile.commission_balance = balance - amount
    profile.save(update_fields=['commission_balance'])
    wallet.balance = (wallet.balance or Decimal('0')) + amount
    wallet.save(update_fields=['balance'])
    AuditService.log(user=agent_user, action='COMMISSION_CLAIMED',
                     details={'amount': str(amount)})
    logger.info(f"Commission {amount} BIF réclamée par {agent_user.phone_number}")
    return amount, profile.commission_balance, wallet.balance
