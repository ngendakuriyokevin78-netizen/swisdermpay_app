"""
Maintenance / réparation — AJOUT SEUL.
- GET  /api/auth/maintenance/status/ (public : PWA affiche bannière)
- POST /api/auth/maintenance/set/ {duration_minutes, reason} ADMIN
- POST /api/auth/maintenance/clear/ ADMIN
"""
from datetime import timedelta
from django.utils import timezone
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import AllowAny, IsAuthenticated
from drf_yasg.utils import swagger_auto_schema
from rest_framework import serializers


class SetSerializer(serializers.Serializer):
    duration_minutes = serializers.IntegerField(min_value=1, max_value=1440)
    reason = serializers.CharField(required=False, allow_blank=True, default='', max_length=255)


def _is_admin(u):
    return (u.role == 'ADMIN' or u.is_staff) if u and u.is_authenticated else False


def _payload(mw):
    if not mw:
        return {'active': False}
    now = timezone.now()
    remain = max(0, int((mw.ends_at - now).total_seconds() // 60))
    return {'active': True, 'reason': mw.reason, 'ends_at': mw.ends_at,
            'remaining_minutes': remain}


class MaintenanceStatusView(APIView):
    permission_classes = [AllowAny]

    @swagger_auto_schema(operation_summary="État maintenance (public)")
    def get(self, request):
        from .models import MaintenanceWindow
        return Response({'success': True, **_payload(MaintenanceWindow.current())})


class MaintenanceSetView(APIView):
    permission_classes = [IsAuthenticated]

    @swagger_auto_schema(request_body=SetSerializer, operation_summary="Programmer coupure (ADMIN)")
    def post(self, request):
        from .models import MaintenanceWindow
        from .services import AuditService
        if not _is_admin(request.user):
            return Response({'success': False, 'error': 'Réservé ADMIN.'}, status=403)
        s = SetSerializer(data=request.data)
        if not s.is_valid():
            return Response({'success': False, 'details': s.errors}, status=400)
        # Coupe l'ancienne fenêtre encore active (ajout seul, pas de suppression)
        now = timezone.now()
        MaintenanceWindow.objects.filter(enabled=True, ends_at__gt=now).update(enabled=False)
        mw = MaintenanceWindow.objects.create(
            reason=s.validated_data.get('reason', ''),
            starts_at=now,
            ends_at=now + timedelta(minutes=s.validated_data['duration_minutes']),
            enabled=True, created_by=request.user,
        )
        AuditService.log(user=request.user, action='MAINTENANCE_SET',
                         ip_address=AuditService.get_client_ip(request),
                         details={'minutes': s.validated_data['duration_minutes'],
                                  'reason': mw.reason})
        # Notification clients (ajout seul : SMS broadcast + bannière PWA via status)
        try:
            from .services import SMSService
            from .models import User
            mins = s.validated_data['duration_minutes']
            msg = f"Swisderm Pay: Service interrompu {mins} min pour réparation ({mw.reason or 'maintenance'}). Reprise prévue. Merci."
            for ph in User.objects.filter(is_active=True, is_phone_verified=True).values_list('phone_number', flat=True)[:5000]:
                SMSService.send_async(ph, msg)
        except Exception:
            pass
        return Response({'success': True, 'message': f"Service interrompu {s.validated_data['duration_minutes']} min.",
                         **_payload(mw)})


class MaintenanceClearView(APIView):
    permission_classes = [IsAuthenticated]

    @swagger_auto_schema(operation_summary="Reprendre le service (ADMIN)")
    def post(self, request):
        from .models import MaintenanceWindow
        from .services import AuditService
        if not _is_admin(request.user):
            return Response({'success': False, 'error': 'Réservé ADMIN.'}, status=403)
        now = timezone.now()
        n = MaintenanceWindow.objects.filter(enabled=True, ends_at__gt=now).update(enabled=False)
        AuditService.log(user=request.user, action='MAINTENANCE_CLEARED',
                         ip_address=AuditService.get_client_ip(request))
        try:
            from .services import SMSService
            from .models import User
            for ph in User.objects.filter(is_active=True, is_phone_verified=True).values_list('phone_number', flat=True)[:5000]:
                SMSService.send_async(ph, "Swisderm Pay: Service repris. Merci de votre patience.")
        except Exception:
            pass
        return Response({'success': True, 'message': 'Service repris.' if n else 'Aucune coupure active.'})
