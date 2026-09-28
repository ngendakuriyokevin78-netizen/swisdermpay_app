"""
Surveillance intrusion/vol ADMIN — AJOUT SEUL.
Lit AuditLog existant, aucune migration, aucune logique métier modifiée.
- GET /api/auth/security/summary/?hours=24 -> compteurs + top phones/IP + alerte
- GET /api/auth/security/events/?hours=24&type=all|intrusion -> 100 derniers suspects
Actions suspectes : LOGIN_FAILED, OTP_FAILED, PIN_FAILED, ACCOUNT_BLOCKED (+MANUAL).
"""
from datetime import timedelta
from django.utils import timezone
from django.db.models import Count
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated

SUSPECT = ['LOGIN_FAILED', 'OTP_FAILED', 'PIN_FAILED', 'ACCOUNT_BLOCKED',
           'ACCOUNT_BLOCKED_MANUAL']


def _is_admin(u):
    return (u.role == 'ADMIN' or u.is_staff) if u else False


class SecuritySummaryView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        if not _is_admin(request.user):
            return Response({'success': False, 'error': 'Réservé ADMIN.'}, status=403)
        from apps.authentication.models import AuditLog
        try:
            hours = max(1, min(168, int(request.query_params.get('hours', 24))))
        except ValueError:
            hours = 24
        since = timezone.now() - timedelta(hours=hours)
        qs = AuditLog.objects.filter(created_at__gte=since, action__in=SUSPECT)
        by_action = list(qs.values('action').annotate(nb=Count('id')).order_by('-nb'))
        top_phones = list(qs.exclude(user__isnull=True).values(
            'user__phone_number').annotate(nb=Count('id')).order_by('-nb')[:10])
        top_ips = list(qs.exclude(ip_address__isnull=True).exclude(ip_address='').values(
            'ip_address').annotate(nb=Count('id')).order_by('-nb')[:10])
        total = qs.count()
        blocked = qs.filter(action__in=['ACCOUNT_BLOCKED', 'ACCOUNT_BLOCKED_MANUAL']).count()
        # Alerte simple : >=10 échecs ou >=3 blocages sur la période
        alert = total >= 10 or blocked >= 3
        level = 'CRITICAL' if blocked >= 3 or total >= 50 else ('WARNING' if alert else 'OK')
        return Response({'success': True, 'hours': hours, 'total_suspect': total,
                         'blocked': blocked, 'alert': alert, 'level': level,
                         'by_action': by_action, 'top_phones': top_phones, 'top_ips': top_ips})


class SecurityEventsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        if not _is_admin(request.user):
            return Response({'success': False, 'error': 'Réservé ADMIN.'}, status=403)
        from apps.authentication.models import AuditLog
        try:
            hours = max(1, min(168, int(request.query_params.get('hours', 24))))
        except ValueError:
            hours = 24
        ftype = (request.query_params.get('type') or 'intrusion').lower()
        since = timezone.now() - timedelta(hours=hours)
        qs = AuditLog.objects.select_related('user').filter(created_at__gte=since)
        if ftype == 'intrusion':
            qs = qs.filter(action__in=SUSPECT)
        qs = qs.order_by('-created_at')[:100]
        out = [{'at': l.created_at, 'action': l.action,
                'phone': l.user.phone_number if l.user else (l.details.get('phone') if isinstance(l.details, dict) else None),
                'ip': l.ip_address, 'details': l.details} for l in qs]
        return Response({'success': True, 'count': len(out), 'events': out})
