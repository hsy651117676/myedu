"""
myedu URL Configuration
"""
from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', include('main.urls')),
]

# 开发环境下提供静态文件和媒体文件访问
if settings.DEBUG:
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

# 自定义admin站点信息
admin.site.site_header = '系统管理平台'
admin.site.site_title = '管理后台'
admin.site.index_title = '功能导航'
