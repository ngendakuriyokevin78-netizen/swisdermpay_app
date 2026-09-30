"""
Passerelle TOUS TELEPHONES — AJOUT SEUL (maquette USSD/SMS sans opérateur réel).
- POST /api/interop/ussd/ *300# : 1 Envoyer, 2 Attente, 3 Valider, 4 Solde,
  5 Annuler, 9 Plus (6 Histo, 7 Achat marchand, 8 Retrait agent, 9 Compte),
  0 Retour (0 seul = Aide). Création compte nouveau client : 9*9*1.
- POST /api/interop/sms/ : ENVOYER / ATTENTE / VALIDER / ANNULER / HISTO / SOLDE.
Réutilise process_transfer + pending_services + withdraw existants, ne les modifie pas.
"""
from decimal import Decimal
from django.core.exceptions import ValidationError
from django.conf import settings
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import AllowAny
from cashtel.throttles import UssdRateThrottle
from apps.transactions.money import fmt_bif as _b


def _check_operator(request) -> bool:
    """Vérifie la clé opérateur si configurée ; ouvert en DEBUG pour tests locaux."""
    expected = getattr(settings, 'OPERATOR_API_KEY', '')
    if not expected:
        return True if settings.DEBUG else True  # maquette : ouvert, durcir en prod via .env
    got = request.headers.get('X-Operator-Key') or request.data.get('operator_key') or ''
    if got != expected:
        return False
    ips = getattr(settings, 'ALLOWED_USSD_IPS', []) or []
    if ips:
        ip = request.META.get('HTTP_X_FORWARDED_FOR', '').split(',')[0].strip() or request.META.get('REMOTE_ADDR')
        if ip not in ips:
            return False
    return True


def _get_user(phone):
    from apps.authentication.models import User
    from apps.authentication.contacts_views import normalize_phone
    norm = normalize_phone(phone)
    try:
        return User.objects.get(phone_number=norm, is_active=True), norm
    except User.DoesNotExist:
        return None, norm


def _menu(parent: str, defaults: dict) -> dict:
    """Libellés du menu depuis l'admin (modifiables sans code source), sinon défauts."""
    try:
        from apps.interop.models import UssdMenuOption
        return UssdMenuOption.labels(parent, defaults)
    except Exception:
        return dict(defaults)


ROOT_DEFAULTS = {'1': 'Envoyer', '2': 'Attente', '3': 'Valider', '4': 'Solde', '5': 'Annuler', '9': 'Plus'}
PLUS_DEFAULTS = {'6': 'Histo', '7': 'Achat', '8': 'Retrait', '9': 'Compte'}
COMPTE_DEFAULTS = {'1': 'Créer', '2': 'PIN', '3': 'Nom'}


def _root_menu() -> str:
    lb = _menu('root', ROOT_DEFAULTS)
    lines = ['CON Cash Tel'] + [f'{k}.{lb[k]}' for k in ('1', '2', '3', '4', '5', '9') if k in lb]
    return '\n'.join(lines)


def _plus_menu() -> str:
    lb = _menu('plus', PLUS_DEFAULTS)
    lines = ['CON Plus'] + [f'{k}.{lb[k]}' for k in ('6', '7', '8', '9') if k in lb] + ['0.Retour']
    return '\n'.join(lines)


def _compte_menu() -> str:
    lb = _menu('compte', COMPTE_DEFAULTS)
    lines = ['CON Compte'] + [f'{k}.{lb[k]}' for k in ('1', '2', '3') if k in lb] + ['0.Retour']
    return '\n'.join(lines)


class UssdGatewayView(APIView):
    """Menu USSD *300# : 1 Envoyer, 2 Attente, 3 Valider, 4 Solde, 5 Annuler, 9 Plus (6 Histo, 7 Achat, 8 Retrait agent, 9 Compte), 0 Retour/Aide. 1-6 inchangés."""
    permission_classes = [AllowAny]
    authentication_classes = []
    throttle_classes = [UssdRateThrottle]

    def post(self, request):
        if not _check_operator(request):
            return Response({'response': 'END Accès refusé.'}, status=403)
        phone = request.data.get('phoneNumber') or request.data.get('msisdn') or request.data.get('phone') or ''
        text = (request.data.get('text') or request.data.get('input') or '').strip()
        user, norm = _get_user(phone)

        # Création compte nouveau client via USSD (sans compte requis) : 9*9*1*prénom*nom*pin
        if (not user) and (text.startswith('9*9*1') or text in ('9', '9*9')):
            parts0 = text.split('*')
            # 0 = Retour : recule d'une étape dans le formulaire de création
            while len(parts0) > 3 and parts0[-1] == '0':
                parts0 = parts0[:-2]
            text0 = '*'.join(parts0)
            if text0 in ('9', '9*9'):
                return Response({'response': 'CON Prénom:\n0.Retour'})
            parts0 = text0.split('*')
            if len(parts0) == 3:
                return Response({'response': 'CON Prénom:\n0.Retour'})
            if len(parts0) == 4:
                return Response({'response': 'CON Nom:\n0.Retour'})
            if len(parts0) == 5:
                return Response({'response': 'CON Nouveau PIN 4 chiffres:\n0.Retour'})
            if len(parts0) >= 6:
                prenom, nom, pin = parts0[3].strip(), parts0[4].strip(), parts0[5].strip()
                if len(prenom) < 2 or len(nom) < 2:
                    return Response({'response': 'END Prénom/nom trop courts.'})
                if not (pin.isdigit() and len(pin) == 4):
                    return Response({'response': 'END PIN invalide (4 chiffres).'})
                try:
                    from apps.authentication.models import User
                    from apps.authentication.services import AuditService, SMSService
                    if User.objects.filter(phone_number=norm).exists():
                        return Response({'response': 'END Numéro déjà inscrit. Tapez *300#.'})
                    nu = User(phone_number=norm, first_name=prenom[:100],
                              last_name=nom[:100], is_phone_verified=True)
                    nu.set_password('ussd-' + norm)
                    nu.set_pin(pin)
                    nu.save()
                    AuditService.log(user=nu, action='REGISTER_USSD', details={'phone': norm})
                    SMSService.send_async(norm, f"Swisderm Pay: Bienvenue {prenom} ! Compte créé. Solde 0 BIF.")
                    return Response({'response': f'END Bienvenue {prenom} ! Compte {norm} créé.'})
                except ValueError as e:
                    return Response({'response': f'END Echec: {e}'})
                except Exception:
                    return Response({'response': 'END Erreur interne.'})

        if not user:
            return Response({'response': 'END Numéro non inscrit Cash Tel. Choix 9*9*1 pour créer un compte.'})
        if not user.is_phone_verified:
            return Response({'response': 'END Compte non vérifié.'})
        # Coupure maintenance : même message que l'app (sans casser le menu)
        try:
            from apps.authentication.models import MaintenanceWindow
            mw = MaintenanceWindow.current()
            if mw and not (user.role == 'ADMIN' or user.is_staff):
                return Response({'response': f"END Service interrompu ({mw.reason or 'réparation'}). Réessayez plus tard."})
        except Exception:
            pass
        parts = text.split('*') if text else []

        # 0 = Retour page précédente (sauf « 0 » seul à la racine = Aide, compatibilité)
        if text != '0' and len(parts) >= 2 and parts[-1] == '0':
            back = parts[:-2]
            text = '*'.join(back)
            parts = back
            if not text:
                return Response({'response': _root_menu()})

        # Menu racine (libellés modifiables dans /admin/ sans code source)
        if not text:
            return Response({'response': _root_menu()})

        if parts[0] == '4':
            try:
                bal = user.wallet.balance
            except Exception:
                bal = 0
            return Response({'response': f'END Solde: {_b(bal)}'})

        # 1. Envoyer direct : 1*montant*numero*pin
        if parts[0] == '1':
            if len(parts) == 1:
                return Response({'response': 'CON Montant BIF:\n0.Retour'})
            if len(parts) == 2:
                return Response({'response': 'CON Numéro destinataire (+257...):\n0.Retour'})
            if len(parts) == 3:
                return Response({'response': 'CON PIN 4 chiffres:\n0.Retour'})
            if len(parts) >= 4:
                try:
                    from apps.transactions.services import process_transfer
                    from apps.authentication.contacts_views import normalize_phone
                    txn = process_transfer(user, normalize_phone(parts[2]),
                                           Decimal(parts[1]), parts[3])
                    return Response({'response': f'END Envoyé {_b(txn.amount)} à {parts[2]}. Frais {_b(txn.fee)}.'})
                except ValidationError as e:
                    return Response({'response': f'END Echec: {e.message}'})
                except Exception:
                    return Response({'response': 'END Erreur interne.'})

        # 2. Mettre en attente : 2*montant*numero
        if parts[0] == '2':
            if len(parts) == 1:
                return Response({'response': 'CON Montant BIF:\n0.Retour'})
            if len(parts) == 2:
                return Response({'response': 'CON Numéro destinataire:\n0.Retour'})
            if len(parts) >= 3:
                try:
                    from apps.transactions.pending_services import create_pending_transfer
                    from apps.authentication.contacts_views import normalize_phone
                    t = create_pending_transfer(user, normalize_phone(parts[2]), Decimal(parts[1]))
                    return Response({'response': f'END Mis en attente {_b(t.amount)} vers {parts[2]}. Réf {str(t.reference)[:8].upper()}. Composez 3 pour valider.'})
                except ValidationError as e:
                    return Response({'response': f'END Echec: {e.message}'})

        # 3. Valider : 3*ref8? Non -> on liste : 3*reference*pin
        if parts[0] == '3':
            if len(parts) == 1:
                # liste les 3 dernières refs courtes
                from apps.transactions.pending_services import list_pending_transfers
                pend = list(list_pending_transfers(user)[:3])
                if not pend:
                    return Response({'response': 'END Aucune attente.'})
                msg = 'CON Choisir:\n' + '\n'.join(
                    f'{i+1}. {_b(p.amount)} vers {p.receiver.phone_number}' for i, p in enumerate(pend))
                msg += '\n0.Retour'
                return Response({'response': msg, 'refs': [str(p.reference) for p in pend]})
            if len(parts) == 2:
                return Response({'response': 'CON PIN:\n0.Retour'})
            if len(parts) >= 3:
                try:
                    from apps.transactions.pending_services import list_pending_transfers, validate_pending_transfer
                    pend = list(list_pending_transfers(user))
                    idx = int(parts[1]) - 1 if parts[1].isdigit() else -1
                    if idx < 0 or idx >= len(pend):
                        return Response({'response': 'END Choix invalide.'})
                    txn = validate_pending_transfer(user, str(pend[idx].reference), parts[2])
                    return Response({'response': f'END Validé {_b(txn.amount)}.'})
                except ValidationError as e:
                    return Response({'response': f'END Echec: {e.message}'})
                except Exception:
                    return Response({'response': 'END Erreur interne.'})

        # 5. Annuler attente : 5 -> liste, 5*idx -> annule (sans PIN, comme l'app)
        if parts[0] == '5':
            from apps.transactions.pending_services import list_pending_transfers, cancel_pending_transfer
            pend = list(list_pending_transfers(user)[:3])
            if not pend:
                return Response({'response': 'END Aucune attente.'})
            if len(parts) == 1:
                msg = 'CON Annuler:\n' + '\n'.join(
                    f'{i+1}. {_b(p.amount)} vers {p.receiver.phone_number}' for i, p in enumerate(pend))
                msg += '\n0.Retour'
                return Response({'response': msg})
            try:
                idx = int(parts[1]) - 1 if parts[1].isdigit() else -1
                if idx < 0 or idx >= len(pend):
                    return Response({'response': 'END Choix invalide.'})
                t = cancel_pending_transfer(user, str(pend[idx].reference), 'annulé via USSD')
                return Response({'response': f'END Attente {_b(t.amount)} annulée.'})
            except ValidationError as e:
                return Response({'response': f'END Echec: {e.message}'})

        # 6. Historique : 3 dernières transactions (aussi via 9*6)
        if parts[0] == '6' or (parts[0] == '9' and len(parts) > 1 and parts[1] == '6'):
            try:
                from apps.transactions.services import get_user_transactions
                last = list(get_user_transactions(user)[:3])
                if not last:
                    return Response({'response': 'END Aucune transaction.'})
                lines = []
                for t in last:
                    sens = '+' if (t.receiver_id == user.id) else '-'
                    lines.append(f'{sens}{_b(t.amount)} {t.status}')
                return Response({'response': 'END ' + ' | '.join(lines)})
            except Exception:
                return Response({'response': 'END Erreur interne.'})

        # 7. Achat chez marchand : 7*montant*numero*pin (aussi 9*7*...)
        _achat = parts[1:] if (parts[0] == '9' and len(parts) > 1 and parts[1] == '7') else (parts[1:] if parts[0] == '7' else None)
        if _achat is not None:
            if len(_achat) == 0:
                return Response({'response': 'CON Montant achat BIF:\n0.Retour'})
            if len(_achat) == 1:
                return Response({'response': 'CON Numéro marchand (+257...):\n0.Retour'})
            if len(_achat) == 2:
                return Response({'response': 'CON PIN 4 chiffres:\n0.Retour'})
            try:
                from apps.transactions.services import process_transfer
                from apps.authentication.contacts_views import normalize_phone
                txn = process_transfer(user, normalize_phone(_achat[1]), Decimal(_achat[0]), _achat[2])
                return Response({'response': f'END Achat {_b(txn.amount)} payé. Frais {_b(txn.fee)}.'})
            except ValidationError as e:
                return Response({'response': f'END Echec: {e.message}'})
            except Exception:
                return Response({'response': 'END Erreur interne.'})

        # 8. Retrait chez agent : 8*montant*pin (aussi 9*8*...) -> code à montrer à l'agent
        _ret = parts[1:] if (parts[0] == '9' and len(parts) > 1 and parts[1] == '8') else (parts[1:] if parts[0] == '8' else None)
        if _ret is not None:
            if len(_ret) == 0:
                return Response({'response': 'CON Montant retrait BIF:\n0.Retour'})
            if len(_ret) == 1:
                return Response({'response': 'CON PIN 4 chiffres:\n0.Retour'})
            try:
                from apps.agent.withdraw_services import request_withdrawal
                req = request_withdrawal(user, Decimal(_ret[0]), _ret[1],
                                         f"ussd-{norm}-{text}"[:64])
                return Response({'response': f'END Code retrait {req.code}. {_b(req.amount)}. Montrez à l agent.'})
            except ValidationError as e:
                return Response({'response': f'END Echec: {e.message}'})
            except Exception:
                return Response({'response': 'END Erreur interne.'})

        # 9. Plus / Compte (libellés modifiables sans code source)
        if parts[0] == '9':
            if len(parts) == 1:
                return Response({'response': _plus_menu()})
            if len(parts) >= 2 and parts[1] == '9':
                if len(parts) == 2:
                    return Response({'response': _compte_menu()})
                if len(parts) >= 3 and parts[2] == '1':
                    if user:
                        return Response({'response': 'END Numéro déjà inscrit.'})
                    if len(parts) == 3:
                        return Response({'response': 'CON Prénom:\n0.Retour'})
                    if len(parts) == 4:
                        return Response({'response': 'CON Nom:\n0.Retour'})
                    if len(parts) == 5:
                        return Response({'response': 'CON Nouveau PIN 4 chiffres:\n0.Retour'})
                if len(parts) >= 3 and parts[2] == '2':
                    if len(parts) == 3:
                        return Response({'response': 'CON Ancien PIN:\n0.Retour'})
                    if len(parts) == 4:
                        return Response({'response': 'CON Nouveau PIN:\n0.Retour'})
                    if len(parts) >= 5:
                        old, new = parts[3].strip(), parts[4].strip()
                        if not user.check_pin(old):
                            return Response({'response': 'END Ancien PIN incorrect.'})
                        try:
                            user.set_pin(new)
                            user.save(update_fields=['pin'])
                            from apps.authentication.services import AuditService
                            AuditService.log(user=user, action='PIN_CHANGED_USSD', details={})
                            return Response({'response': 'END PIN modifié.'})
                        except ValueError as e:
                            return Response({'response': f'END Echec: {e}'})
                if len(parts) >= 3 and parts[2] == '3':
                    if len(parts) == 3:
                        return Response({'response': 'CON Prénom:\n0.Retour'})
                    if len(parts) == 4:
                        return Response({'response': 'CON Nom:\n0.Retour'})
                    if len(parts) == 5:
                        return Response({'response': 'CON PIN pour confirmer:\n0.Retour'})
                    if len(parts) >= 6:
                        prenom, nom, pin = parts[3].strip(), parts[4].strip(), parts[5].strip()
                        if not user.check_pin(pin):
                            return Response({'response': 'END PIN incorrect.'})
                        if len(prenom) < 2 or len(nom) < 2:
                            return Response({'response': 'END Prénom/nom trop courts.'})
                        user.first_name, user.last_name = prenom[:100], nom[:100]
                        user.save(update_fields=['first_name', 'last_name'])
                        return Response({'response': f'END Compte à jour : {prenom} {nom}.'})

        # 0. Aide (0 seul à la racine ; ailleurs 0 = Retour traité plus haut)
        if parts[0] == '0':
            return Response({'response': 'END Cash Tel *300# : 1 Envoyer, 2 Attente, 3 Valider, 4 Solde, 5 Annuler, 9 Plus (6 Histo, 7 Achat, 8 Retrait, 9 Compte). 0 Retour.'})

        return Response({'response': 'END Choix invalide.'})


class SmsGatewayView(APIView):
    """SMS transfert seul : ENVOYER / ATTENTE / VALIDER / ANNULER / HISTO / SOLDE (sans achat ni retrait)."""
    permission_classes = [AllowAny]
    authentication_classes = []
    throttle_classes = [UssdRateThrottle]

    def post(self, request):
        if not _check_operator(request):
            return Response({'success': False, 'reply': 'Accès refusé.'}, status=403)
        raw_from = request.data.get('from') or request.data.get('phoneNumber') or ''
        text = (request.data.get('text') or '').strip().upper()
        user, norm = _get_user(raw_from)
        if not user:
            return Response({'success': False, 'reply': 'Numéro non inscrit.'})
        toks = text.split()
        try:
            from apps.authentication.contacts_views import normalize_phone
            if toks[:1] == ['SOLDE']:
                return Response({'success': True, 'reply': f'Solde: {_b(user.wallet.balance)}'})
            if toks[:1] == ['ENVOYER'] and 'AU' in toks and 'PIN' in toks:
                # ENVOYER 5000 AU +257... PIN 1234
                amt = Decimal(toks[1])
                dest = normalize_phone(toks[toks.index('AU') + 1])
                pin = toks[toks.index('PIN') + 1]
                from apps.transactions.services import process_transfer
                txn = process_transfer(user, dest, amt, pin)
                return Response({'success': True, 'reply': f'Envoyé {_b(txn.amount)}. Frais {_b(txn.fee)}.'})
            if toks[:1] == ['ATTENTE'] and 'AU' in toks:
                amt = Decimal(toks[1])
                dest = normalize_phone(toks[toks.index('AU') + 1])
                from apps.transactions.pending_services import create_pending_transfer
                t = create_pending_transfer(user, dest, amt)
                return Response({'success': True, 'reply': f'En attente {_b(t.amount)}. Réf {t.reference}. VALIDER {t.reference} PIN XXXX.'})
            if toks[:1] == ['VALIDER'] and 'PIN' in toks:
                ref = request.data.get('text', '').split()[1]
                pin = toks[toks.index('PIN') + 1]
                from apps.transactions.pending_services import validate_pending_transfer
                txn = validate_pending_transfer(user, ref, pin)
                return Response({'success': True, 'reply': f'Validé {_b(txn.amount)}.'})
            if toks[:1] == ['ANNULER']:
                ref = request.data.get('text', '').split()[1]
                from apps.transactions.pending_services import cancel_pending_transfer
                t = cancel_pending_transfer(user, ref, 'annulé via SMS')
                return Response({'success': True, 'reply': f'Attente {_b(t.amount)} annulée.'})
            if toks[:1] in (['HISTO'], ['HISTORIQUE']):
                from apps.transactions.services import get_user_transactions
                last = list(get_user_transactions(user)[:3])
                if not last:
                    return Response({'success': True, 'reply': 'Aucune transaction.'})
                txt = ' | '.join(
                    f"{'+' if t.receiver_id == user.id else '-'}{_b(t.amount)} {t.status}" for t in last)
                return Response({'success': True, 'reply': txt})
        except ValidationError as e:
            return Response({'success': False, 'reply': f'Echec: {e.message}'})
        except Exception:
            return Response({'success': False, 'reply': 'Format: ENVOYER 5000 AU +257... PIN 1234'})
        return Response({'success': False, 'reply': 'Format: ENVOYER / ATTENTE / VALIDER / ANNULER / HISTO / SOLDE'})
