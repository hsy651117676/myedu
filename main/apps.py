from django.apps import AppConfig


class MainConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'main'
    verbose_name = '主应用'
    
    def ready(self):
        """应用启动时的初始化操作"""
        import main.signals  # 如果后续添加信号处理
