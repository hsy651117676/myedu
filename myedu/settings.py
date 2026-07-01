# myedu/settings.py
import os
from pathlib import Path

# ==================== 基础配置 ====================
BASE_DIR = Path(__file__).resolve().parent.parent


# ========== 读取配置文件 ==========
def load_credentials(config_path="/etc/myedu/credentials.conf"):
    """从配置文件加载凭据到环境变量"""
    config_file = Path(config_path)

    if config_file.exists():
        with open(config_file, "r") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    key, value = line.split("=", 1)
                    os.environ.setdefault(key.strip(), value.strip())


# 加载凭据
load_credentials()

# ==================== 基础配置 ====================
SECRET_KEY = os.environ.get("DJANGO_SECRET_KEY")
if not SECRET_KEY:
    import secrets

    SECRET_KEY = secrets.token_urlsafe(50)

DEBUG = os.environ.get("DJANGO_DEBUG", "True").lower() == "true"

ALLOWED_HOSTS = [
    "localhost",
    "127.0.0.1",
    "218.201.223.229",
    "192.168.16.100",
    "192.168.17.100",
    "192.168.18.100",
    "pzs.das.cn",
    "pzsdas.com",
    "das.edu",
]
LOGIN_URL = "login"
LOGIN_REDIRECT_URL = "home"
LOGOUT_REDIRECT_URL = "login"

# ==================== 档案扫描图像配置 ====================

SCAN_IMAGE_BASE_DIR = "/mnt/raid10/das_images"
SCAN_PDF_OUTPUT_DIR = "/mnt/raid10/das_pdf"
MEDIA_BASE_DIR = "/mnt/media"

SCAN_IMAGE_TYPES = {
    "YS": "原始图像",
    "GQ": "高清图像",
}
SCAN_AES_KEY = os.environ.get("SCAN_AES_KEY")
if SCAN_AES_KEY:
    SCAN_AES_KEY = SCAN_AES_KEY.encode().ljust(16, b"\x00")[:16]
else:
    raise RuntimeError("SCAN_AES_KEY 未配置，请检查 /etc/myedu/credentials.conf")

SCAN_PDF_PAGE_SIZE = "A4"
SCAN_PDF_VERTICAL = True
SCAN_PDF_MARGIN_UP = 1
SCAN_PDF_MARGIN_DOWN = 1
SCAN_PDF_MARGIN_LEFT = 1
SCAN_PDF_MARGIN_RIGHT = 1
SCAN_PDF_DPI = 150
SCAN_PDF_JPEG_QUALITY = 85

# ==================== 音频视频配置 ====================

# ==================== 安全配置 ====================
if not DEBUG:
    SECURE_SSL_REDIRECT = True
    SECURE_HSTS_SECONDS = 31536000
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD = True
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
    USE_X_FORWARDED_HOST = True

SESSION_EXPIRE_AT_BROWSER_CLOSE = True
SESSION_COOKIE_AGE = 60 * 60 * 8
SESSION_COOKIE_SECURE = not DEBUG
CSRF_COOKIE_SECURE = not DEBUG
SESSION_COOKIE_HTTPONLY = True
CSRF_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = "Lax"
CSRF_COOKIE_SAMESITE = "Lax"

X_FRAME_OPTIONS = "SAMEORIGIN"

CSRF_TRUSTED_ORIGINS = [
    "https://218.201.223.229:8341",
    "http://localhost:8000",
    "http://127.0.0.1:8000",
]
AUTHENTICATION_BACKENDS = [
    "main.backends.ArchiveAuthBackend",
    "django.contrib.auth.backends.ModelBackend",
]

# ==================== 应用配置 ====================

INSTALLED_APPS = [
    "simpleui",
    "sslserver",
    "django_extensions",
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "main",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "main.middleware.LoginJumpMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "myedu.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "myedu.wsgi.application"

# ==================== 数据库配置 ====================

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.mysql",
        "NAME": os.environ.get("DB_NAME", "myedu"),
        "USER": os.environ.get("DB_USER", "root"),
        "PASSWORD": os.environ.get("DB_PASSWORD", ""),
        "HOST": os.environ.get("DB_HOST", "127.0.0.1"),
        "PORT": os.environ.get("DB_PORT", "3306"),
        "OPTIONS": {
            "charset": "utf8mb4",
            "init_command": "SET sql_mode='STRICT_TRANS_TABLES'",
        },
        "CONN_MAX_AGE": 600,
    }
}

POPULATION_DB = {
    "DRIVER": "ODBC Driver 18 for SQL Server",
    "SERVER": "127.0.0.1",
    "PORT": "1433",
    "DATABASE": os.environ.get("POP_DB_NAME", "rs_new"),
    "UID": os.environ.get("POP_DB_USER", "sa"),
    "PWD": os.environ.get("POP_DB_PASSWORD", ""),
    "Encrypt": "Optional",
    "TrustServerCertificate": "Yes",
}

ARCHIVES_DB = {
    "DRIVER": "ODBC Driver 18 for SQL Server",
    "SERVER": "127.0.0.1",
    "PORT": "1433",
    "DATABASE": "rs_new",
    "UID": "sa",
    "PWD": os.environ.get("POP_DB_PASSWORD", ""),
    "Encrypt": "Optional",
    "TrustServerCertificate": "Yes",
}

# ==================== 密码验证 ====================

AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
        "OPTIONS": {
            "min_length": 8,
        },
    },
    {
        "NAME": "django.contrib.auth.password_validation.CommonPasswordValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.NumericPasswordValidator",
    },
]

PASSWORD_HASHERS = [
    "django.contrib.auth.hashers.Argon2PasswordHasher",
    "django.contrib.auth.hashers.PBKDF2PasswordHasher",
    "django.contrib.auth.hashers.PBKDF2SHA1PasswordHasher",
    "django.contrib.auth.hashers.BCryptSHA256PasswordHasher",
]

# ==================== 缓存配置 ====================

CACHES = {
    "default": {
        "BACKEND": "django_redis.cache.RedisCache",
        "LOCATION": os.environ.get("REDIS_URL", "redis://127.0.0.1:6379/0"),
        "OPTIONS": {
            "CLIENT_CLASS": "django_redis.client.DefaultClient",
            "CONNECTION_POOL_KWARGS": {
                "max_connections": 100,
                "retry_on_timeout": True,
            },
            "PASSWORD": os.environ.get("REDIS_PASSWORD", ""),
            "SOCKET_CONNECT_TIMEOUT": 5,
            "SOCKET_TIMEOUT": 5,
        },
        "KEY_PREFIX": "myedu",
        "TIMEOUT": 300,
    }
}

SESSION_ENGINE = "django.contrib.sessions.backends.cache"
SESSION_CACHE_ALIAS = "default"

# ==================== 邮件配置 ====================

EMAIL_BACKEND = "django.core.mail.backends.smtp.EmailBackend"
EMAIL_HOST = os.environ.get("EMAIL_HOST", "smtp.qq.com")
EMAIL_PORT = int(os.environ.get("EMAIL_PORT", 465))
EMAIL_USE_SSL = os.environ.get("EMAIL_USE_SSL", "True").lower() == "true"
EMAIL_USE_TLS = os.environ.get("EMAIL_USE_TLS", "False").lower() == "true"
EMAIL_HOST_USER = os.environ.get("EMAIL_HOST_USER", "")
EMAIL_HOST_PASSWORD = os.environ.get("EMAIL_HOST_PASSWORD", "")
DEFAULT_FROM_EMAIL = EMAIL_HOST_USER
EMAIL_TIMEOUT = 30

# ==================== 国际化 ====================

LANGUAGE_CODE = "zh-hans"
TIME_ZONE = "Asia/Shanghai"
USE_I18N = True
USE_L10N = True
USE_TZ = True

# ==================== 静态文件 ====================

STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "static_collect"
STATICFILES_DIRS = [
    BASE_DIR / "static",
]

MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"
SECURE_CROSS_ORIGIN_OPENER_POLICY = None

STATICFILES_STORAGE = (
    "django.contrib.staticfiles.storage.ManifestStaticFilesStorage"
    if not DEBUG
    else "django.contrib.staticfiles.storage.StaticFilesStorage"
)

# ==================== SimpleUI配置 ====================
SIMPLEUI_HOME_INFO = False
SIMPLEUI_ANALYSIS = False
SIMPLEUI_STATIC_OFFLINE = True
SIMPLEUI_LOADING = False
SIMPLEUI_CONFIG = {
    "system_keep": False,
    "dynamic": True,
}
SIMPLEUI_ICON = {
    "人口查询": "fas fa-search",
    "人口管理": "fas fa-users",
    "数据变更": "fas fa-edit",
}

# ==================== 日志配置 ====================

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "verbose": {
            "format": "[{levelname}] {asctime} {module} {process:d} {thread:d} {message}",
            "style": "{",
        },
        "simple": {
            "format": "[{levelname}] {asctime} {message}",
            "style": "{",
        },
    },
    "filters": {
        "require_debug_false": {
            "()": "django.utils.log.RequireDebugFalse",
        },
        "require_debug_true": {
            "()": "django.utils.log.RequireDebugTrue",
        },
    },
    "handlers": {
        "console": {
            "level": "DEBUG",
            "class": "logging.StreamHandler",
            "formatter": "simple",
            "filters": ["require_debug_true"],
        },
        "file_info": {
            "level": "INFO",
            "class": "logging.handlers.RotatingFileHandler",
            "filename": BASE_DIR / "logs/info.log",
            "maxBytes": 1024 * 1024 * 10,
            "backupCount": 10,
            "formatter": "verbose",
        },
        "file_error": {
            "level": "ERROR",
            "class": "logging.handlers.RotatingFileHandler",
            "filename": BASE_DIR / "logs/error.log",
            "maxBytes": 1024 * 1024 * 10,
            "backupCount": 10,
            "formatter": "verbose",
        },
        "mail_admins": {
            "level": "ERROR",
            "class": "django.utils.log.AdminEmailHandler",
            "filters": ["require_debug_false"],
        },
    },
    "loggers": {
        "django": {
            "handlers": ["console", "file_info"],
            "level": "INFO",
            "propagate": True,
        },
        "django.request": {
            "handlers": ["file_error", "mail_admins"],
            "level": "ERROR",
            "propagate": False,
        },
        "django.security": {
            "handlers": ["file_error", "mail_admins"],
            "level": "ERROR",
            "propagate": False,
        },
        "django.db.backends": {
            "handlers": ["console"],
            "level": "WARNING",
            "propagate": False,
        },
        "main": {
            "handlers": ["console", "file_info", "file_error"],
            "level": "INFO",
            "propagate": False,
        },
    },
}

LOGS_DIR = BASE_DIR / "logs"
if not LOGS_DIR.exists():
    LOGS_DIR.mkdir(parents=True, exist_ok=True)

# ==================== 默认主键 ====================

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# ==================== 自定义设置 ====================

PAGINATION = {
    "default_page_size": 30,
    "max_page_size": 100,
}

CAPTCHA = {
    "length": 4,
    "expire_time": 300,
}

LOGIN_LIMIT = {
    "max_attempts": 5,
    "lockout_time": 600,
}

EMAIL_LIMIT = {
    "send_interval": 60,
    "max_per_hour": 10,
    "code_expire": 300,
}

# ==================== 生产环境检查 ====================

if not DEBUG:
    SECURE_SSL_REDIRECT = True
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_HSTS_SECONDS = 31536000
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD = True
    SECURE_CONTENT_TYPE_NOSNIFF = True
    SECURE_BROWSER_XSS_FILTER = True
