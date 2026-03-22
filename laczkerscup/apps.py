from django.apps import AppConfig


class LaczkerscupConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name               = 'laczkerscup'
    verbose_name       = 'Łączkerskup'

    def ready(self):
        """Rejestracja sygnałów — wywoływane raz przy starcie serwera."""
        import laczkerscup.signals  # noqa: F401
