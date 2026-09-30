"""
Format monétaire français — AJOUT SEUL.
- fmt_bif() : notation française, virgule décimale, max 3 décimales, SANS arrondi.
  Ex : 12500.5 -> "12 500,5 BIF" ; 200 -> "200 BIF".
- L'affichage tronque à 3 décimales (ROUND_DOWN) ; le calcul/stock garde la valeur exacte.
"""
from decimal import Decimal, ROUND_DOWN


def _as_decimal(value) -> Decimal:
    if isinstance(value, Decimal):
        return value
    try:
        return Decimal(str(value))
    except Exception:
        return Decimal('0')


def fmt_bif(value) -> str:
    """'12 500,5 BIF' — espaces milliers, virgule décimale, SANS arrondi."""
    d = _as_decimal(value).quantize(Decimal('0.001'), rounding=ROUND_DOWN)
    sign = '-' if d < 0 else ''
    d = abs(d)
    ent = int(d)
    cents = int((d - ent) * 1000)
    ent_txt = f"{ent:,}".replace(',', ' ')
    if cents == 0:
        return f"{sign}{ent_txt} BIF"
    dec_txt = f"{cents:03d}".rstrip('0')
    return f"{sign}{ent_txt},{dec_txt} BIF"


def fmt_num(value) -> str:
    """Nombre français sans unité : '12 500,5'."""
    return fmt_bif(value).replace(' BIF', '')
