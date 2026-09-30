"""URLs pour l'authentification Cash Tel."""
from django.urls import path
from rest_framework_simplejwt.views import TokenRefreshView
from . import views
from . import contacts_views  # AJOUT contacts (aucune route existante modifiée)
from . import security_views  # AJOUT surveillance admin
from . import maintenance_views  # AJOUT maintenance
from . import notify_views  # AJOUT broadcast SMS admin

app_name = 'authentication'

urlpatterns = [
    # Inscription et vérification
    path('register/', views.RegisterView.as_view(), name='register'),
    path('verify-otp/', views.VerifyOTPView.as_view(), name='verify-otp'),
    path('resend-otp/', views.ResendOTPView.as_view(), name='resend-otp'),

    # Authentification JWT
    path('login/', views.LoginView.as_view(), name='login'),
    path('logout/', views.LogoutView.as_view(), name='logout'),
    path('token/refresh/', TokenRefreshView.as_view(), name='token-refresh'),

    # Profil
    path('profile/', views.ProfileView.as_view(), name='profile'),
    path('set-pin/', views.SetPinView.as_view(), name='set-pin'),
    path('change-pin/', views.ChangePinView.as_view(), name='change-pin'),
    path('change-password/', views.ChangePasswordView.as_view(), name='change-password'),

    # Blocage compte client/agent (ADMIN, ajout seul)
    path('block/', views.BlockUserView.as_view(), name='block'),
    path('unblock/', views.UnblockUserView.as_view(), name='unblock'),
    # Reset password + changement numéro + modif compte (ADMIN siège, ajout seul)
    path('admin/reset-password/', views.AdminResetPasswordView.as_view(), name='admin-reset-password'),
    path('admin/change-phone/', views.AdminChangePhoneView.as_view(), name='admin-change-phone'),
    path('admin/update-account/', views.AdminUpdateAccountView.as_view(), name='admin-update-account'),
    # Contacts : noms correspondants + récents (ajout seul)
    path('contacts/resolve/', contacts_views.ContactResolveView.as_view(), name='contacts-resolve'),
    path('contacts/recent/', contacts_views.RecentContactsView.as_view(), name='contacts-recent'),
    path('contacts/lookup/', contacts_views.LookupOneView.as_view(), name='contacts-lookup'),
    path('contacts/import/', contacts_views.ContactImportView.as_view(), name='contacts-import'),
    # Surveillance intrusion/vol ADMIN (ajout seul)
    path('security/summary/', security_views.SecuritySummaryView.as_view(), name='security-summary'),
    path('security/events/', security_views.SecurityEventsView.as_view(), name='security-events'),
    # Maintenance / réparation (ajout seul)
    path('maintenance/status/', maintenance_views.MaintenanceStatusView.as_view(), name='maintenance-status'),
    path('maintenance/set/', maintenance_views.MaintenanceSetView.as_view(), name='maintenance-set'),
    path('maintenance/clear/', maintenance_views.MaintenanceClearView.as_view(), name='maintenance-clear'),
    # Broadcast SMS admin (ajout seul)
    path('notify/', notify_views.AdminBroadcastView.as_view(), name='admin-notify'),
]
