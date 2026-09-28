"""
Adaptateur bancaire abstrait (interface de base).
Tous les adaptateurs bancaires doivent implémenter cette interface.

Pour ajouter une nouvelle banque :
1. Créer un fichier dans apps/banking/adapters/ (ex: bcb_adapter.py)
2. Hériter de BaseBankAdapter
3. Implémenter toutes les méthodes abstraites
4. Configurer le chemin dans BankPartner.adapter_class
"""
import logging
from abc import ABC, abstractmethod
from decimal import Decimal
from dataclasses import dataclass, field
from typing import Optional

logger = logging.getLogger('apps.banking.adapters')


@dataclass
class BankTransferResult:
    """Résultat standardisé d'un transfert bancaire."""
    success: bool
    bank_reference: str = ''
    message: str = ''
    raw_response: dict = field(default_factory=dict)
    error_code: str = ''


@dataclass
class BankAccountInfo:
    """Informations d'un compte bancaire retournées par la banque."""
    account_number: str = ''
    account_name: str = ''
    is_valid: bool = False
    currency: str = 'BIF'
    raw_response: dict = field(default_factory=dict)


@dataclass
class BankBalanceInfo:
    """Solde d'un compte bancaire."""
    available_balance: Decimal = Decimal('0')
    current_balance: Decimal = Decimal('0')
    currency: str = 'BIF'
    raw_response: dict = field(default_factory=dict)


class BaseBankAdapter(ABC):
    """
    Interface abstraite pour l'intégration avec une banque.

    Chaque banque (CRDB, BCB, BANCOBU, etc.) doit fournir un adaptateur
    qui implémente ces méthodes. L'adaptateur utilise les credentials
    stockés dans le modèle BankPartner.

    Usage :
        adapter = CRDBAdapter(bank_partner_instance)
        result = adapter.initiate_deposit(account_number, amount)
    """

    def __init__(self, bank_partner):
        """
        Initialise l'adaptateur avec la configuration de la banque.

        Args:
            bank_partner: Instance de BankPartner contenant api_base_url,
                         api_key, api_secret, etc.
        """
        self.bank_partner = bank_partner
        self.api_base_url = bank_partner.api_base_url
        self.api_key = bank_partner.api_key
        self.api_secret = bank_partner.api_secret

    # ── Vérification de compte ───────────────────────────────────────────────

    @abstractmethod
    def verify_account(self, account_number: str) -> BankAccountInfo:
        """
        Vérifie qu'un numéro de compte bancaire est valide et retourne
        les informations du titulaire.

        Args:
            account_number: Numéro de compte à vérifier

        Returns:
            BankAccountInfo avec is_valid=True si le compte existe
        """
        pass

    # ── Dépôt (Banque → Wallet Cash Tel) ─────────────────────────────────────

    @abstractmethod
    def initiate_deposit(
        self,
        source_account: str,
        amount: Decimal,
        reference: str,
        description: str = ''
    ) -> BankTransferResult:
        """
        Initie un transfert depuis un compte bancaire vers Cash Tel.
        (L'argent quitte la banque pour entrer dans le wallet)

        Args:
            source_account: Numéro de compte bancaire source
            amount: Montant en BIF
            reference: Référence unique Cash Tel
            description: Description du transfert

        Returns:
            BankTransferResult avec le statut et la référence banque
        """
        pass

    # ── Retrait (Wallet Cash Tel → Banque) ───────────────────────────────────

    @abstractmethod
    def initiate_withdrawal(
        self,
        destination_account: str,
        amount: Decimal,
        reference: str,
        description: str = ''
    ) -> BankTransferResult:
        """
        Initie un transfert depuis Cash Tel vers un compte bancaire.
        (L'argent quitte le wallet pour aller dans la banque)

        Args:
            destination_account: Numéro de compte bancaire destination
            amount: Montant en BIF
            reference: Référence unique Cash Tel
            description: Description du transfert

        Returns:
            BankTransferResult avec le statut et la référence banque
        """
        pass

    # ── Vérification du statut d'un transfert ────────────────────────────────

    @abstractmethod
    def check_transfer_status(self, bank_reference: str) -> BankTransferResult:
        """
        Vérifie le statut d'un transfert en cours.

        Args:
            bank_reference: Référence retournée par la banque

        Returns:
            BankTransferResult avec le statut actuel
        """
        pass

    # ── Consultation de solde ────────────────────────────────────────────────

    @abstractmethod
    def get_balance(self, account_number: str) -> BankBalanceInfo:
        """
        Récupère le solde d'un compte bancaire.

        Args:
            account_number: Numéro de compte

        Returns:
            BankBalanceInfo avec le solde disponible
        """
        pass

    # ── Vérification du webhook ──────────────────────────────────────────────

    @abstractmethod
    def verify_webhook_signature(self, payload: bytes, signature: str) -> bool:
        """
        Vérifie l'authenticité d'une notification webhook de la banque.

        Args:
            payload: Corps de la requête webhook
            signature: Signature fournie dans les headers

        Returns:
            True si la signature est valide
        """
        pass
