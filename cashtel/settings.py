"""
Configuration principale de Cash Tel.
Charge les variables d'environnement depuis le fichier .env.
"""
import environ
import os
from datetime import timedelta
from pathlib import Path

# ── Chemins ──────────────────────────────────────────────────────────────────
BASE_DIR = Path(__file__).resolve().parent.parent

# ── Variables d'environnement ─────────────────────────────────────────────────
env = environ.Env(DEBUG=(bool, False))
environ.Env.read_env(os.path.join(BASE_DIR, '.env'))

# ── Sécurité ──────────────────────────────────────────────────────────────────
SECRET_KEY = env('SECRET_KEY', default='django-insecure-dev-key-change-in-prod')
DEBUG = env('DEBUG', default=True)
ALLOWED_HOSTS = env.list('ALLOWED_HOSTS', default=['localhost', '127.0.0.1', '0.0.0.0'])

# ── Applications ──────────────────────────────────────────────────────────────
INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    # Tiers
    'rest_framework',
    'rest_framework_simplejwt',
    'rest_framework_simplejwt.token_blacklist',
    'corsheaders',
    'drf_yasg',
    'django_filters',
    # Applications Cash Tel
    'apps.authentication.apps.AuthenticationConfig',
    'apps.wallet.apps.WalletConfig',
    'apps.transactions.apps.TransactionsConfig',
    'apps.agent.apps.AgentConfig',
    'apps.bills.apps.BillsConfig',
    # Extensions Swisderm (ajout seul — tables nouvelles uniquement)
    'apps.merchant.apps.MerchantConfig',
    'apps.shop.apps.ShopConfig',
    'apps.banking.apps.BankingConfig',
    'apps.interop.apps.InteropConfig',
    'apps.mobile.apps.MobileConfig',
]

# ── Middleware ─────────────────────────────────────────────────────────────────
MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'corsheaders.middleware.CorsMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'cashtel.maintenance_mw.MaintenanceMiddleware',  # AJOUT maintenance (lecture libre, écritures bloquées sauf admin)
]

ROOT_URLCONF = 'cashtel.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'cashtel.wsgi.application'

# ── Base de données ────────────────────────────────────────────────────────────
DATABASES = {
    'default': env.db(
        'DATABASE_URL',
        default='postgres://cashtel:cashtel_password@db:5432/cashtel'
    )
}

# ── Modèle utilisateur personnalisé ───────────────────────────────────────────
AUTH_USER_MODEL = 'authentication.User'

# ── Validation des mots de passe ──────────────────────────────────────────────
AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

# ── Internationalisation ───────────────────────────────────────────────────────
LANGUAGE_CODE = 'fr-fr'
TIME_ZONE = 'Africa/Bujumbura'
USE_I18N = True
USE_TZ = True

# ── Fichiers statiques ─────────────────────────────────────────────────────────
STATIC_URL = '/static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'
STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'

# ── Fichiers médias (QR codes, etc.) ──────────────────────────────────────────
MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# ── Django REST Framework ──────────────────────────────────────────────────────
REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': [
        'rest_framework_simplejwt.authentication.JWTAuthentication',
    ],
    'DEFAULT_PERMISSION_CLASSES': [
        'rest_framework.permissions.IsAuthenticated',
    ],
    'DEFAULT_PAGINATION_CLASS': 'rest_framework.pagination.PageNumberPagination',
    'PAGE_SIZE': 20,
    'DEFAULT_FILTER_BACKENDS': [
        'django_filters.rest_framework.DjangoFilterBackend',
        'rest_framework.filters.OrderingFilter',
    ],
    'DEFAULT_RENDERER_CLASSES': [
        'rest_framework.renderers.JSONRenderer',
    ],
    'EXCEPTION_HANDLER': 'cashtel.exceptions.custom_exception_handler',
    # ── Anti-bruteforce (ajout seul, quotas larges pour ne pas casser l'usage normal)
    # Throttles résilients : ouverts si Redis indisponible (dev local Windows)
    'DEFAULT_THROTTLE_CLASSES': [
        'cashtel.throttles.ResilientAnonThrottle',
        'cashtel.throttles.ResilientUserThrottle',
    ],
    'DEFAULT_THROTTLE_RATES': {
        'anon': env('DRF_ANON_RATE', default='60/min'),
        'user': env('DRF_USER_RATE', default='300/min'),
        'login': env('DRF_LOGIN_RATE', default='10/min'),
        'otp': env('DRF_OTP_RATE', default='5/min'),
        'ussd': env('DRF_USSD_RATE', default='30/min'),
        'strict_user': env('DRF_STRICT_RATE', default='20/min'),
    },
}

# ── Passerelle opérateur USSD/SMS (ajout seul ; vide = ouvert en DEBUG, exigé en prod)
OPERATOR_API_KEY = env('OPERATOR_API_KEY', default='')
ALLOWED_USSD_IPS = env.list('ALLOWED_USSD_IPS', default=[])

# ── Durcissement prod (ajout seul ; actif si SECURE=True dans .env)
SECURE_MODE = env.bool('SECURE', default=False)
if SECURE_MODE:
    SECURE_SSL_REDIRECT = True
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_HSTS_SECONDS = 31536000
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD = True
    SECURE_CONTENT_TYPE_NOSNIFF = True
    X_FRAME_OPTIONS = 'DENY'

# ── JWT (Simple JWT) ───────────────────────────────────────────────────────────
SIMPLE_JWT = {
    'ACCESS_TOKEN_LIFETIME': timedelta(
        hours=env.int('JWT_ACCESS_TOKEN_LIFETIME_HOURS', default=1)
    ),
    'REFRESH_TOKEN_LIFETIME': timedelta(
        days=env.int('JWT_REFRESH_TOKEN_LIFETIME_DAYS', default=7)
    ),
    'ROTATE_REFRESH_TOKENS': True,
    'BLACKLIST_AFTER_ROTATION': True,
    'AUTH_HEADER_TYPES': ('Bearer',),
    'UPDATE_LAST_LOGIN': True,
}

# ── CORS ───────────────────────────────────────────────────────────────────────
CORS_ALLOWED_ORIGINS = env.list(
    'CORS_ALLOWED_ORIGINS',
    default=['http://localhost:3000', 'http://localhost:8080']
)
CORS_ALLOW_CREDENTIALS = True

# ── Celery ─────────────────────────────────────────────────────────────────────
REDIS_URL = env('REDIS_URL', default='redis://redis:6379/0')
CELERY_BROKER_URL = REDIS_URL
CELERY_RESULT_BACKEND = REDIS_URL
CELERY_ACCEPT_CONTENT = ['json']
CELERY_TASK_SERIALIZER = 'json'
CELERY_RESULT_SERIALIZER = 'json'
CELERY_TIMEZONE = TIME_ZONE

# ── Cache Redis ────────────────────────────────────────────────────────────────
CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.redis.RedisCache',
        'LOCATION': REDIS_URL,
    }
}

# ── Mode test : pas de Redis, Celery synchrone ─────────────────────────────────
import sys
if 'pytest' in sys.argv[0] or 'test' in sys.argv:
    CACHES = {'default': {'BACKEND': 'django.core.cache.backends.locmem.LocMemCache'}}
    CELERY_TASK_ALWAYS_EAGER = True
    CELERY_TASK_EAGER_PROPAGATES = True
    PASSWORD_HASHERS = ['django.contrib.auth.hashers.MD5PasswordHasher']

# ── Configuration SMS ──────────────────────────────────────────────────────────
SMS_BACKEND = env('SMS_BACKEND', default='mock')
AFRICAS_TALKING_USERNAME = env('AFRICAS_TALKING_USERNAME', default='')
AFRICAS_TALKING_API_KEY = env('AFRICAS_TALKING_API_KEY', default='')
AFRICAS_TALKING_SENDER_ID = env('AFRICAS_TALKING_SENDER_ID', default='SwisdermPay')

# ── Règles métier ──────────────────────────────────────────────────────────────
MAX_PIN_ATTEMPTS = env.int('MAX_PIN_ATTEMPTS', default=3)
OTP_EXPIRY_MINUTES = env.int('OTP_EXPIRY_MINUTES', default=10)
MIN_TRANSFER_AMOUNT = env.int('MIN_TRANSFER_AMOUNT', default=100)

# ── Swagger / drf-yasg ─────────────────────────────────────────────────────────
SWAGGER_SETTINGS = {
    'SECURITY_DEFINITIONS': {
        'Bearer': {
            'type': 'apiKey',
            'name': 'Authorization',
            'in': 'header',
        }
    },
    'USE_SESSION_AUTH': False,
    'JSON_EDITOR': True,
}

# ── Logging ────────────────────────────────────────────────────────────────────
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {
            'format': '[{levelname}] {asctime} {module} {message}',
            'style': '{',
        },
    },
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
            'formatter': 'verbose',
        },
    },
    'root': {
        'handlers': ['console'],
        'level': 'INFO',
    },
    'loggers': {
        'cashtel': {
            'handlers': ['console'],
            'level': 'DEBUG',
            'propagate': False,
        },
        'apps': {
            'handlers': ['console'],
            'level': 'DEBUG',
            'propagate': False,
        },
    },
}
