"""
Adaptateur eNoti (Bancobu) — Service Mobile Money Burundi.

╔══════════════════════════════════════════════════════════════════════════════╗
║  ⚠️  PLACEHOLDER — INTÉGRATION API ENOTI (BANCOBU)                           ║
║                                                                            ║
║  eNoti est le service de paiement mobile de Bancobu (Burundi).              ║
║                                                                            ║
║  Pour activer :                                                            ║
║  1. Signer l'accord d'interopérabilité avec Bancobu                        ║
║  2. Obtenir les credentials API (api_key, api_secret, merchant_id)         ║
║  3. Admin → Opérateurs Externes → ENOTI → adapter_class =                  ║
║     "apps.interop.adapters.enoti_adapter.EnotiAdapter"                      ║
║  4. Remplir api_base_url, api_key, api_secret, merchant_id                 ║
║                                                                            ║
║  Documentation API eNoti : (à obtenir auprès de Bancobu)                   ║
╚══════════════════════════════════════════════════════════════════════════════╝
"""
import logging
from decimal import Decimal

from .base import BaseProviderAdapter, TransferResult, AccountValidation

logger = logging.getLogger('apps.interop.adapters.enoti')


class EnotiAdapter(BaseProviderAdapter):
    """
    Adaptateur API eNoti / Bancobu (Burundi).

    Configuration requise dans ExternalProvider :
        - api_base_url  : URL de base API eNoti
        - api_key       : Clé API fournie par Bancobu
        - api_secret    : Secret API
        - merchant_id   : Identifiant marchand chez Bancobu
        - webhook_secret: Secret pour vérifier les callbacks
    """

    # ── Endpoints API eNoti (PLACEHOLDER) ────────────────────────────────────
    # ⚠️ À adapter selon la documentation officielle Bancobu eNoti
    ENDPOINT_VALIDATE = '/api/account/verify'
    ENDPOINT_SEND = '/api/payment/send'
    ENDPOINT_RECEIVE = '/api/payment/collect'
    ENDPOINT_STATUS = '/api/payment/status'

    def validate_account(self, phone_number: str) -> AccountValidation:
        """
        ⚠️ PLACEHOLDER — Vérifie un numéro eNoti (Bancobu).

        TODO: Implémenter avec l'API eNoti :
        POST {api_base_url}/api/account/verify
        """
        logger.warning(
            f"[ENOTI PLACEHOLDER] validate_account({phone_number}) — "
            "API eNoti non configurée"
        )

        # ⚠️ REMPLACER par l'appel API réel

        return AccountValidation(
            phone_number=phone_number,
            account_name='[eNoti — Vérification non disponible]',
            is_valid=True,
            raw_response={'placeholder': True},
        )

    def send_money(
        self, destination_phone: str, amount: Decimal,
        reference: str, description: str = ''
    ) -> TransferResult:
        """
        ⚠️ PLACEHOLDER — Envoie de l'argent vers eNoti (Bancobu).

        Flux : Wallet Cash Tel → Compte eNoti du destinataire

        TODO: Implémenter avec l'API eNoti :
        POST {api_base_url}/api/payment/send
        Body: {
            "recipient": "+25762...",
            "amount": 5000,
            "currency": "BIF",
            "external_ref": "CT-xxx",
            "narration": "Envoi Cash Tel",
            "callback": "https://votre-domaine/api/interop/webhooks/enoti/"
        }
        """
        logger.warning(
            f"[ENOTI PLACEHOLDER] send_money("
            f"dest={destination_phone}, amount={amount} BIF, ref={reference})"
        )

        return TransferResult(
            success=True,
            external_reference=f'ENOTI-MOCK-{reference[:8]}',
            message='[PLACEHOLDER] Envoi eNoti simulé',
            raw_response={'placeholder': True, 'amount': str(amount)},
        )

    def request_money(
        self, source_phone: str, amount: Decimal,
        reference: str, description: str = ''
    ) -> TransferResult:
        """
        ⚠️ PLACEHOLDER — Reçoit de l'argent depuis eNoti (Bancobu).

        TODO: Implémenter avec l'API eNoti
        """
        logger.warning(
            f"[ENOTI PLACEHOLDER] request_money("
            f"source={source_phone}, amount={amount} BIF, ref={reference})"
        )

        return TransferResult(
            success=True,
            external_reference=f'ENOTI-MOCK-{reference[:8]}',
            message='[PLACEHOLDER] Réception eNoti simulée',
            raw_response={'placeholder': True, 'amount': str(amount)},
        )

    def check_status(self, external_reference: str) -> TransferResult:
        """
        ⚠️ PLACEHOLDER — Vérifie le statut d'un transfert eNoti.

        TODO: GET/POST {api_base_url}/api/payment/status
        """
        logger.warning(
            f"[ENOTI PLACEHOLDER] check_status({external_reference})"
        )

        return TransferResult(
            success=True,
            external_reference=external_reference,
            message='[PLACEHOLDER] Statut simulé — complété',
            raw_response={'placeholder': True, 'status': 'completed'},
        )

    def verify_webhook(self, payload: bytes, signature: str) -> bool:
        """
        ⚠️ PLACEHOLDER — Vérifie la signature webhook eNoti.

        TODO: Implémenter selon la méthode de signature Bancobu
        """
        logger.warning("[ENOTI PLACEHOLDER] verify_webhook — non implémenté")
        return False


# Alias de compatibilité (anciennes lignes DB pointant vers EnofiAdapter)
EnofiAdapter = EnotiAdapter
