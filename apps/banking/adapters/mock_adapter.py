"""
Adaptateur bancaire Mock — pour le développement et les tests.
Simule toutes les opérations bancaires sans appeler d'API réelle.
"""
import logging
import uuid
from decimal import Decimal

from .base import BaseBankAdapter, BankTransferResult, BankAccountInfo, BankBalanceInfo

logger = logging.getLogger('apps.banking.adapters.mock')


class MockBankAdapter(BaseBankAdapter):
    """
    Adaptateur mock pour le développement.
    Simule les réponses bancaires avec succès systématique.

    ⚠️ NE PAS utiliser en production.
    """

    def verify_account(self, account_number: str) -> BankAccountInfo:
        logger.info(f"[MOCK BANK] Vérification compte : {account_number}")
        return BankAccountInfo(
            account_number=account_number,
            account_name='Compte Test Mock',
            is_valid=True,
            currency='BIF',
            raw_response={'mock': True},
        )

    def initiate_deposit(
        self, source_account: str, amount: Decimal,
        reference: str, description: str = ''
    ) -> BankTransferResult:
        mock_ref = f'MOCK-DEP-{uuid.uuid4().hex[:8].upper()}'
        logger.info(
            f"[MOCK BANK] Dépôt : {source_account} → Cash Tel | "
            f"{amount} BIF | ref: {mock_ref}"
        )
        return BankTransferResult(
            success=True,
            bank_reference=mock_ref,
            message=f'Dépôt mock de {amount} BIF réussi',
            raw_response={'mock': True, 'reference': mock_ref},
        )

    def initiate_withdrawal(
        self, destination_account: str, amount: Decimal,
        reference: str, description: str = ''
    ) -> BankTransferResult:
        mock_ref = f'MOCK-WIT-{uuid.uuid4().hex[:8].upper()}'
        logger.info(
            f"[MOCK BANK] Retrait : Cash Tel → {destination_account} | "
            f"{amount} BIF | ref: {mock_ref}"
        )
        return BankTransferResult(
            success=True,
            bank_reference=mock_ref,
            message=f'Retrait mock de {amount} BIF réussi',
            raw_response={'mock': True, 'reference': mock_ref},
        )

    def check_transfer_status(self, bank_reference: str) -> BankTransferResult:
        logger.info(f"[MOCK BANK] Statut : {bank_reference} → completed")
        return BankTransferResult(
            success=True,
            bank_reference=bank_reference,
            message='Transfert complété (mock)',
            raw_response={'mock': True, 'status': 'completed'},
        )

    def get_balance(self, account_number: str) -> BankBalanceInfo:
        logger.info(f"[MOCK BANK] Solde : {account_number}")
        return BankBalanceInfo(
            available_balance=Decimal('10000000'),
            current_balance=Decimal('10000000'),
            currency='BIF',
            raw_response={'mock': True},
        )

    def verify_webhook_signature(self, payload: bytes, signature: str) -> bool:
        logger.info("[MOCK BANK] Webhook vérifié (mock — toujours True)")
        return True
