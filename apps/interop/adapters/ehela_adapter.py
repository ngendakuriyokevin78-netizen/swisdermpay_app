"""
Adaptateur eHela — Service de transfert IMTO Burundi.

╔══════════════════════════════════════════════════════════════════════════════╗
║  ⚠️  PLACEHOLDER — INTÉGRATION API EHELA                                   ║
║                                                                            ║
║  eHela est un service de paiement mobile / IMTO au Burundi.               ║
║                                                                            ║
║  Pour activer :                                                            ║
║  1. Signer l'accord d'interopérabilité avec eHela                         ║
║  2. Obtenir les credentials API (api_key, api_secret, merchant_id)         ║
║  3. Admin → Opérateurs Externes → EHELA → adapter_class =                 ║
║     "apps.interop.adapters.ehela_adapter.EhelaAdapter"                     ║
║  4. Remplir api_base_url, api_key, api_secret, merchant_id                ║
║                                                                            ║
║  Documentation API eHela : (à obtenir auprès d'eHela / IMTO)             ║
╚══════════════════════════════════════════════════════════════════════════════╝
"""
import logging
from decimal import Decimal

from .base import BaseProviderAdapter, TransferResult, AccountValidation

logger = logging.getLogger('apps.interop.adapters.ehela')


class EhelaAdapter(BaseProviderAdapter):
    """
    Adaptateur API eHela (IMTO — Burundi).

    Configuration requise dans ExternalProvider :
        - api_base_url  : URL de base API eHela
        - api_key       : Clé API fournie par eHela
        - api_secret    : Secret API
        - merchant_id   : Identifiant marchand chez eHela
        - webhook_secret: Secret pour vérifier les callbacks
    """

    # ── Endpoints API eHela (PLACEHOLDER) ────────────────────────────────────
    # ⚠️ À adapter selon la documentation officielle eHela
    ENDPOINT_VALIDATE = '/v1/account/lookup'
    ENDPOINT_SEND = '/v1/remittance/send'
    ENDPOINT_RECEIVE = '/v1/collection/initiate'
    ENDPOINT_STATUS = '/v1/transaction/status'

    def validate_account(self, phone_number: str) -> AccountValidation:
        """
        ⚠️ PLACEHOLDER — Vérifie un numéro eHela.

        TODO: Implémenter avec l'API eHela :
        POST {api_base_url}/v1/account/lookup
        """
        logger.warning(
            f"[EHELA PLACEHOLDER] validate_account({phone_number}) — "
            "API eHela non configurée"
        )

        # ⚠️ REMPLACER par l'appel API réel

        return AccountValidation(
            phone_number=phone_number,
            account_name='[eHela — Vérification non disponible]',
            is_valid=True,
            raw_response={'placeholder': True},
        )

    def send_money(
        self, destination_phone: str, amount: Decimal,
        reference: str, description: str = ''
    ) -> TransferResult:
        """
        ⚠️ PLACEHOLDER — Envoie de l'argent vers eHela.

        Flux : Wallet Cash Tel → Compte eHela du destinataire

        TODO: Implémenter avec l'API eHela :
        POST {api_base_url}/v1/remittance/send
        Body: {
            "beneficiary_msisdn": "+25762...",
            "amount": "5000",
            "currency": "BIF",
            "partner_ref": "CT-xxx",
            "purpose": "Envoi Cash Tel",
            "webhook_url": "https://votre-domaine/api/interop/webhooks/ehela/"
        }
        """
        logger.warning(
            f"[EHELA PLACEHOLDER] send_money("
            f"dest={destination_phone}, amount={amount} BIF, ref={reference})"
        )

        return TransferResult(
            success=True,
            external_reference=f'EHELA-MOCK-{reference[:8]}',
            message='[PLACEHOLDER] Envoi eHela simulé',
            raw_response={'placeholder': True, 'amount': str(amount)},
        )

    def request_money(
        self, source_phone: str, amount: Decimal,
        reference: str, description: str = ''
    ) -> TransferResult:
        """
        ⚠️ PLACEHOLDER — Reçoit de l'argent depuis eHela.

        TODO: Implémenter avec l'API eHela
        POST {api_base_url}/v1/collection/initiate
        """
        logger.warning(
            f"[EHELA PLACEHOLDER] request_money("
            f"source={source_phone}, amount={amount} BIF, ref={reference})"
        )

        return TransferResult(
            success=True,
            external_reference=f'EHELA-MOCK-{reference[:8]}',
            message='[PLACEHOLDER] Réception eHela simulée',
            raw_response={'placeholder': True, 'amount': str(amount)},
        )

    def check_status(self, external_reference: str) -> TransferResult:
        """
        ⚠️ PLACEHOLDER — Vérifie le statut d'un transfert eHela.

        TODO: GET {api_base_url}/v1/transaction/status?ref={external_reference}
        """
        logger.warning(
            f"[EHELA PLACEHOLDER] check_status({external_reference})"
        )

        return TransferResult(
            success=True,
            external_reference=external_reference,
            message='[PLACEHOLDER] Statut simulé — complété',
            raw_response={'placeholder': True, 'status': 'completed'},
        )

    def verify_webhook(self, payload: bytes, signature: str) -> bool:
        """
        ⚠️ PLACEHOLDER — Vérifie la signature webhook eHela.

        TODO: Implémenter selon la méthode de signature eHela
        """
        logger.warning("[EHELA PLACEHOLDER] verify_webhook — non implémenté")
        return False
