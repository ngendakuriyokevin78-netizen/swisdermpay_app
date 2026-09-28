"""
Adaptateur CRDB — Banque principale de Swisderm.

╔══════════════════════════════════════════════════════════════════════════════╗
║  ⚠️  PLACEHOLDER — INTÉGRATION API CRDB                                    ║
║                                                                            ║
║  Ce fichier contient la structure complète de l'adaptateur CRDB.           ║
║  Toutes les méthodes sont prêtes à être implémentées une fois que :       ║
║                                                                            ║
║  1. L'accord commercial avec CRDB est signé                               ║
║  2. Les credentials API sont fournis (api_key, api_secret, base_url)       ║
║  3. La documentation API CRDB est disponible                               ║
║                                                                            ║
║  Pour activer :                                                            ║
║  → Admin → Banques Partenaires → CRDB → adapter_class =                   ║
║    "apps.banking.adapters.crdb_adapter.CRDBAdapter"                        ║
║  → Remplir api_base_url, api_key, api_secret                              ║
╚══════════════════════════════════════════════════════════════════════════════╝
"""
import logging
import hashlib
import hmac
from decimal import Decimal
from typing import Optional

from .base import BaseBankAdapter, BankTransferResult, BankAccountInfo, BankBalanceInfo

logger = logging.getLogger('apps.banking.adapters.crdb')


class CRDBAdapter(BaseBankAdapter):
    """
    Adaptateur API pour la CRDB (Coopérative de Crédit et de Développement Rural).
    Banque par défaut de Swisderm au Burundi.

    Configuration requise dans BankPartner :
        - api_base_url  : URL de base de l'API CRDB (ex: https://api.crdb.co.bi/v1)
        - api_key       : Clé API fournie par CRDB
        - api_secret    : Secret pour la signature des requêtes
        - webhook_secret: Secret pour vérifier les callbacks CRDB
    """

    # ── Constantes API CRDB ──────────────────────────────────────────────────
    # ⚠️ À adapter selon la documentation officielle CRDB

    ENDPOINT_VERIFY_ACCOUNT = '/accounts/verify'
    ENDPOINT_TRANSFER = '/transfers'
    ENDPOINT_TRANSFER_STATUS = '/transfers/{reference}/status'
    ENDPOINT_BALANCE = '/accounts/{account}/balance'

    def __init__(self, bank_partner):
        super().__init__(bank_partner)
        self.headers = {
            'Authorization': f'Bearer {self.api_key}',
            'Content-Type': 'application/json',
            'X-API-Key': self.api_key,
            # ⚠️ Ajouter d'autres headers requis par CRDB
        }

    # ── Vérification de compte ───────────────────────────────────────────────

    def verify_account(self, account_number: str) -> BankAccountInfo:
        """
        ⚠️ PLACEHOLDER — Vérifie un compte CRDB.

        TODO: Quand l'API CRDB sera disponible, implémenter :
        1. POST/GET vers ENDPOINT_VERIFY_ACCOUNT
        2. Envoyer le numéro de compte
        3. Parser la réponse (nom titulaire, statut, devise)
        """
        logger.warning(
            f"[CRDB PLACEHOLDER] verify_account({account_number}) — "
            "Intégration API CRDB non encore configurée."
        )

        # ── Réponse simulée pour le développement ────────────────────────────
        # ⚠️ REMPLACER par l'appel API réel :
        #
        # import requests
        # response = requests.post(
        #     f"{self.api_base_url}{self.ENDPOINT_VERIFY_ACCOUNT}",
        #     headers=self.headers,
        #     json={'account_number': account_number}
        # )
        # data = response.json()
        # return BankAccountInfo(
        #     account_number=data['account_number'],
        #     account_name=data['account_holder_name'],
        #     is_valid=data['status'] == 'active',
        #     currency=data.get('currency', 'BIF'),
        #     raw_response=data,
        # )

        return BankAccountInfo(
            account_number=account_number,
            account_name='[CRDB — Vérification non disponible]',
            is_valid=True,  # ⚠️ En prod, doit être vérifié via API
            currency='BIF',
            raw_response={'placeholder': True, 'message': 'API CRDB non configurée'},
        )

    # ── Dépôt : Banque CRDB → Wallet Cash Tel ────────────────────────────────

    def initiate_deposit(
        self,
        source_account: str,
        amount: Decimal,
        reference: str,
        description: str = ''
    ) -> BankTransferResult:
        """
        ⚠️ PLACEHOLDER — Initie un dépôt depuis CRDB.

        Flux réel attendu :
        1. Cash Tel envoie une requête à CRDB pour débiter le compte source
        2. CRDB vérifie le solde et autorise le débit
        3. CRDB retourne une référence de transaction
        4. Cash Tel crédite le wallet du client
        5. CRDB envoie un webhook de confirmation

        TODO: Implémenter avec l'API CRDB :
        """
        logger.warning(
            f"[CRDB PLACEHOLDER] initiate_deposit("
            f"account={source_account}, amount={amount} BIF, ref={reference})"
        )

        # ── Appel API simulé ─────────────────────────────────────────────────
        # ⚠️ REMPLACER par l'appel API réel :
        #
        # import requests
        # response = requests.post(
        #     f"{self.api_base_url}{self.ENDPOINT_TRANSFER}",
        #     headers=self.headers,
        #     json={
        #         'type': 'debit',
        #         'source_account': source_account,
        #         'amount': str(amount),
        #         'currency': 'BIF',
        #         'reference': reference,
        #         'description': description or f'Dépôt Cash Tel {reference}',
        #         'callback_url': 'https://votre-domaine.com/api/banking/webhooks/crdb/',
        #     }
        # )
        # data = response.json()
        #
        # if response.status_code == 200 and data.get('status') == 'accepted':
        #     return BankTransferResult(
        #         success=True,
        #         bank_reference=data['transaction_id'],
        #         message='Transfert initié avec succès',
        #         raw_response=data,
        #     )
        # else:
        #     return BankTransferResult(
        #         success=False,
        #         message=data.get('error', 'Erreur inconnue'),
        #         error_code=data.get('error_code', ''),
        #         raw_response=data,
        #     )

        return BankTransferResult(
            success=True,
            bank_reference=f'CRDB-MOCK-{reference[:8]}',
            message='[PLACEHOLDER] Dépôt CRDB simulé — API non configurée',
            raw_response={'placeholder': True, 'amount': str(amount)},
        )

    # ── Retrait : Wallet Cash Tel → Banque CRDB ──────────────────────────────

    def initiate_withdrawal(
        self,
        destination_account: str,
        amount: Decimal,
        reference: str,
        description: str = ''
    ) -> BankTransferResult:
        """
        ⚠️ PLACEHOLDER — Initie un retrait vers CRDB.

        Flux réel attendu :
        1. Cash Tel débite le wallet du client
        2. Cash Tel envoie une requête à CRDB pour créditer le compte destination
        3. CRDB exécute le virement
        4. CRDB envoie un webhook de confirmation

        TODO: Implémenter avec l'API CRDB
        """
        logger.warning(
            f"[CRDB PLACEHOLDER] initiate_withdrawal("
            f"account={destination_account}, amount={amount} BIF, ref={reference})"
        )

        # ⚠️ REMPLACER par l'appel API réel (même structure que initiate_deposit)

        return BankTransferResult(
            success=True,
            bank_reference=f'CRDB-MOCK-{reference[:8]}',
            message='[PLACEHOLDER] Retrait CRDB simulé — API non configurée',
            raw_response={'placeholder': True, 'amount': str(amount)},
        )

    # ── Vérification du statut ───────────────────────────────────────────────

    def check_transfer_status(self, bank_reference: str) -> BankTransferResult:
        """
        ⚠️ PLACEHOLDER — Vérifie le statut d'un transfert CRDB.

        TODO: Implémenter :
        GET {api_base_url}/transfers/{bank_reference}/status
        """
        logger.warning(
            f"[CRDB PLACEHOLDER] check_transfer_status({bank_reference})"
        )

        # ⚠️ REMPLACER par l'appel API réel :
        #
        # import requests
        # url = f"{self.api_base_url}{self.ENDPOINT_TRANSFER_STATUS.format(reference=bank_reference)}"
        # response = requests.get(url, headers=self.headers)
        # data = response.json()
        # return BankTransferResult(
        #     success=data['status'] in ('completed', 'settled'),
        #     bank_reference=bank_reference,
        #     message=data.get('status_description', ''),
        #     raw_response=data,
        # )

        return BankTransferResult(
            success=True,
            bank_reference=bank_reference,
            message='[PLACEHOLDER] Statut simulé — complété',
            raw_response={'placeholder': True, 'status': 'completed'},
        )

    # ── Consultation de solde ────────────────────────────────────────────────

    def get_balance(self, account_number: str) -> BankBalanceInfo:
        """
        ⚠️ PLACEHOLDER — Récupère le solde d'un compte CRDB.

        TODO: Implémenter :
        GET {api_base_url}/accounts/{account_number}/balance
        """
        logger.warning(
            f"[CRDB PLACEHOLDER] get_balance({account_number})"
        )

        return BankBalanceInfo(
            available_balance=Decimal('0'),
            current_balance=Decimal('0'),
            currency='BIF',
            raw_response={'placeholder': True, 'message': 'API CRDB non configurée'},
        )

    # ── Vérification webhook ─────────────────────────────────────────────────

    def verify_webhook_signature(self, payload: bytes, signature: str) -> bool:
        """
        ⚠️ PLACEHOLDER — Vérifie la signature d'un webhook CRDB.

        TODO: Implémenter selon la méthode de signature CRDB
        (probablement HMAC-SHA256 ou RSA)
        """
        if not self.bank_partner.webhook_secret:
            logger.warning("[CRDB PLACEHOLDER] Webhook secret non configuré")
            return False

        # ⚠️ REMPLACER par la méthode de signature réelle de CRDB :
        #
        # expected = hmac.new(
        #     self.bank_partner.webhook_secret.encode(),
        #     payload,
        #     hashlib.sha256
        # ).hexdigest()
        # return hmac.compare_digest(expected, signature)

        logger.warning("[CRDB PLACEHOLDER] verify_webhook_signature — non implémenté")
        return False
