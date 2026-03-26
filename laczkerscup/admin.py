from django.contrib import admin
from django.utils.html import format_html
from .models import (
    Player, EloMatch, EloHistory,
    LosowanieELO, UczestnikLosowania, MeczLosowania,
    Turniej, Etap, UczestnikTurnieju, Mecz, WystepGracza,
    WynikTurnieju, TypTurnieju,
)


# ─────────────────────────────────────────────────────────────────────
#  GRACZE
# ─────────────────────────────────────────────────────────────────────

@admin.register(Player)
class PlayerAdmin(admin.ModelAdmin):
    list_display  = ['display_name', 'first_name', 'last_name', 'is_active', 'joined_date']
    list_filter   = ['is_active']
    search_fields = ['first_name', 'last_name', 'nickname']


# ─────────────────────────────────────────────────────────────────────
#  ELO
# ─────────────────────────────────────────────────────────────────────

@admin.register(EloMatch)
class EloMatchAdmin(admin.ModelAdmin):
    list_display  = ['player_a', 'player_b', 'result', 'date']
    list_filter   = ['result', 'date']
    date_hierarchy = 'date'


@admin.register(EloHistory)
class EloHistoryAdmin(admin.ModelAdmin):
    list_display = ['player', 'match', 'rating_before', 'delta', 'rating_after']
    list_filter  = ['player']


# ─────────────────────────────────────────────────────────────────────
#  TURNIEJE
# ─────────────────────────────────────────────────────────────────────

class EtapInline(admin.TabularInline):
    """Etapy edytowalne bezpośrednio na stronie turnieju."""
    model  = Etap
    extra  = 1
    fields = ['nazwa', 'typ', 'poziom', 'sumuj_punkty_z_poprzednich']


class UczestnikTurniejuInline(admin.TabularInline):
    """Gracze edytowalni bezpośrednio na stronie turnieju."""
    model  = UczestnikTurnieju
    extra  = 1
    fields = ['gracz', 'zespol', 'ulubiony_klub']
    autocomplete_fields = ['gracz']


# ── Typer ─────────────────────────────────────────────────────────────

class WynikTurniejuInline(admin.StackedInline):
    model   = WynikTurnieju
    extra   = 1
    max_num = 1

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        """Ogranicz wybór graczy do uczestników danego turnieju."""
        if db_field.name in ['miejsce_1', 'miejsce_2', 'miejsce_3', 'miejsce_ostatnie',
                              'krol_strzelcow', 'murarz', 'kosiarz']:
            turniej_id = request.resolver_match.kwargs.get('object_id')
            if turniej_id:
                kwargs['queryset'] = Player.objects.filter(
                    id__in=UczestnikTurnieju.objects.filter(
                        turniej_id=turniej_id
                    ).values('gracz_id')
                ).order_by('last_name')
        return super().formfield_for_foreignkey(db_field, request, **kwargs)


@admin.register(Turniej)
class TurniejAdmin(admin.ModelAdmin):
    list_display = ['nazwa', 'data_start', 'data_koniec', 'liczba_graczy']
    fields       = ['nazwa', 'data_start', 'data_koniec', 'opis', 'notka', 'zdjecie']
    inlines      = [EtapInline, UczestnikTurniejuInline, WynikTurniejuInline]

    def liczba_graczy(self, obj):
        return obj.uczestnicy.count()
    liczba_graczy.short_description = 'Graczy'


@admin.register(Etap)
class EtapAdmin(admin.ModelAdmin):
    list_display = ['nazwa', 'turniej', 'typ', 'poziom']
    list_filter  = ['turniej', 'typ']


# ─────────────────────────────────────────────────────────────────────
#  MECZE
# ─────────────────────────────────────────────────────────────────────

class WystepGraczaInline(admin.TabularInline):
    """Statystyki widoczne bezpośrednio przy meczu (tylko do podglądu)."""
    model   = WystepGracza
    extra   = 0
    fields  = ['gracz', 'gole_strzelone', 'gole_stracone',
                'zolte_kartki', 'czerwone_kartki', 'punkty']
    readonly_fields = ['gracz', 'gole_strzelone', 'gole_stracone',
                       'zolte_kartki', 'czerwone_kartki', 'punkty']
    can_delete = False

    def has_add_permission(self, request, obj=None):
        return False


@admin.register(Mecz)
class MeczAdmin(admin.ModelAdmin):
    list_display  = ['__str__', 'turniej', 'etap', 'status',
                     'wynik', 'zwyciezca', 'data']
    list_filter   = ['turniej', 'etap', 'status']
    date_hierarchy = 'data'
    autocomplete_fields = ['gracz_a', 'gracz_b']
    inlines       = [WystepGraczaInline]

    fieldsets = [
        ('Turniej', {
            'fields': ['turniej', 'etap', 'data', 'status', 'opis']
        }),
        ('Gracze', {
            'fields': ['gracz_a', 'gracz_b']
        }),
        ('Wynik', {
            'fields': [
                ('gole_a', 'gole_b'),
                ('zolte_a', 'zolte_b'),
                ('czerwone_a', 'czerwone_b'),
                'zwyciezca',
            ]
        }),
    ]

    actions = ['przelicz_wystepy']

    def wynik(self, obj):
        if obj.status == 'wolny_los':
            return format_html('<span style="color:#888">BYE</span>')
        if obj.gole_a is not None and obj.gole_b is not None:
            return f'{obj.gole_a} : {obj.gole_b}'
        return '—'
    wynik.short_description = 'Wynik'

    @admin.action(description='Przelicz statystyki zaznaczonych meczów')
    def przelicz_wystepy(self, request, queryset):
        count = 0
        for mecz in queryset:
            mecz.przelicz_wystepy()
            count += 1
        self.message_user(request, f'Przeliczono statystyki dla {count} meczów.')


# ─────────────────────────────────────────────────────────────────────
#  STATYSTYKI
# ─────────────────────────────────────────────────────────────────────

@admin.register(WystepGracza)
class WystepGraczaAdmin(admin.ModelAdmin):
    list_display = ['gracz', 'przeciwnik', 'turniej', 'etap',
                    'gole_strzelone', 'gole_stracone',
                    'zolte_kartki', 'czerwone_kartki', 'punkty']
    list_filter  = ['turniej', 'etap', 'gracz']
    readonly_fields = ['mecz', 'turniej', 'etap', 'gracz', 'przeciwnik',
                       'gole_strzelone', 'gole_stracone',
                       'zolte_kartki', 'czerwone_kartki', 'punkty']

    def has_add_permission(self, request):
        return False  # Zawsze generowane przez Mecz.przelicz_wystepy()



@admin.register(TypTurnieju)
class TypTurniejuAdmin(admin.ModelAdmin):
    list_display  = ['gracz', 'turniej', 'punkty_display']
    list_filter   = ['turniej']
    ordering      = ['turniej', 'gracz__last_name']
    autocomplete_fields = ['gracz']

    def punkty_display(self, obj):
        try:
            wynik = obj.turniej.wynik
        except WynikTurnieju.DoesNotExist:
            return '—'
        return obj.oblicz_punkty(wynik)
    punkty_display.short_description = 'Punkty'

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        gracze_fk = ['miejsce_1', 'miejsce_2', 'miejsce_3', 'miejsce_ostatnie',
                     'krol_strzelcow', 'murarz', 'kosiarz']
        if db_field.name in gracze_fk:
            # Przy edycji istniejącego rekordu — filtruj po turnieju
            object_id = request.resolver_match.kwargs.get('object_id')
            if object_id:
                try:
                    typ = TypTurnieju.objects.get(pk=object_id)
                    kwargs['queryset'] = Player.objects.filter(
                        id__in=UczestnikTurnieju.objects.filter(
                            turniej=typ.turniej
                        ).values('gracz_id')
                    ).order_by('last_name')
                except TypTurnieju.DoesNotExist:
                    pass
        return super().formfield_for_foreignkey(db_field, request, **kwargs)
