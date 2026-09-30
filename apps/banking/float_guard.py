"""
Garde-fou float cantonné (AJOUT SEUL).
Règle : somme(Wallet.balance) + nouveau_montant <= somme(BankFloat.ceiling).
Sans plafond déclaré -> émission bloquée (fail-safe).
À appeler dans TOUS les chemins qui CRÉENT de l'e-money :
  bank_deposit, agent cashin, interop_receive.
Les transferts internes (P2P, scan-pay, cashout) ne créent rien -> pas de garde.
"""
import logging
from decimal import Decimal
from django.core.exceptions import ValidationError
from django.db.models import Sum

logger = logging.getLogger('apps.banking.float')
from apps.transactions.money import fmt_bif as _b


def get_total_emoney() -> Decimal:
    from apps.wallet.models import Wallet
    total = Wallet.objects.aggregate(s=Sum('balance'))['s']
    return total or Decimal('0')


def get_total_ceiling() -> Decimal:
    from .models import BankFloat
    total = BankFloat.objects.aggregate(s=Sum('ceiling'))['s']
    return total or Decimal('0')


def float_status() -> dict:
    total = get_total_emoney()
    ceiling = get_total_ceiling()
    return {
        'total_emoney': str(total),
        'ceiling': str(ceiling),
        'available': str(ceiling - total),
        'healthy': total <= ceiling,
    }


def require_float(amount: Decimal, label: str = 'émission'):
    """Lève ValidationError si l'émission dépasserait le float. Appel interne."""
    amount = Decimal(str(amount))
    st = float_status()
    total, ceiling = Decimal(st['total_emoney']), Decimal(st['ceiling'])
    if ceiling <= 0:
        raise ValidationError(
            "Émission bloquée : aucun plafond cantonné déclaré. "
            "Admin → Plafonds cantonnés → déclarez ex: CRDB 1000000.")
    if total + amount > ceiling:
        raise ValidationError(
            f"Émission refusée ({label} {_b(amount)}) : "
            f"total {_b(total)} + {_b(amount)} dépasserait le plafond {_b(ceiling)}. "
            f"Disponible : {_b((ceiling - total))}.")
    logger.info(f"Float OK : {_b(total)} + {_b(amount)} <= {_b(ceiling)}")
