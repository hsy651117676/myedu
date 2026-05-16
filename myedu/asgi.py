"""
ASGI config for myedu project.
支持异步应用的部署配置
"""

import os
from django.core.asgi import get_asgi_application

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'myedu.settings')

application = get_asgi_application()
