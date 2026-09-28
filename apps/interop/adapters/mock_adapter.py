"""
Adaptateur Mock — pour le développement et les tests.
Simule toutes les opérations d'interopérabilité sans appeler d'API réelle.
"""
import logging
import uuid
from decimal import Decimal

from .base import BaseProviderAdapter, TransferResult, AccountValidation

logger = logging.getLogger('apps.interop.adapters.mock')


class MockProviderAdapter(BaseProviderAdapter):
    """
    Adaptateur mock pour le développement.
    Simule les réponses des opérateurs externes avec succès systématique.

    ⚠️ NE PAS utiliser en production.
    """

    def validate_account(self, phone_number: str) -> AccountValidation:
        logger.info(f"[MOCK PROVIDER] Vérification : {phone_number}")
        return AccountValidation(
            phone_number=phone_number,
            account_name='Compte Test Mock',
            is_valid=True,
            raw_response={'mock': True},
        )

    def send_money(
        self, destination_phone: str, amount: Decimal,
        reference: str, description: str = ''
    ) -> TransferResult:
        mock_ref = f'MOCK-SEND-{uuid.uuid4().hex[:8].upper()}'
        logger.info(
            f"[MOCK PROVIDER] Envoi : Cash Tel → {destination_phone} | "
            f"{amount} BIF | ref: {mock_ref}"
        )
        return TransferResult(
            success=True,
            external_reference=mock_ref,
            message=f'Envoi mock de {amount} BIF réussi',
            raw_response={'mock': True, 'reference': mock_ref},
        )

    def request_money(
        self, source_phone: str, amount: Decimal,
        reference: str, description: str = ''
    ) -> TransferResult:
        mock_ref = f'MOCK-REQ-{uuid.uuid4().hex[:8].upper()}'
        logger.info(
            f"[MOCK PROVIDER] Réception : {source_phone} → Cash Tel | "
            f"{amount} BIF | ref: {mock_ref}"
        )
        return TransferResult(
            success=True,
            external_reference=mock_ref,
            message=f'Demande mock de {amount} BIF réussie',
            raw_response={'mock': True, 'reference': mock_ref},
        )

    def check_status(self, external_reference: str) -> TransferResult:
        logger.info(f"[MOCK PROVIDER] Statut : {external_reference} → completed")
        return TransferResult(
            success=True,
            external_reference=external_reference,
            message='Transfert complété (mock)',
            raw_response={'mock': True, 'status': 'completed'},
        )

    def verify_webhook(self, payload: bytes, signature: str) -> bool:
        logger.info("[MOCK PROVIDER] Webhook vérifié (mock — toujours True)")
        return True
