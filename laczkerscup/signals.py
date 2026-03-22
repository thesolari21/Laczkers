"""
Sygnały Django dla modelu EloMatch.

Po każdym zapisaniu lub usunięciu meczu ELO, automatycznie
przeliczany jest cały ranking od zera.

Dzięki temu:
- Dodanie meczu → ranking zaktualizowany natychmiast.
- Edycja meczu (zmiana wyniku, daty) → ranking przeliczony od nowa, spójny.
- Usunięcie meczu → ranking przeliczony bez tego meczu.
"""

from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from .models import EloMatch


@receiver(post_save, sender=EloMatch)
def elo_match_saved(sender, instance, **kwargs):
    """Przelicz ELO po zapisaniu meczu (nowy lub edytowany)."""
    from .elo import recalculate_elo
    recalculate_elo()


@receiver(post_delete, sender=EloMatch)
def elo_match_deleted(sender, instance, **kwargs):
    """Przelicz ELO po usunięciu meczu."""
    from .elo import recalculate_elo
    recalculate_elo()
