"""
Utilitaire téléphone Burundi — AJOUT SEUL (aucune logique existante modifiée).
- Normalisation +257XXXXXXXX
- Détection opérateur (Lumitel/Viettel recommandé, sans bloquer les autres)
Réf ARCT 2023 : Lumitel = 61, 62, 65, 66, 67, 68, 69 (+64 récent).
"""

LUMITEL_PREFIXES = ('61', '62', '64', '65', '66', '67', '68', '69')
ECONET_PREFIXES = ('71', '72', '76', '79')
ONATEL_PREFIXES = ('77',)

LUMITEL_RECOMMENDATION = (
    "Numéro Lumitel (Viettel) recommandé : préfixes 61, 62, 64-69. "
    "Idéal pour OTP rapides et LumiCash. Les autres opérateurs +257 restent acceptés."
)


def normalize_phone(raw: str) -> str:
    """Nettoie et normalise vers +257XXXXXXXX. Lève ValueError si invalide."""
    if raw is None:
        raise ValueError('Numéro requis.')
    cleaned = str(raw).replace(' ', '').replace('-', '').replace('.', '')
    if cleaned.startswith('+'):
        pass
    elif cleaned.startswith('00257'):
        cleaned = '+' + cleaned[2:]
    elif cleaned.startswith('257') and len(cleaned) >= 11:
        cleaned = '+' + cleaned
    elif cleaned.startswith('0') and len(cleaned) == 9:
        # 06XXXXXXXX local -> +2576XXXXXXXX
        cleaned = '+257' + cleaned[1:]
    elif len(cleaned) == 8 and cleaned[:2] in (
        LUMITEL_PREFIXES + ECONET_PREFIXES + ONATEL_PREFIXES
    ):
        cleaned = '+257' + cleaned
    elif not cleaned.startswith('+'):
        cleaned = '+257' + cleaned.lstrip('0')
    # Validation finale : +257 + 8 chiffres
    digits = cleaned.replace('+', '')
    if not digits.isdigit() or not cleaned.startswith('+257') or len(cleaned) != 12:
        raise ValueError('Numéro invalide. Format attendu : +25761XXXXXX (8 chiffres après +257).')
    return cleaned


def operator_of(phone: str) -> str:
    """Retourne LUMITEL / ECONET / ONATEL / AUTRE / INCONNU (jamais d'exception)."""
    try:
        p = normalize_phone(phone)
    except Exception:
        return 'INCONNU'
    prefix = p[4:6]
    if prefix in LUMITEL_PREFIXES:
        return 'LUMITEL'
    if prefix in ECONET_PREFIXES:
        return 'ECONET'
    if prefix in ONATEL_PREFIXES:
        return 'ONATEL'
    return 'AUTRE'


def is_lumitel(phone: str) -> bool:
    return operator_of(phone) == 'LUMITEL'
