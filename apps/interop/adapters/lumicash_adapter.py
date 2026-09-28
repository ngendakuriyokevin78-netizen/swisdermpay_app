"""
Adaptateur LumiCash — Econet Leo Burundi.

╔══════════════════════════════════════════════════════════════════════════════╗
║  ⚠️  PLACEHOLDER — INTÉGRATION API LUMICASH                                ║
║                                                                            ║
║  LumiCash est le service Mobile Money d'Econet Leo au Burundi.             ║
║  Ce fichier contient la structure complète de l'adaptateur.                ║
║                                                                            ║
║  Pour activer :                                                            ║
║  1. Signer l'accord d'interopérabilité avec Econet Leo / LumiCash         ║
║  2. Obtenir les credentials API (api_key, api_secret, merchant_id)         ║
║  3. Admin → Opérateurs Externes → LUMICASH → adapter_class =              ║
║     "apps.interop.adapters.lumicash_adapter.LumiCashAdapter"               ║
║  4. Remplir api_base_url, api_key, api_secret, merchant_id                ║
║                                                                            ║
║  Documentation API LumiCash : (à obtenir auprès d'Econet Leo)             ║
╚══════════════════════════════════════════════════════════════════════════════╝
"""
import logging
from decimal import Decimal

from .base import BaseProviderAdapter, TransferResult, AccountValidation

logger = logging.getLogger('apps.interop.adapters.lumicash')


class LumiCashAdapter(BaseProviderAdapter):
    """
    Adaptateur API LumiCash (Econet Leo — Burundi).

    Configuration requise dans ExternalProvider :
        - api_base_url  : URL de base API LumiCash (ex: https://api.lumicash.bi/v1)
        - api_key       : Clé API fournie par LumiCash
        - api_secret    : Secret pour la signature des requêtes
        - merchant_id   : Identifiant marchand chez LumiCash
        - webhook_secret: Secret pour vérifier les callbacks LumiCash
    """

    # ── Endpoints API LumiCash (PLACEHOLDER) ─────────────────────────────────
    # ⚠️ À adapter selon la documentation officielle LumiCash
    ENDPOINT_VALIDATE = '/accounts/validate'
    ENDPOINT_SEND = '/transfers/send'
    ENDPOINT_RECEIVE = '/transfers/request'
    ENDPOINT_STATUS = '/transfers/{reference}/status'

    def validate_account(self, phone_number: str) -> AccountValidation:
        """
        ⚠️ PLACEHOLDER — Vérifie un numéro LumiCash.

        TODO: Implémenter avec l'API LumiCash :
        POST {api_base_url}/accounts/validate
        Body: {"phone_number": "+25762..."}
        """
        logger.warning(
            f"[LUMICASH PLACEHOLDER] validate_account({phone_number}) — "
            "API LumiCash non configurée"
        )

        # ⚠️ REMPLACER par l'appel API réel :
        #
        # import requests
        # response = requests.post(
        #     f"{self.api_base_url}{self.ENDPOINT_VALIDATE}",
        #     headers={
        #         'Authorization': f'Bearer {self.api_key}',
        #         'X-Merchant-ID': self.merchant_id,
        #     },
        #     json={'phone_number': phone_number}
        # )
        # data = response.json()
        # return AccountValidation(
        #     phone_number=phone_number,
        #     account_name=data.get('name', ''),
        #     is_valid=data.get('registered', False),
        #     raw_response=data,
        # )

        return AccountValidation(
            phone_number=phone_number,
            account_name='[LumiCash — Vérification non disponible]',
            is_valid=True,
            raw_response={'placeholder': True},
        )

    def send_money(
        self, destination_phone: str, amount: Decimal,
        reference: str, description: str = ''
    ) -> TransferResult:
        """
        ⚠️ PLACEHOLDER — Envoie de l'argent vers LumiCash.

        Flux : Wallet Cash Tel → Compte LumiCash du destinataire

        TODO: Implémenter avec l'API LumiCash :
        POST {api_base_url}/transfers/send
        Body: {
            "destination": "+25762...",
            "amount": "5000",
            "currency": "BIF",
            "reference": "CT-xxx",
            "description": "Envoi Cash Tel",
            "callback_url": "https://votre-domaine/api/interop/webhooks/lumicash/"
        }
        """
        logger.warning(
            f"[LUMICASH PLACEHOLDER] send_money("
            f"dest={destination_phone}, amount={amount} BIF, ref={reference})"
        )

        return TransferResult(
            success=True,
            external_reference=f'LUMI-MOCK-{reference[:8]}',
            message='[PLACEHOLDER] Envoi LumiCash simulé',
            raw_response={'placeholder': True, 'amount': str(amount)},
        )

    def request_money(
        self, source_phone: str, amount: Decimal,
        reference: str, description: str = ''
    ) -> TransferResult:
        """
        ⚠️ PLACEHOLDER — Reçoit de l'argent depuis LumiCash.

        Flux : Compte LumiCash de l'expéditeur → Wallet Cash Tel

        TODO: Implémenter avec l'API LumiCash
        """
        logger.warning(
            f"[LUMICASH PLACEHOLDER] request_money("
            f"source={source_phone}, amount={amount} BIF, ref={reference})"
        )

        return TransferResult(
            success=True,
            external_reference=f'LUMI-MOCK-{reference[:8]}',
            message='[PLACEHOLDER] Réception LumiCash simulée',
            raw_response={'placeholder': True, 'amount': str(amount)},
        )

    def check_status(self, external_reference: str) -> TransferResult:
        """
        ⚠️ PLACEHOLDER — Vérifie le statut d'un transfert LumiCash.

        TODO: GET {api_base_url}/transfers/{external_reference}/status
        """
        logger.warning(
            f"[LUMICASH PLACEHOLDER] check_status({external_reference})"
        )

        return TransferResult(
            success=True,
            external_reference=external_reference,
            message='[PLACEHOLDER] Statut simulé — complété',
            raw_response={'placeholder': True, 'status': 'completed'},
        )

    def verify_webhook(self, payload: bytes, signature: str) -> bool:
        """
        ⚠️ PLACEHOLDER — Vérifie la signature webhook LumiCash.

        TODO: Implémenter selon la méthode de signature LumiCash
        """
        logger.warning("[LUMICASH PLACEHOLDER] verify_webhook — non implémenté")
        return False
