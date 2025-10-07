import os
from pathlib import Path
from datetime import timedelta

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = 'django-insecure-3_8*j1!u72&6_0@iv3$cyr4gis_xm5x_1ob2o!$#mxl!u97gg5'

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = True

ALLOWED_HOSTS = [
    'localhost',
    '127.0.0.1',
    'myalmet.com',
    'www.myalmet.com',
    '161.97.101.41',  # Server IP
]

# Application definition
INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    
    # Third-party apps
    'rest_framework',
    'rest_framework_simplejwt',
    'drf_yasg',
    'corsheaders',
    'django_filters',  
    'django_celery_beat',      # Beat scheduler
    'django_celery_results',

    # Local apps
    'api',
    'grading',  
]

MIDDLEWARE = [
    'corsheaders.middleware.CorsMiddleware',  # CORS-u ən başa qoyun
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'almet_hris_backend.urls'

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

WSGI_APPLICATION = 'almet_hris_backend.wsgi.application'

# Database - Local Configuration
# DATABASES = {
#     'default': {
#         'ENGINE': 'django.db.backends.postgresql',
#         'NAME': 'almet_hris',
#         'USER': 'postgres',
#         'PASSWORD': 'almet2025',  # Sizin qoyduğunuz parol
#         'HOST': 'localhost',
#         'PORT': '5432',
#         'CONN_MAX_AGE': 60,  # Connection pooling
#     }
# }

# Database - Server Configuration
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': 'myalmet_db',           # Bu adı dəyişin
        'USER': 'myalmet_user',         # Bu adı dəyişin
        'PASSWORD': 'almet2025',
        'HOST': 'localhost',
        'PORT': '5432',
    }
}

# Password validation
AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]

# Internationalization
LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'UTC'
USE_I18N = True
USE_TZ = True

# Static files (CSS, JavaScript, Images)
STATIC_URL = 'static/'
STATIC_ROOT = os.path.join(BASE_DIR, 'staticfiles')
# Default primary key field type
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# REST Framework settings
REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': [
        'rest_framework_simplejwt.authentication.JWTAuthentication',
    ],
    'DEFAULT_PARSER_CLASSES': [
        'rest_framework.parsers.JSONParser',
        'rest_framework.parsers.MultiPartParser',  # VACIB: File upload üçün
        'rest_framework.parsers.FormParser',        # VACIB: Form data üçün
    ],
    'DEFAULT_PERMISSION_CLASSES': [
        'rest_framework.permissions.IsAuthenticated',
    ],
    'DEFAULT_FILTER_BACKENDS': [
        'django_filters.rest_framework.DjangoFilterBackend',
        'rest_framework.filters.SearchFilter',
        'rest_framework.filters.OrderingFilter',
    ],
    'DEFAULT_PAGINATION_CLASS': 'rest_framework.pagination.PageNumberPagination',
    'PAGE_SIZE': 25,
}

# JWT Settings
SIMPLE_JWT = {
    'ACCESS_TOKEN_LIFETIME': timedelta(minutes=60),
    'REFRESH_TOKEN_LIFETIME': timedelta(days=1),
    'ROTATE_REFRESH_TOKENS': False,
    'ALGORITHM': 'HS256',
    'SIGNING_KEY': SECRET_KEY,
    'AUTH_HEADER_TYPES': ('Bearer',),
}

# Microsoft Azure App Registration settings
MICROSOFT_CLIENT_ID = "230458ff-ed69-4abb-8496-3888067116f6"
MICROSOFT_TENANT_ID = 'b3222ef7-242d-4724-a665-97b0a764f2d0'

# CORS settings - Frontend üçün
CORS_ALLOWED_ORIGINS = [
    "http://localhost:3000",
    "http://127.0.0.1:3000",
    "https://myalmet.com",
    "https://www.myalmet.com",
    
]

CORS_ALLOW_CREDENTIALS = True
CORS_ALLOW_ALL_ORIGINS = False  # Development üçün True edə bilərsiniz

# Enhanced Logging for Grading System
# LOGGING = {
#     'version': 1,
#     'disable_existing_loggers': False,
#     'formatters': {
#         'verbose': {
#             'format': '{levelname} {asctime} {module} {process:d} {thread:d} {message}',
#             'style': '{',
#         },
#         'simple': {
#             'format': '{levelname} {message}',
#             'style': '{',
#         },
#     },
#     'handlers': {
#         'console': {
#             'level': 'INFO',
#             'class': 'logging.StreamHandler',
#             'formatter': 'simple',
#         },
#         'file': {
#             'level': 'INFO',
#             'class': 'logging.FileHandler',
#             'filename': os.path.join(BASE_DIR, 'grading_system.log'),
#             'formatter': 'verbose',
#         },
#     },
#     'loggers': {
#         'grading': {
#             'handlers': ['console', 'file'],
#             'level': 'INFO',
#             'propagate': True,
#         },
#         'api': {
#             'handlers': ['console', 'file'],
#             'level': 'INFO',
#             'propagate': True,
#         },
#         'django.db.backends': {
#             'handlers': ['console'],
#             'level': 'WARNING',  # SQL query logging
#             'propagate': False,
#         },
#     },
#     'root': {
#         'handlers': ['console'],
#         'level': 'INFO',
#     },
# }

# Swagger JWT Settings
SWAGGER_SETTINGS = {
    'SECURITY_DEFINITIONS': {
        'Bearer': {
            'type': 'apiKey',
            'name': 'Authorization',
            'in': 'header',
            'description': 'JWT token. Format: Bearer <your_token>'
        }
    },
    'USE_SESSION_AUTH': False,
    'JSON_EDITOR': True,
    'SUPPORTED_SUBMIT_METHODS': [
        'get',
        'post',
        'put',
        'delete',
        'patch'
    ],
    'OPERATIONS_SORTER': 'alpha',
    'TAGS_SORTER': 'alpha',
    'DOC_EXPANSION': 'none',
    'DEEP_LINKING': True,
    'SHOW_EXTENSIONS': True,
    'DEFAULT_MODEL_RENDERING': 'model',
}

# Redoc settings
REDOC_SETTINGS = {
   'LAZY_RENDERING': False,
}

# Grading System Specific Settings
GRADING_SYSTEM_SETTINGS = {
    'DEFAULT_BASE_CURRENCY': 'AZN',
   
    'MAX_SCENARIOS_PER_SYSTEM': 50,  # Limit scenarios per grading system
    'AUTO_ARCHIVE_DAYS': 365,  # Auto archive old scenarios after 1 year
}

# Cache Configuration (for better performance with PostgreSQL)
CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.db.DatabaseCache',
        'LOCATION': 'cache_table',
        'TIMEOUT': 300,  # 5 minutes
        'OPTIONS': {
            'MAX_ENTRIES': 1000,
        }
    }
}

# Session configuration
SESSION_ENGINE = 'django.contrib.sessions.backends.db'
SESSION_COOKIE_AGE = 3600  # 1 hour
MEDIA_URL = '/media/'
MEDIA_ROOT = os.path.join(BASE_DIR, 'media')

# File Upload Settings
FILE_UPLOAD_MAX_MEMORY_SIZE = 50 * 1024 * 1024  # 50MB
DATA_UPLOAD_MAX_MEMORY_SIZE = 50 * 1024 * 1024   # 50MB

# File Storage Configuration
DEFAULT_FILE_STORAGE = 'django.core.files.storage.FileSystemStorage'

# CORS settings for file uploads
CORS_ALLOW_HEADERS = [
    'accept', 'accept-encoding', 'authorization', 'content-type', 
    'dnt', 'origin', 'user-agent', 'x-csrftoken', 'x-requested-with',
    'x-file-name', 'x-file-size', 'x-file-type',
]


#celery

# ==========================================
# CELERY CONFIGURATION - PostgreSQL Backend
# ==========================================

# Use SQLAlchemy database URL format for PostgreSQL
CELERY_BROKER_URL = 'db+postgresql://postgres:almet2025@localhost:5432/almet_hris'

# Result backend using django-celery-results
CELERY_RESULT_BACKEND = 'django-db'

# Task execution settings
CELERY_TASK_ALWAYS_EAGER = False
CELERY_TASK_EAGER_PROPAGATES = True

# Serialization
CELERY_ACCEPT_CONTENT = ['json']
CELERY_TASK_SERIALIZER = 'json'
CELERY_RESULT_SERIALIZER = 'json'

# Timezone
CELERY_TIMEZONE = 'Asia/Baku'
CELERY_ENABLE_UTC = True

# Beat scheduler
CELERY_BEAT_SCHEDULER = 'django_celery_beat.schedulers:DatabaseScheduler'

# Connection settings
CELERY_BROKER_CONNECTION_RETRY_ON_STARTUP = True
CELERY_BROKER_CONNECTION_RETRY = True
CELERY_BROKER_CONNECTION_MAX_RETRIES = 10