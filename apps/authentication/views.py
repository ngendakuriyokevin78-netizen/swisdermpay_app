"""
Vues API pour l'authentification Cash Tel.
- RegisterView : inscription + envoi OTP
- VerifyOTPView : validation OTP
- LoginView : connexion JWT par PIN
- ProfileView : profil utilisateur
- ChangePinView : modification PIN
- LogoutView : révocation token
"""
import logging
from django.contrib.auth import get_user_model
from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.exceptions import TokenError
from drf_yasg.utils import swagger_auto_schema
from drf_yasg import openapi

from .serializers import (
    RegisterSerializer, VerifyOTPSerializer, LoginSerializer,
    UserProfileSerializer, ChangePinSerializer, SetPinSerializer
)
from .services import OTPService, AuditService
from django.conf import settings
from cashtel.throttles import LoginRateThrottle, OtpRateThrottle

logger = logging.getLogger('apps.authentication')
User = get_user_model()


def success_response(data: dict, status_code=status.HTTP_200_OK) -> Response:
    """Wrapper pour une réponse API cohérente."""
    return Response({'success': True, **data}, status=status_code)


# ── Inscription ────────────────────────────────────────────────────────────────

class RegisterView(APIView):
    """
    POST /api/auth/register/
    Inscrit un nouvel utilisateur et envoie un OTP par SMS.
    """
    permission_classes = [AllowAny]
    throttle_classes = [OtpRateThrottle]

    @swagger_auto_schema(
        request_body=RegisterSerializer,
        responses={
            201: openapi.Response('Compte créé, OTP envoyé par SMS'),
            400: 'Données invalides',
        },
        operation_summary="Inscription",
        operation_description="Crée un compte et envoie un OTP de vérification par SMS."
    )
    def post(self, request):
        serializer = RegisterSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(
                {'success': False, 'error': 'Données invalides', 'details': serializer.errors},
                status=status.HTTP_400_BAD_REQUEST
            )

        user = serializer.save()

        # Envoi OTP de vérification
        OTPService.send_otp(user)

        AuditService.log(
            user=user,
            action='REGISTER',
            ip_address=AuditService.get_client_ip(request),
            details={'phone': user.phone_number}
        )

        logger.info(f"Nouveau compte créé : {user.phone_number}")
        # Recommandation Lumitel non bloquante (AJOUT SEUL)
        try:
            from .phone_utils import operator_of, is_lumitel, LUMITEL_RECOMMENDATION
            _op = operator_of(user.phone_number)
            _is_lumi = is_lumitel(user.phone_number)
        except Exception:
            _op, _is_lumi, LUMITEL_RECOMMENDATION = 'INCONNU', False, ''
        has_pin = bool(user.pin)
        return success_response(
            {
                'message': f'Compte créé. Un OTP a été envoyé au {user.phone_number}.',
                'phone_number': user.phone_number,
                'operator': _op,
                'is_lumitel': _is_lumi,
                'recommandation': LUMITEL_RECOMMENDATION if not _is_lumi else 'Numéro Lumitel détecté : parfait pour Cash Tel.',
                'has_pin': has_pin,
                'next_step': 'Vérifiez votre OTP puis connectez-vous avec votre mot de passe.'
                if has_pin else 'Vérifiez votre OTP, connectez-vous, puis créez votre code transfert à 4 chiffres dans l’app.',
            },
            status_code=status.HTTP_201_CREATED
        )


# ── Vérification OTP ──────────────────────────────────────────────────────────

class VerifyOTPView(APIView):
    """
    POST /api/auth/verify-otp/
    Vérifie le code OTP reçu par SMS.
    """
    permission_classes = [AllowAny]
    throttle_classes = [OtpRateThrottle]

    @swagger_auto_schema(
        request_body=VerifyOTPSerializer,
        responses={200: 'Téléphone vérifié', 400: 'OTP invalide ou expiré'},
        operation_summary="Vérification OTP",
    )
    def post(self, request):
        serializer = VerifyOTPSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(
                {'success': False, 'error': 'Données invalides', 'details': serializer.errors},
                status=status.HTTP_400_BAD_REQUEST
            )

        phone = serializer.validated_data['phone_number']
        otp_code = serializer.validated_data['otp']

        try:
            user = User.objects.get(phone_number=phone)
        except User.DoesNotExist:
            return Response(
                {'success': False, 'error': 'Utilisateur introuvable.'},
                status=status.HTTP_404_NOT_FOUND
            )

        if not OTPService.verify(user, otp_code):
            AuditService.log(user=user, action='OTP_FAILED',
                             ip_address=AuditService.get_client_ip(request))
            return Response(
                {'success': False, 'error': 'OTP invalide ou expiré.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        AuditService.log(user=user, action='OTP_VERIFIED',
                         ip_address=AuditService.get_client_ip(request))

        return success_response({'message': 'Téléphone vérifié avec succès.'})


# ── Connexion (Login JWT) ─────────────────────────────────────────────────────

class LoginView(APIView):
    """
    POST /api/auth/login/
    Nouveau : {phone_number, password} pour l'app internet.
    Rétro-compat : {phone_number, pin} toujours accepté (anciens comptes/USSD).
    Si password fourni -> vérifié en priorité, sinon fallback PIN.
    PIN 4 chiffres = uniquement pour les transferts/débits, plus pour le login web.
    """
    permission_classes = [AllowAny]
    throttle_classes = [LoginRateThrottle]

    @swagger_auto_schema(
        request_body=LoginSerializer,
        responses={
            200: openapi.Response('Tokens JWT', schema=openapi.Schema(
                type=openapi.TYPE_OBJECT,
                properties={
                    'access': openapi.Schema(type=openapi.TYPE_STRING),
                    'refresh': openapi.Schema(type=openapi.TYPE_STRING),
                }
            )),
            401: 'Identifiants incorrects',
            403: 'Compte bloqué',
        },
        operation_summary="Connexion",
        operation_description="Password en priorité, PIN en fallback compat. Blocage après 3 échecs."
    )
    def post(self, request):
        serializer = LoginSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(
                {'success': False, 'error': 'Données invalides', 'details': serializer.errors},
                status=status.HTTP_400_BAD_REQUEST
            )

        phone = serializer.validated_data['phone_number']
        # Normalisation douce : accepte 61XXXXXXXX, 06.., 257.., +257..
        try:
            from .phone_utils import normalize_phone
            phone = normalize_phone(phone)
        except Exception:
            pass
        password = serializer.validated_data.get('password') or ''
        pin = serializer.validated_data.get('pin') or ''

        try:
            user = User.objects.get(phone_number=phone)
        except User.DoesNotExist:
            AuditService.log(user=None, action='LOGIN_FAILED',
                             ip_address=AuditService.get_client_ip(request),
                             details={'phone': phone, 'reason': 'unknown'})
            return Response(
                {'success': False, 'error': 'Identifiants incorrects.'},
                status=status.HTTP_401_UNAUTHORIZED
            )

        # Vérification compte bloqué
        if user.is_blocked:
            return Response(
                {'success': False, 'error': 'Compte bloqué après 3 tentatives. Contactez le support.'},
                status=status.HTTP_403_FORBIDDEN
            )

        # Vérification compte actif
        if not user.is_active:
            return Response(
                {'success': False, 'error': 'Compte désactivé.'},
                status=status.HTTP_403_FORBIDDEN
            )

        # Vérification téléphone vérifié
        if not user.is_phone_verified:
            return Response(
                {'success': False, 'error': 'Téléphone non vérifié. Vérifiez votre OTP.'},
                status=status.HTTP_403_FORBIDDEN
            )

        # Vérification identifiants : password d'abord, PIN en fallback
        auth_ok = False
        auth_mode = None
        if password:
            try:
                auth_ok = user.check_password(password)
            except Exception:
                auth_ok = False
            auth_mode = 'password' if auth_ok else None
        if not auth_ok and pin:
            auth_ok = user.check_pin(pin)
            auth_mode = 'pin' if auth_ok else None
        # Si password fourni mais faux, on n'essaie pas le PIN vide -> échec direct
        if not auth_ok:
            user.failed_pin_attempts += 1
            max_attempts = settings.MAX_PIN_ATTEMPTS

            AuditService.log(user=user, action='LOGIN_FAILED',
                             ip_address=AuditService.get_client_ip(request),
                             details={'phone': phone, 'mode': 'password' if password else 'pin'})

            if user.failed_pin_attempts >= max_attempts:
                user.is_blocked = True
                user.save(update_fields=['failed_pin_attempts', 'is_blocked'])
                AuditService.log(user=user, action='ACCOUNT_BLOCKED',
                                 ip_address=AuditService.get_client_ip(request))
                return Response(
                    {'success': False, 'error': f'Compte bloqué après {max_attempts} tentatives échouées.'},
                    status=status.HTTP_403_FORBIDDEN
                )

            user.save(update_fields=['failed_pin_attempts'])
            tentatives_restantes = max_attempts - user.failed_pin_attempts
            msg = 'Mot de passe incorrect.' if password else 'PIN incorrect.'
            return Response(
                {'success': False, 'error': f'{msg} {tentatives_restantes} tentative(s) restante(s).'},
                status=status.HTTP_401_UNAUTHORIZED
            )

        # Succès : réinitialise les tentatives et génère les tokens
        user.failed_pin_attempts = 0
        user.save(update_fields=['failed_pin_attempts'])

        refresh = RefreshToken.for_user(user)

        AuditService.log(user=user, action='LOGIN',
                         ip_address=AuditService.get_client_ip(request),
                         details={'mode': auth_mode or 'password'})
        logger.info(f"Connexion réussie : {user.phone_number} via {auth_mode}")

        try:
            from .phone_utils import operator_of, is_lumitel
            _op = operator_of(user.phone_number)
            _is_lumi = is_lumitel(user.phone_number)
        except Exception:
            _op, _is_lumi = 'INCONNU', False
        return success_response({
            'access': str(refresh.access_token),
            'refresh': str(refresh),
            'auth_mode': auth_mode,
            'user': {
                'id': str(user.id),
                'phone_number': user.phone_number,
                'full_name': user.get_full_name(),
                'role': user.role,
                'has_pin': bool(user.pin),
                'operator': _op,
                'is_lumitel': _is_lumi,
            },
            'need_pin': not bool(user.pin),
            'pin_message': None if user.pin else 'Créez votre code transfert à 4 chiffres dans l’app (Sécurité). Il servira uniquement pour les transferts.',
        })


# ── Déconnexion ───────────────────────────────────────────────────────────────

class LogoutView(APIView):
    """
    POST /api/auth/logout/
    Révoque le refresh token (blacklist JWT).
    """
    permission_classes = [IsAuthenticated]

    @swagger_auto_schema(
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            properties={'refresh': openapi.Schema(type=openapi.TYPE_STRING)},
            required=['refresh']
        ),
        responses={200: 'Déconnecté', 400: 'Token invalide'},
        operation_summary="Déconnexion",
    )
    def post(self, request):
        try:
            refresh_token = request.data.get('refresh')
            token = RefreshToken(refresh_token)
            token.blacklist()
            AuditService.log(user=request.user, action='LOGOUT',
                             ip_address=AuditService.get_client_ip(request))
            return success_response({'message': 'Déconnecté avec succès.'})
        except TokenError:
            return Response(
                {'success': False, 'error': 'Token invalide ou déjà révoqué.'},
                status=status.HTTP_400_BAD_REQUEST
            )


# ── Profil Utilisateur ────────────────────────────────────────────────────────

class ProfileView(APIView):
    """
    GET /api/auth/profile/
    Retourne le profil complet de l'utilisateur connecté.
    """
    permission_classes = [IsAuthenticated]

    @swagger_auto_schema(
        responses={200: UserProfileSerializer},
        operation_summary="Mon profil",
    )
    def get(self, request):
        serializer = UserProfileSerializer(request.user)
        return success_response({'user': serializer.data})


# ── Changement de PIN ─────────────────────────────────────────────────────────

class ChangePinView(APIView):
    """
    POST /api/auth/change-pin/
    Permet de changer son PIN en fournissant l'ancien.
    """
    permission_classes = [IsAuthenticated]

    @swagger_auto_schema(
        request_body=ChangePinSerializer,
        responses={200: 'PIN modifié', 400: 'PIN actuel incorrect'},
        operation_summary="Changer le PIN",
    )
    def post(self, request):
        serializer = ChangePinSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(
                {'success': False, 'error': 'Données invalides', 'details': serializer.errors},
                status=status.HTTP_400_BAD_REQUEST
            )

        user = request.user
        current_pin = serializer.validated_data['current_pin']
        new_pin = serializer.validated_data['new_pin']

        if not user.check_pin(current_pin):
            return Response(
                {'success': False, 'error': 'PIN actuel incorrect.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        user.set_pin(new_pin)
        user.save(update_fields=['pin'])

        AuditService.log(user=user, action='PIN_CHANGED',
                         ip_address=AuditService.get_client_ip(request))

        return success_response({'message': 'PIN modifié avec succès.'})


# ── Création PIN transfert depuis l'intérieur (AJOUT SEUL) ─────────────────

class SetPinView(APIView):
    """
    POST /api/auth/set-pin/ {pin, confirm_pin} — connecté uniquement.
    Crée le code transfert 4 chiffres quand l'utilisateur est déjà dans l'app.
    - Si PIN déjà existant -> 400, utiliser change-pin.
    - PIN = uniquement pour débits/transferts, jamais pour le login web.
    """
    permission_classes = [IsAuthenticated]

    @swagger_auto_schema(
        request_body=SetPinSerializer,
        responses={200: 'Code transfert créé', 400: 'Déjà existant / invalide'},
        operation_summary="Créer mon code transfert",
    )
    def post(self, request):
        from .serializers import SetPinSerializer
        s = SetPinSerializer(data=request.data)
        if not s.is_valid():
            return Response(
                {'success': False, 'error': 'Données invalides', 'details': s.errors},
                status=status.HTTP_400_BAD_REQUEST
            )
        user = request.user
        if user.pin:
            return Response(
                {'success': False, 'error': 'Code déjà créé. Utilisez Changer code pour le modifier.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        user.set_pin(s.validated_data['pin'])
        user.save(update_fields=['pin'])
        AuditService.log(user=user, action='PIN_CREATED',
                         ip_address=AuditService.get_client_ip(request))
        return success_response({'message': 'Code transfert à 4 chiffres créé. Il sera demandé pour chaque transfert.', 'has_pin': True})


# ── Renvoyer OTP ──────────────────────────────────────────────────────────────

class ResendOTPView(APIView):
    """
    POST /api/auth/resend-otp/
    Renvoie un nouvel OTP par SMS.
    """
    permission_classes = [AllowAny]
    throttle_classes = [OtpRateThrottle]

    @swagger_auto_schema(
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            properties={'phone_number': openapi.Schema(type=openapi.TYPE_STRING)},
            required=['phone_number']
        ),
        responses={200: 'OTP renvoyé'},
        operation_summary="Renvoyer OTP",
    )
    def post(self, request):
        phone = request.data.get('phone_number')
        try:
            user = User.objects.get(phone_number=phone, is_phone_verified=False)
        except User.DoesNotExist:
            return Response(
                {'success': False, 'error': 'Utilisateur introuvable ou déjà vérifié.'},
                status=status.HTTP_404_NOT_FOUND
            )

        OTPService.send_otp(user)
        return success_response({'message': f'OTP renvoyé au {phone}.'})


# ── Blocage / Déblocage compte (AJOUT SEUL — ADMIN) ────────────────────────

class BlockUserView(APIView):
    """
    POST /api/auth/block/ {phone_number, reason} — ADMIN seul.
    Bloque client ou agent + gèle son wallet. Irréversible sauf unblock.
    """
    permission_classes = [IsAuthenticated]

    def post(self, request):
        from apps.wallet.models import Wallet
        if request.user.role != 'ADMIN' and not request.user.is_staff:
            return Response({'success': False, 'error': 'Réservé ADMIN.'}, status=403)
        phone = (request.data.get('phone_number') or '').strip()
        reason = (request.data.get('reason') or '').strip()
        if not phone:
            return Response({'success': False, 'error': 'Numéro requis.'}, status=400)
        try:
            target = User.objects.get(phone_number=phone)
        except User.DoesNotExist:
            return Response({'success': False, 'error': 'Compte introuvable.'}, status=404)
        if target.is_superuser:
            return Response({'success': False, 'error': 'Superuser non bloquable.'}, status=400)
        target.is_blocked = True
        target.failed_pin_attempts = 0
        target.save(update_fields=['is_blocked', 'failed_pin_attempts'])
        try:
            target.wallet.status = Wallet.Status.FROZEN
            target.wallet.save(update_fields=['status'])
        except Exception:
            pass
        AuditService.log(user=request.user, action='ACCOUNT_BLOCKED_MANUAL',
                         ip_address=AuditService.get_client_ip(request),
                         details={'target': phone, 'reason': reason})
        try:
            from .services import SMSService
            SMSService.send_async(phone, "Swisderm Pay: Votre compte est bloqué. Contactez le support.")
        except Exception:
            pass
        return success_response({'message': f'Compte {phone} bloqué ({target.role}).'})


class UnblockUserView(APIView):
    """
    POST /api/auth/unblock/ {phone_number} — ADMIN seul.
    Débloque + réactive le wallet.
    """
    permission_classes = [IsAuthenticated]

    def post(self, request):
        from apps.wallet.models import Wallet
        if request.user.role != 'ADMIN' and not request.user.is_staff:
            return Response({'success': False, 'error': 'Réservé ADMIN.'}, status=403)
        phone = (request.data.get('phone_number') or '').strip()
        if not phone:
            return Response({'success': False, 'error': 'Numéro requis.'}, status=400)
        try:
            target = User.objects.get(phone_number=phone)
        except User.DoesNotExist:
            return Response({'success': False, 'error': 'Compte introuvable.'}, status=404)
        target.is_blocked = False
        target.failed_pin_attempts = 0
        target.save(update_fields=['is_blocked', 'failed_pin_attempts'])
        try:
            if target.wallet.status == Wallet.Status.FROZEN:
                target.wallet.status = Wallet.Status.ACTIVE
                target.wallet.save(update_fields=['status'])
        except Exception:
            pass
        AuditService.log(user=request.user, action='ACCOUNT_UNBLOCKED',
                         ip_address=AuditService.get_client_ip(request),
                         details={'target': phone})
        return success_response({'message': f'Compte {phone} débloqué.'})


# ── Changer son propre mot de passe (connecté, TOUS rôles dont ADMIN) ───

class ChangePasswordView(APIView):
    """
    POST /api/auth/change-password/ {current_password, new_password, confirm_password}.
    Pour l'utilisateur connecté lui-même (client, agent ou admin).
    """
    permission_classes = [IsAuthenticated]

    def post(self, request):
        cur = request.data.get('current_password') or ''
        new = request.data.get('new_password') or ''
        conf = request.data.get('confirm_password') or ''
        user = request.user
        has_pwd = bool(user.password and not user.password.startswith('!'))
        if has_pwd and not user.check_password(cur):
            return Response({'success': False, 'error': 'Mot de passe actuel incorrect.'}, status=400)
        if len(new) < 8:
            return Response({'success': False, 'error': 'Nouveau mot de passe : 8 caractères minimum.'}, status=400)
        if new != conf:
            return Response({'success': False, 'error': 'Les mots de passe ne correspondent pas.'}, status=400)
        user.set_password(new)
        user.save(update_fields=['password'])
        AuditService.log(user=user, action='PASSWORD_CHANGED',
                         ip_address=AuditService.get_client_ip(request))
        return success_response({'message': 'Mot de passe modifié. Reconnectez-vous.'})


# ── Reset password + changement numéro par l'ADMIN (AJOUT SEUL) ───────────

class AdminResetPasswordView(APIView):
    """
    POST /api/auth/admin/reset-password/ {phone_number, new_password} — ADMIN seul.
    Réinitialise le mot de passe connexion d'un client/agent. SMS notifié.
    """
    permission_classes = [IsAuthenticated]

    def post(self, request):
        if request.user.role != 'ADMIN' and not request.user.is_staff:
            return Response({'success': False, 'error': 'Réservé ADMIN.'}, status=403)
        phone = (request.data.get('phone_number') or '').strip()
        new_pwd = request.data.get('new_password') or ''
        if not phone:
            return Response({'success': False, 'error': 'Numéro requis.'}, status=400)
        if len(new_pwd) < 8:
            return Response({'success': False, 'error': 'Nouveau mot de passe : 8 caractères minimum.'}, status=400)
        try:
            target = User.objects.get(phone_number=phone)
        except User.DoesNotExist:
            return Response({'success': False, 'error': 'Compte introuvable.'}, status=404)
        if target.is_superuser and not request.user.is_superuser:
            return Response({'success': False, 'error': 'Superuser : seul un superuser peut le réinitialiser.'}, status=400)
        target.set_password(new_pwd)
        target.failed_pin_attempts = 0
        target.save(update_fields=['password', 'failed_pin_attempts'])
        AuditService.log(user=request.user, action='PASSWORD_RESET_ADMIN',
                         ip_address=AuditService.get_client_ip(request),
                         details={'target': phone})
        try:
            from .services import SMSService
            SMSService.send_async(phone, "Swisderm Pay: Votre mot de passe a été réinitialisé par le support. Connectez-vous avec le nouveau mot de passe.")
        except Exception:
            pass
        return success_response({'message': f'Mot de passe de {phone} réinitialisé.'})


class AdminChangePhoneView(APIView):
    """
    POST /api/auth/admin/change-phone/ {old_phone, new_phone} — ADMIN seul.
    Change le numéro identifiant d'un client/agent (ex : perte de SIM).
    Le nouveau numéro doit être libre et vérifié par OTP ensuite.
    """
    permission_classes = [IsAuthenticated]

    def post(self, request):
        if request.user.role != 'ADMIN' and not request.user.is_staff:
            return Response({'success': False, 'error': 'Réservé ADMIN.'}, status=403)
        old_phone = (request.data.get('old_phone') or '').strip()
        new_phone = (request.data.get('new_phone') or '').strip()
        if not old_phone or not new_phone:
            return Response({'success': False, 'error': 'Ancien + nouveau numéros requis.'}, status=400)
        try:
            from .phone_utils import normalize_phone
            new_phone = normalize_phone(new_phone)
        except ValueError as e:
            return Response({'success': False, 'error': str(e)}, status=400)
        try:
            target = User.objects.get(phone_number=old_phone)
        except User.DoesNotExist:
            return Response({'success': False, 'error': 'Compte introuvable.'}, status=404)
        if target.is_superuser and not request.user.is_superuser:
            return Response({'success': False, 'error': 'Numéro superuser : seul un superuser peut le changer.'}, status=400)
        if User.objects.filter(phone_number=new_phone).exists():
            return Response({'success': False, 'error': 'Nouveau numéro déjà utilisé.'}, status=400)
        target.phone_number = new_phone
        target.is_phone_verified = False
        target.otp = None
        target.otp_expires_at = None
        target.save(update_fields=['phone_number', 'is_phone_verified', 'otp', 'otp_expires_at'])
        from .services import OTPService
        OTPService.send_otp(target)
        AuditService.log(user=request.user, action='PHONE_CHANGED_ADMIN',
                         ip_address=AuditService.get_client_ip(request),
                         details={'old': old_phone, 'new': new_phone})
        return success_response({
            'message': f'Numéro changé : {old_phone} → {new_phone}. OTP envoyé au nouveau numéro.',
            'phone_number': new_phone,
        })


class AdminUpdateAccountView(APIView):
    """
    POST /api/auth/admin/update-account/ {phone_number, first_name?, last_name?, role?} — ADMIN seul.
    Modifie le compte d'un client/agent depuis l'espace admin (nom, rôle).
    """
    permission_classes = [IsAuthenticated]

    def post(self, request):
        if request.user.role != 'ADMIN' and not request.user.is_staff:
            return Response({'success': False, 'error': 'Réservé ADMIN.'}, status=403)
        phone = (request.data.get('phone_number') or '').strip()
        if not phone:
            return Response({'success': False, 'error': 'Numéro requis.'}, status=400)
        try:
            target = User.objects.get(phone_number=phone)
        except User.DoesNotExist:
            return Response({'success': False, 'error': 'Compte introuvable.'}, status=404)
        if target.is_superuser and not request.user.is_superuser:
            return Response({'success': False, 'error': 'Superuser non modifiable.'}, status=400)
        changed = []
        fn = (request.data.get('first_name') or '').strip()
        ln = (request.data.get('last_name') or '').strip()
        role = (request.data.get('role') or '').strip().upper()
        if fn:
            target.first_name = fn
            changed.append('prénom')
        if ln:
            target.last_name = ln
            changed.append('nom')
        if role:
            if role not in ('USER', 'AGENT', 'ADMIN'):
                return Response({'success': False, 'error': 'Rôle invalide (USER/AGENT/ADMIN).'}, status=400)
            if role == 'ADMIN' and not request.user.is_superuser:
                return Response({'success': False, 'error': 'Passage ADMIN réservé superuser.'}, status=400)
            target.role = role
            target.is_staff = True if role == 'ADMIN' else (target.is_staff and target.is_superuser)
            changed.append('rôle')
        if not changed:
            return Response({'success': False, 'error': 'Rien à modifier (prénom, nom ou rôle).'}, status=400)
        target.save()
        AuditService.log(user=request.user, action='ACCOUNT_UPDATED_ADMIN',
                         ip_address=AuditService.get_client_ip(request),
                         details={'target': phone, 'changed': changed})
        return success_response({'message': f"Compte {phone} modifié ({', '.join(changed)}).",
                                 'user': {'phone_number': target.phone_number,
                                          'full_name': target.get_full_name(), 'role': target.role}})
