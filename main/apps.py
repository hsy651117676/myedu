from django.apps import AppConfig


class MainConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'main'
    verbose_name = '主应用'

    def ready(self):
        try:
            import main.signals
        except ImportError:
            pass
