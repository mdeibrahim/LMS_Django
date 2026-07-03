from datetime import timedelta
from pathlib import Path

import dj_database_url
from decouple import config

from .unfold_config import UNFOLD


BASE_DIR = Path(__file__).resolve().parent.parent


def _cast_debug(value):
    if isinstance(value, bool):
        return value
    normalized = str(value).strip().lower()
    if normalized in {"1", "true", "yes", "on", "debug", "development"}:
        return True
    if normalized in {"0", "false", "no", "off", "release", "production"}:
        return False
    return bool(value)


SECRET_KEY = config('SECRET_KEY', default='django-insecure-change-me')
DEBUG = config('DEBUG', default=True, cast=_cast_debug)
ALLOWED_HOSTS = [host.strip() for host in config('ALLOWED_HOSTS', default='*').split(',') if host.strip()]

def _parse_csv_setting(name, default):
    raw_value = config(name, default=default)
    if raw_value is None:
        raw_value = default

    raw_value = str(raw_value).strip()
    # Treat blank environment values as "unset" so defaults still apply.
    if not raw_value:
        raw_value = default

    normalized = raw_value.replace(';', ',')
    return [item.strip() for item in normalized.split(',') if item.strip()]


# CORS / CSRF settings for the React frontend.
CORS_ALLOWED_ORIGINS = _parse_csv_setting(
    'CORS_ALLOWED_ORIGINS',
    'http://localhost:3000,http://127.0.0.1:3000,https://test.lenscafestudio.com',
)
CORS_ALLOW_CREDENTIALS = config('CORS_ALLOW_CREDENTIALS', default=True, cast=_cast_debug)
CSRF_TRUSTED_ORIGINS = _parse_csv_setting(
    'CSRF_TRUSTED_ORIGINS',
    'http://localhost:3000,http://127.0.0.1:3000,https://test.lenscafestudio.com',
)


INSTALLED_APPS = [
    'unfold',
    'unfold.contrib.filters',
    'unfold.contrib.forms',
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'rest_framework',
    'rest_framework_simplejwt',
    'rest_framework_simplejwt.token_blacklist',
    'content',
    'apps.teacher_dashboard',
    'apps.student_dashboard',
]


MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'teaching_platform.cors.SimpleCorsMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]


ROOT_URLCONF = 'teaching_platform.urls'


TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
                'django.template.context_processors.debug',
                'django.template.context_processors.i18n',
                'django.template.context_processors.media',
                'django.template.context_processors.static',
                'django.template.context_processors.tz',
            ],
        },
    },
]


WSGI_APPLICATION = 'teaching_platform.wsgi.application'
ASGI_APPLICATION = 'teaching_platform.asgi.application'


DATABASES = {
    'default': dj_database_url.config(
        default=f'sqlite:///{BASE_DIR / "db.sqlite3"}',
        conn_max_age=600,
    )
}


AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]


LANGUAGE_CODE = 'en-us'
TIME_ZONE = config('TIME_ZONE', default='UTC')
USE_I18N = True
USE_TZ = True


STATIC_URL = '/static/'
STATICFILES_DIRS = [BASE_DIR / 'static']
STATIC_ROOT = BASE_DIR / 'staticfiles'
STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'

MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'


DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

AUTH_USER_MODEL = 'content.User'


LOGIN_URL = 'content:login'
LOGIN_REDIRECT_URL = 'content:home'
LOGOUT_REDIRECT_URL = 'content:home'


EMAIL_BACKEND = config('EMAIL_BACKEND', default='django.core.mail.backends.console.EmailBackend')
DEFAULT_FROM_EMAIL = config('DEFAULT_FROM_EMAIL', default='no-reply@example.com')
SERVER_EMAIL = config('SERVER_EMAIL', default=None)  # For admin notifications
EMAIL_HOST = config('EMAIL_HOST', default=None)
EMAIL_PORT = config('EMAIL_PORT', default=587, cast=int)
EMAIL_HOST_USER = config('EMAIL_HOST_USER', default=None)
EMAIL_HOST_PASSWORD = config('EMAIL_HOST_PASSWORD', default=None)
EMAIL_USE_TLS = config('EMAIL_USE_TLS', default=True, cast=_cast_debug)
EMAIL_USE_SSL = config('EMAIL_USE_SSL', default=False, cast=_cast_debug)
EMAIL_TIMEOUT = config('EMAIL_TIMEOUT', default=10, cast=int)

SITE_NAME = config('SITE_NAME', default='Teaching Platform')


SITE_URL = config('SITE_URL', default='http://localhost:8000')
OTP_ATTEMPT_WINDOW = config('OTP_ATTEMPT_WINDOW', default=300, cast=int)
OTP_ATTEMPT_LIMIT = config('OTP_ATTEMPT_LIMIT', default=5, cast=int)
OTP_LOCKOUT_SECONDS = config('OTP_LOCKOUT_SECONDS', default=600, cast=int)
OTP_RESEND_WINDOW = config('OTP_RESEND_WINDOW', default=900, cast=int)
OTP_RESEND_LIMIT = config('OTP_RESEND_LIMIT', default=3, cast=int)


REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': (
        'rest_framework.authentication.SessionAuthentication',
        'rest_framework_simplejwt.authentication.JWTAuthentication',
    ),
    'DEFAULT_PERMISSION_CLASSES': (
        'rest_framework.permissions.AllowAny',
    ),
}


SIMPLE_JWT = {
    'ACCESS_TOKEN_LIFETIME': timedelta(days=30),
    'REFRESH_TOKEN_LIFETIME': timedelta(days=60),
    'ROTATE_REFRESH_TOKENS': True,
    'BLACKLIST_AFTER_ROTATION': True,
}


UNFOLD = UNFOLD
