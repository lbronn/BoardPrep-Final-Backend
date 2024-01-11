import os 
from .settings import *
from .settings import BASE_DIR


SECRET_KEY = os.environ.get('SECRET')
ALLOWED_HOSTS = [os.environ.get('WEBSITE_HOSTNAME'), os.environ.get('GODADDY_HOSTNAME', 'boardprep-backend.com')]
CSRF_TRUSTED_ORIGINS = ['https://' + os.environ.get('WEBSITE_HOSTNAME', 'localhost:8000')]
DEBUG = True

# WhiteNoise configuration
MIDDLEWARE = [
    'corsheaders.middleware.CorsMiddleware',
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
] 

CORS_ORIGIN_ALLOW_ALL = True
CORS_ALLOWED_ORIGINS = [
    "https://boardprep.vercel.app",
    "http://localhost:3000",
    # ... other allowed origins ...
]

STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'
STATIC_ROOT = os.path.join(BASE_DIR, 'staticfiles')


DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.mysql',
        'NAME': os.environ.get('AZURE_MYSQL_NAME'),
        'HOST': os.environ.get('AZURE_MYSQL_HOST'),
        'USER': os.environ.get('AZURE_MYSQL_USER'),
        'PASSWORD': os.environ.get('AZURE_MYSQL_PASSWORD'),
    }
}