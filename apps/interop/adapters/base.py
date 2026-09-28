"""
Adaptateur opérateur Mobile Money abstrait (interface de base).
Tous les adaptateurs d'interopérabilité doivent implémenter cette interface.

Pour ajouter un nouvel opérateur :
1. Créer un fichier dans apps/interop/adapters/ (ex: smart_adapter.py)
2. Hériter de BaseProviderAdapter
3. Implémenter toutes les méthodes abstraites
4. Configurer le chemin dans ExternalProvider.adapter_class
"""
import logging
from abc import ABC, abstractmethod
from decimal import Decimal
from dataclasses import dataclass, field

logger = logging.getLogger('apps.interop.adapters')


@dataclass
class TransferResult:
    """Résultat standardisé d'un transfert inter-opérateur."""
    success: bool
    external_reference: str = ''
    message: str = ''
    raw_response: dict = field(default_factory=dict)
    error_code: str = ''


@dataclass
class AccountValidation:
    """Résultat de la vérification d'un numéro chez l'opérateur."""
    phone_number: str = ''
    account_name: str = ''
    is_valid: bool = False
    raw_response: dict = field(default_factory=dict)


class BaseProviderAdapter(ABC):
    """
    Interface abstraite pour l'interopérabilité avec un opérateur Mobile Money.

    Chaque opérateur (LumiCash, eNoti/Bancobu, eHela) doit fournir un adaptateur
    qui implémente ces méthodes.

    Usage :
        adapter = LumiCashAdapter(provider_instance)
        result = adapter.send_money('+25762000001', Decimal('5000'), 'REF-001')
    """

    def __init__(self, provider):
        """
        Initialise l'adaptateur avec la configuration de l'opérateur.

        Args:
            provider: Instance de ExternalProvider contenant api_base_url,
                     api_key, api_secret, merchant_id, etc.
        """
        self.provider = provider
        self.api_base_url = provider.api_base_url
        self.api_key = provider.api_key
        self.api_secret = provider.api_secret
        self.merchant_id = provider.merchant_id

    # ── Vérification de numéro ───────────────────────────────────────────────

    @abstractmethod
    def validate_account(self, phone_number: str) -> AccountValidation:
        """
        Vérifie qu'un numéro de téléphone est enregistré chez l'opérateur.

        Args:
            phone_number: Numéro à vérifier (format +257...)

        Returns:
            AccountValidation avec is_valid=True si le numéro existe
        """
        pass

    # ── Envoi d'argent (Cash Tel → Opérateur) ────────────────────────────────

    @abstractmethod
    def send_money(
        self,
        destination_phone: str,
        amount: Decimal,
        reference: str,
        description: str = ''
    ) -> TransferResult:
        """
        Envoie de l'argent depuis Cash Tel vers un compte chez l'opérateur.

        Args:
            destination_phone: Numéro du destinataire chez l'opérateur
            amount: Montant en BIF
            reference: Référence unique Cash Tel
            description: Description du transfert

        Returns:
            TransferResult avec le statut et la référence opérateur
        """
        pass

    # ── Réception d'argent (Opérateur → Cash Tel) ────────────────────────────

    @abstractmethod
    def request_money(
        self,
        source_phone: str,
        amount: Decimal,
        reference: str,
        description: str = ''
    ) -> TransferResult:
        """
        Demande un paiement depuis un compte chez l'opérateur vers Cash Tel.

        Args:
            source_phone: Numéro de l'expéditeur chez l'opérateur
            amount: Montant en BIF
            reference: Référence unique Cash Tel
            description: Description

        Returns:
            TransferResult avec le statut
        """
        pass

    # ── Vérification du statut ───────────────────────────────────────────────

    @abstractmethod
    def check_status(self, external_reference: str) -> TransferResult:
        """
        Vérifie le statut d'un transfert en cours.

        Args:
            external_reference: Référence retournée par l'opérateur

        Returns:
            TransferResult avec le statut actuel
        """
        pass

    # ── Vérification du webhook ──────────────────────────────────────────────

    @abstractmethod
    def verify_webhook(self, payload: bytes, signature: str) -> bool:
        """
        Vérifie l'authenticité d'une notification webhook de l'opérateur.

        Args:
            payload: Corps de la requête webhook
            signature: Signature fournie dans les headers

        Returns:
            True si la signature est valide
        """
        pass
