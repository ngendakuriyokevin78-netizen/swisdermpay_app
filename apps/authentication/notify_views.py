"""
Notification SMS admin — AJOUT SEUL.
- POST /api/auth/notify/ {message} ADMIN -> tous les vérifiés (5000 max).
- POST /api/auth/notify/ {message, phone_number} ADMIN -> un client précis.
Réutilise SMSService.send_async (Celery si Redis, sinon synchrone).
"""
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from drf_yasg.utils import swagger_auto_schema
from rest_framework import serializers
from cashtel.throttles import StrictUserThrottle


class NotifySerializer(serializers.Serializer):
    message = serializers.CharField(min_length=1, max_length=320)
    phone_number = serializers.CharField(required=False, allow_blank=True, default='', max_length=20)


class AdminBroadcastView(APIView):
    permission_classes = [IsAuthenticated]
    throttle_classes = [StrictUserThrottle]

    @swagger_auto_schema(request_body=NotifySerializer, operation_summary="Notifier tous les clients (ADMIN)")
    def post(self, request):
        from .models import User
        from .services import AuditService, SMSService
        u = request.user
        if not (getattr(u, 'role', '') == 'ADMIN' or getattr(u, 'is_staff', False)):
            return Response({'success': False, 'error': 'Réservé ADMIN.'}, status=403)
        s = NotifySerializer(data=request.data)
        if not s.is_valid():
            return Response({'success': False, 'details': s.errors}, status=400)
        msg = 'Swisderm Pay: ' + s.validated_data['message'].strip()
        target = (s.validated_data.get('phone_number') or '').strip()
        if target:
            from .contacts_views import normalize_phone
            norm = normalize_phone(target)
            if not User.objects.filter(phone_number=norm, is_active=True).exists():
                return Response({'success': False, 'error': 'Client introuvable.'}, status=404)
            SMSService.send_async(norm, msg)
            AuditService.log(user=u, action='ADMIN_NOTIFY_ONE',
                             ip_address=AuditService.get_client_ip(request),
                             details={'phone': norm, 'message': msg})
            return Response({'success': True, 'message': f'Notification envoyée à {norm}.'})
        phones = list(User.objects.filter(is_active=True, is_phone_verified=True
                                          ).values_list('phone_number', flat=True)[:5000])
        n = 0
        for ph in phones:
            try:
                SMSService.send_async(ph, msg)
                n += 1
            except Exception:
                pass
        AuditService.log(user=u, action='ADMIN_BROADCAST',
                         ip_address=AuditService.get_client_ip(request),
                         details={'message': msg, 'recipients': n})
        return Response({'success': True, 'message': f'Notification envoyée à {n} clients.'})
