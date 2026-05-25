from django.urls import path, re_path, include
from django.conf.urls.static import static
from django.conf import settings
from main.system_admin.views import placeholder
from .views.home import home_view

urlpatterns = [
    # ==================== 主页 ====================
    path("", home_view, name="home"),

    # ==================== 人口管理 ====================
    path("population/", include("main.views.population.urls")),

    # ==================== 常用工具 ====================
    path("tools/", include("main.views.tools.urls")),

    # ==================== 档案系统管理 ====================
    path("archivesSystem/", include("main.views.archivesSystem.urls")),

    # ==================== 系统管理 ====================
    path("", include("main.system_admin.urls")),

    # ==================== 档案模块 ====================
    path("archives/", include("main.views.archives.urls")),

    # ==================== 业务模块 ====================
    path("business/", include("main.views.business.urls")),

    # ==================== 组件 ====================
    path("components/", include("main.views.components.urls")),

]

if settings.DEBUG:
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATICFILES_DIRS[0])
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
