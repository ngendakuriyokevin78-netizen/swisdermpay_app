"""Vues Marchand : QR vendeur à scanner par le téléphone client (ajout seul)."""
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from drf_yasg.utils import swagger_auto_schema


class MyMerchantQRView(APIView):
    """
    GET /api/merchant/my-qr/?order_number=CMD-... ou ?sku=LAIT-500&qty=1
    Le vendeur Swisderm affiche ce QR (ou qr_data) ; le client le scanne
    avec /m/ -> transfert automatique.
    """
    permission_classes = [IsAuthenticated]

    @swagger_auto_schema(operation_summary="QR vendeur à faire scanner")
    def get(self, request):
        try:
            profile = request.user.merchant_profile
        except Exception:
            return Response({'success': False, 'error': 'Compte non marchand.'}, status=403)
        order_number = request.query_params.get('order_number', '')
        sku = request.query_params.get('sku', '')
        qty = request.query_params.get('qty', '1')
        if order_number:
            qr_data = f"SWISDERM:{profile.id}:{order_number}"
        elif sku:
            qr_data = f"SWISDERM:{profile.id}:{sku}:{qty}"
        else:
            qr_data = f"SWISDERM:{profile.id}"
        return Response({'success': True, 'qr_data': qr_data,
                         'merchant': profile.trade_name or profile.company_name})
