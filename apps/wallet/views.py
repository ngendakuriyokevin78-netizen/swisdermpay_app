"""
Vues API pour le module Wallet Cash Tel.
"""
import logging
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework import status
from django.http import FileResponse
from drf_yasg.utils import swagger_auto_schema

from .serializers import WalletSerializer

logger = logging.getLogger('apps.wallet')


class WalletDetailView(APIView):
    """
    GET /api/wallet/me/
    Retourne le wallet et le solde de l'utilisateur connecté.
    """
    permission_classes = [IsAuthenticated]

    @swagger_auto_schema(
        responses={200: WalletSerializer},
        operation_summary="Mon Wallet",
        operation_description="Retourne le solde, le statut et le QR code de votre wallet."
    )
    def get(self, request):
        try:
            wallet = request.user.wallet
        except Exception:
            return Response(
                {'success': False, 'error': 'Wallet introuvable.'},
                status=status.HTTP_404_NOT_FOUND
            )


class WalletQRAmountView(APIView):
    """
    GET /api/wallet/qr-amount/?amount=5000
    QR avec montant intégré : le payeur scanne et paie SANS saisir le montant.
    Format : SWISDERMPAY:{wallet_id}:{phone}:{montant}
    """
    permission_classes = [IsAuthenticated]

    @swagger_auto_schema(operation_summary="QR avec montant intégré (PNG)")
    def get(self, request):
        import qrcode
        from io import BytesIO
        from decimal import Decimal, InvalidOperation
        from django.http import HttpResponse
        try:
            wallet = request.user.wallet
        except Exception:
            return Response({'success': False, 'error': 'Wallet introuvable.'},
                            status=status.HTTP_404_NOT_FOUND)
        try:
            from decimal import Decimal, ROUND_DOWN
            amount = Decimal(str(request.query_params.get('amount', '')))
            # 3 décimales max, SANS arrondi (troncature exacte)
            amount = amount.quantize(Decimal('0.001'), rounding=ROUND_DOWN)
            if amount <= 0:
                raise InvalidOperation
        except (InvalidOperation, ValueError, TypeError, AttributeError):
            return Response({'success': False, 'error': 'Montant BIF requis (3 décimales max).'},
                            status=status.HTTP_400_BAD_REQUEST)
        # QR = format machine (point décimal, sans espaces) pour rester scannable ;
        # l'affichage français (virgule) est réservé aux écrans/SMS.
        qr_num = f"{amount.normalize():f}"
        qr_data = f"SWISDERMPAY:{wallet.wallet_id}:{wallet.user.phone_number}:{qr_num}"
        qr = qrcode.QRCode(version=1, error_correction=qrcode.constants.ERROR_CORRECT_M,
                           box_size=10, border=4)
        qr.add_data(qr_data)
        qr.make(fit=True)
        img = qr.make_image(fill_color='#1a1a2e', back_color='white')
        buf = BytesIO()
        img.save(buf, format='PNG')
        resp = HttpResponse(buf.getvalue(), content_type='image/png')
        resp['X-QR-Data'] = qr_data
        return resp

        serializer = WalletSerializer(wallet, context={'request': request})
        return Response({'success': True, 'wallet': serializer.data})


class WalletQRCodeView(APIView):
    """
    GET /api/wallet/qr/
    Retourne l'image QR code du wallet en PNG.
    """
    permission_classes = [IsAuthenticated]

    @swagger_auto_schema(
        responses={200: 'Image PNG du QR Code'},
        operation_summary="QR Code Wallet",
        operation_description=(
            "Télécharge le QR Code PNG à scanner pour recevoir un paiement. "
            "Format encodé : SWISDERMPAY:{wallet_id}:{phone}"
        )
    )
    def get(self, request):
        try:
            wallet = request.user.wallet
        except Exception:
            return Response(
                {'success': False, 'error': 'Wallet introuvable.'},
                status=status.HTTP_404_NOT_FOUND
            )

        # Régénère le QR si manquant
        if not wallet.qr_code:
            wallet.generate_qr_code()
            wallet.save()

        try:
            return FileResponse(
                wallet.qr_code.open('rb'),
                content_type='image/png',
                as_attachment=False,
                filename=f"cashtel_qr_{wallet.user.phone_number}.png"
            )
        except Exception as e:
            logger.error(f"Erreur génération QR pour {request.user.phone_number}: {e}")
            return Response(
                {'success': False, 'error': 'Impossible de générer le QR code.'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class WalletQRDataView(APIView):
    """
    GET /api/wallet/qr-data/
    Retourne les données brutes du QR code en JSON.
    """
    permission_classes = [IsAuthenticated]

    @swagger_auto_schema(
        operation_summary="Données QR Code",
        operation_description="Retourne la chaîne QR à encoder : SWISDERMPAY:{wallet_id}:{phone}"
    )
    def get(self, request):
        try:
            wallet = request.user.wallet
            return Response({
                'success': True,
                'qr_data': wallet.qr_data,
                'wallet_id': str(wallet.wallet_id),
                'phone_number': wallet.user.phone_number,
            })
        except Exception:
            return Response(
                {'success': False, 'error': 'Wallet introuvable.'},
                status=status.HTTP_404_NOT_FOUND
            )
