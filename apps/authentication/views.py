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
    UserProfileSerializer, ChangePinSerializer
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
        return success_response(
            {
                'message': f'Compte créé. Un OTP a été envoyé au {user.phone_number}.',
                'phone_number': user.phone_number,
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
    Authentifie l'utilisateur par numéro + PIN, retourne les tokens JWT.
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
        operation_description="Retourne access + refresh JWT. Blocage après 3 échecs PIN."
    )
    def post(self, request):
        serializer = LoginSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(
                {'success': False, 'error': 'Données invalides', 'details': serializer.errors},
                status=status.HTTP_400_BAD_REQUEST
            )

        phone = serializer.validated_data['phone_number']
        pin = serializer.validated_data['pin']

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

        # Vérification PIN
        if not user.check_pin(pin):
            user.failed_pin_attempts += 1
            max_attempts = settings.MAX_PIN_ATTEMPTS

            AuditService.log(user=user, action='LOGIN_FAILED',
                             ip_address=AuditService.get_client_ip(request),
                             details={'phone': phone})

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
            return Response(
                {'success': False, 'error': f'PIN incorrect. {tentatives_restantes} tentative(s) restante(s).'},
                status=status.HTTP_401_UNAUTHORIZED
            )

        # Succès : réinitialise les tentatives et génère les tokens
        user.failed_pin_attempts = 0
        user.save(update_fields=['failed_pin_attempts'])

        refresh = RefreshToken.for_user(user)

        AuditService.log(user=user, action='LOGIN',
                         ip_address=AuditService.get_client_ip(request))
        logger.info(f"Connexion réussie : {user.phone_number}")

        return success_response({
            'access': str(refresh.access_token),
            'refresh': str(refresh),
            'user': {
                'id': str(user.id),
                'phone_number': user.phone_number,
                'full_name': user.get_full_name(),
                'role': user.role,
            }
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
