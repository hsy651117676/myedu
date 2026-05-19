from pathlib import Path
import os
from django.contrib import messages

# ==================== 基础配置 ====================
BASE_DIR = Path(__file__).resolve().parent.parent

# 安全警告：生产环境必须修改 SECRET_KEY
SECRET_KEY = os.environ.get(
    'DJANGO_SECRET_KEY',
    'django-insecure-7+3ayv)j!@*6u*l)ri+3ji#cg)d0-z80bn3(2#(ha6xjod53f('
)

# 调试模式（生产环境必须设为False）
DEBUG = os.environ.get('DJANGO_DEBUG', 'True').lower() == 'true'

ALLOWED_HOSTS = os.environ.get(
    'DJANGO_ALLOWED_HOSTS',
    'localhost,218.201.223.229,127.0.0.1,pzs.das.cn,pzsdas.com,das.edu,192.168.16.100,192.168.17.100,192.168.18.100'
).split(',')
LOGIN_URL = 'login'
LOGIN_REDIRECT_URL = 'home'
LOGOUT_REDIRECT_URL = 'login'
# ==================== 档案扫描图像配置 ====================

# 扫描图片存放根目录（加密存储）
SCAN_IMAGE_BASE_DIR = '/mnt/data/das_images'

# PDF输出根目录
SCAN_PDF_OUTPUT_DIR = '/mnt/data/das_pdf'

# 支持的图像类型
SCAN_IMAGE_TYPES = {
    'YS': '原始图像',
    'GQ': '高清图像',
}

# 加密密钥
SCAN_AES_KEY = b"3yj8jbvx" + b'\x00' * 8

# PDF默认设置
SCAN_PDF_PAGE_SIZE = 'A4'        # A3 / A4 / A5 / B5
SCAN_PDF_VERTICAL = True         # True纵向 / False横向
SCAN_PDF_MARGIN_UP = 1           # 上边距（磅）
SCAN_PDF_MARGIN_DOWN = 1         # 下边距（磅）
SCAN_PDF_MARGIN_LEFT = 1         # 左边距（磅）
SCAN_PDF_MARGIN_RIGHT = 1        # 右边距（磅）
SCAN_PDF_DPI = 150               # 输出DPI
SCAN_PDF_JPEG_QUALITY = 85       # JPEG压缩质量(1-100)

# ==================== 安全配置 ====================
# HTTPS设置
if not DEBUG:
    SECURE_SSL_REDIRECT = True
    SECURE_HSTS_SECONDS = 31536000  # 1年
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD = True
    SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
    USE_X_FORWARDED_HOST = True

# 会话安全配置
SESSION_EXPIRE_AT_BROWSER_CLOSE = True
SESSION_COOKIE_AGE = 60 * 60 * 8  # 8小时
SESSION_COOKIE_SECURE = not DEBUG  # 开发环境允许HTTP
CSRF_COOKIE_SECURE = not DEBUG
SESSION_COOKIE_HTTPONLY = True
CSRF_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = 'Lax'
CSRF_COOKIE_SAMESITE = 'Lax'

# 防止点击劫持
X_FRAME_OPTIONS = 'SAMEORIGIN'

# 信任的CSRF来源
CSRF_TRUSTED_ORIGINS = [
    "https://218.201.223.229:8341",
    "http://localhost:8000",
    "http://127.0.0.1:8000",
]
AUTHENTICATION_BACKENDS = [
    'main.backends.ArchiveAuthBackend',
    'django.contrib.auth.backends.ModelBackend',
]
# ==================== 应用配置 ====================

INSTALLED_APPS = [
    'simpleui',  # 管理后台主题
    'sslserver',
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'main',  # 主应用
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    # 'main.middleware.LoginJumpMiddleware',  # 如需iframe跳转则取消注释
]

ROOT_URLCONF = 'myedu.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
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

WSGI_APPLICATION = 'myedu.wsgi.application'

# ==================== 数据库配置 ====================

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.mysql',
        'NAME': os.environ.get('DB_NAME', 'myedu'),
        'USER': os.environ.get('DB_USER', 'root'),
        'PASSWORD': os.environ.get('DB_PASSWORD', '123456'),
        'HOST': os.environ.get('DB_HOST', '127.0.0.1'),
        'PORT': os.environ.get('DB_PORT', '3306'),
        'OPTIONS': {
            'charset': 'utf8mb4',
            'init_command': "SET sql_mode='STRICT_TRANS_TABLES'",
        },
        'CONN_MAX_AGE': 600,  # 连接池，10分钟
    }
}

# 人口数据库配置（外部数据库）
POPULATION_DB = {
    "DRIVER": "ODBC Driver 18 for SQL Server",
    "SERVER": "127.0.0.1",
    "PORT": "1433",
    "DATABASE": os.environ.get('POP_DB_NAME', 'rs_new'),
    "UID": os.environ.get('POP_DB_USER', 'sa'),
    "PWD": os.environ.get('POP_DB_PASSWORD', 'PzsjyjDas@3634122!@#'),
    "Encrypt": "Optional",
    "TrustServerCertificate": "Yes",
}

ARCHIVES_DB = {
    "DRIVER": "ODBC Driver 18 for SQL Server",
    "SERVER": "127.0.0.1",
    "PORT": "1433",
    "DATABASE": "rs_new",
    "UID": "sa",
    "PWD": "PzsjyjDas@3634122!@#",
    "Encrypt": "Optional",
    "TrustServerCertificate": "Yes",
}
# ==================== 密码验证 ====================

AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
        'OPTIONS': {
            'min_length': 8,
        }
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]

# 自定义密码哈希器（可选，增强安全性）
PASSWORD_HASHERS = [
    'django.contrib.auth.hashers.Argon2PasswordHasher',
    'django.contrib.auth.hashers.PBKDF2PasswordHasher',
    'django.contrib.auth.hashers.PBKDF2SHA1PasswordHasher',
    'django.contrib.auth.hashers.BCryptSHA256PasswordHasher',
]

# ==================== 缓存配置 ====================

CACHES = {
    "default": {
        "BACKEND": "django_redis.cache.RedisCache",
        "LOCATION": os.environ.get('REDIS_URL', 'redis://127.0.0.1:6379/0'),
        "OPTIONS": {
            "CLIENT_CLASS": "django_redis.client.DefaultClient",
            "CONNECTION_POOL_KWARGS": {
                "max_connections": 100,
                "retry_on_timeout": True,
            },
            "PASSWORD": "redishshy795416",
            "SOCKET_CONNECT_TIMEOUT": 5,
            "SOCKET_TIMEOUT": 5,
        },
        "KEY_PREFIX": "myedu",
        "TIMEOUT": 300,  # 默认超时5分钟
    }
}

# 使用Redis存储Session
SESSION_ENGINE = "django.contrib.sessions.backends.cache"
SESSION_CACHE_ALIAS = "default"

# ==================== 邮件配置 ====================

EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
EMAIL_HOST = os.environ.get('EMAIL_HOST', 'smtp.qq.com')
EMAIL_PORT = int(os.environ.get('EMAIL_PORT', 465))
EMAIL_USE_SSL = os.environ.get('EMAIL_USE_SSL', 'True').lower() == 'true'
EMAIL_USE_TLS = os.environ.get('EMAIL_USE_TLS', 'False').lower() == 'true'
EMAIL_HOST_USER = os.environ.get('EMAIL_HOST_USER', '651117676@qq.com')
EMAIL_HOST_PASSWORD = os.environ.get('EMAIL_HOST_PASSWORD', 'rphcxwtfwljtbehb')
DEFAULT_FROM_EMAIL = EMAIL_HOST_USER
EMAIL_TIMEOUT = 30

# 开发环境使用控制台后端
# if DEBUG:
#     EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend'

# ==================== 国际化 ====================

LANGUAGE_CODE = 'zh-hans'
TIME_ZONE = 'Asia/Shanghai'  # 改为中国时区
USE_I18N = True
USE_L10N = True
USE_TZ = True

# ==================== 静态文件 ====================

STATIC_URL = '/static/'
STATIC_ROOT = BASE_DIR / 'static_collect'
STATICFILES_DIRS = [
    BASE_DIR / 'static',
]

# 媒体文件配置
MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'
SECURE_CROSS_ORIGIN_OPENER_POLICY = None

# 静态文件缓存
STATICFILES_STORAGE = 'django.contrib.staticfiles.storage.ManifestStaticFilesStorage' if not DEBUG else 'django.contrib.staticfiles.storage.StaticFilesStorage'

# ==================== SimpleUI配置 ====================
SIMPLEUI_HOME_INFO = False
SIMPLEUI_ANALYSIS = False
SIMPLEUI_STATIC_OFFLINE = True
SIMPLEUI_LOADING = False
SIMPLEUI_CONFIG = {
    'system_keep': False,
    'dynamic': True,
}
# SimpleUI图标配置
SIMPLEUI_ICON = {
    '人口查询': 'fas fa-search',
    '人口管理': 'fas fa-users',
    '数据变更': 'fas fa-edit',
}

# ==================== 日志配置 ====================

LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {
            'format': '[{levelname}] {asctime} {module} {process:d} {thread:d} {message}',
            'style': '{',
        },
        'simple': {
            'format': '[{levelname}] {asctime} {message}',
            'style': '{',
        },
    },
    'filters': {
        'require_debug_false': {
            '()': 'django.utils.log.RequireDebugFalse',
        },
        'require_debug_true': {
            '()': 'django.utils.log.RequireDebugTrue',
        },
    },
    'handlers': {
        'console': {
            'level': 'DEBUG',
            'class': 'logging.StreamHandler',
            'formatter': 'simple',
            'filters': ['require_debug_true'],
        },
        'file_info': {
            'level': 'INFO',
            'class': 'logging.handlers.RotatingFileHandler',
            'filename': BASE_DIR / 'logs/info.log',
            'maxBytes': 1024 * 1024 * 10,  # 10MB
            'backupCount': 10,
            'formatter': 'verbose',
        },
        'file_error': {
            'level': 'ERROR',
            'class': 'logging.handlers.RotatingFileHandler',
            'filename': BASE_DIR / 'logs/error.log',
            'maxBytes': 1024 * 1024 * 10,
            'backupCount': 10,
            'formatter': 'verbose',
        },
        'mail_admins': {
            'level': 'ERROR',
            'class': 'django.utils.log.AdminEmailHandler',
            'filters': ['require_debug_false'],
        },
    },
    'loggers': {
        'django': {
            'handlers': ['console', 'file_info'],
            'level': 'INFO',
            'propagate': True,
        },
        'django.request': {
            'handlers': ['file_error', 'mail_admins'],
            'level': 'ERROR',
            'propagate': False,
        },
        'django.security': {
            'handlers': ['file_error', 'mail_admins'],
            'level': 'ERROR',
            'propagate': False,
        },
        'django.db.backends': {
            'handlers': ['console'],
            'level': 'WARNING',  # 生产环境设为WARNING，开发可设DEBUG
            'propagate': False,
        },
        'main': {  # 自定义应用日志
            'handlers': ['console', 'file_info', 'file_error'],
            'level': 'INFO',
            'propagate': False,
        },
    },
}

# 确保日志目录存在
LOGS_DIR = BASE_DIR / 'logs'
if not LOGS_DIR.exists():
    LOGS_DIR.mkdir(parents=True, exist_ok=True)

# ==================== 默认主键 ====================

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# ==================== 自定义设置 ====================

# 分页配置
PAGINATION = {
    'default_page_size': 30,
    'max_page_size': 100,
}

# 验证码配置
CAPTCHA = {
    'length': 4,
    'expire_time': 300,  # 5分钟
}

# 登录限制
LOGIN_LIMIT = {
    'max_attempts': 5,
    'lockout_time': 600,  # 10分钟
}

# 邮件发送限制
EMAIL_LIMIT = {
    'send_interval': 60,  # 60秒
    'max_per_hour': 10,
    'code_expire': 300,  # 5分钟
}

# ==================== 生产环境检查 ====================

if not DEBUG:
    # 确保生产环境的关键设置正确
    assert SECRET_KEY != 'django-insecure-7+3ayv)j!@*6u*l)ri+3ji#cg)d0-z80bn3(2#(ha6xjod53f(', \
        "Production must have a secure SECRET_KEY"
    
    # 生产环境强制HTTPS
    SECURE_SSL_REDIRECT = True
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    
    # HSTS设置
    SECURE_HSTS_SECONDS = 31536000
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD = True
    
    # 其他安全头部
    SECURE_CONTENT_TYPE_NOSNIFF = True
    SECURE_BROWSER_XSS_FILTER = True
