from django.contrib.auth.decorators import login_required
"""
views_szwajcar.py
-----------------
Widoki dla generatora systemu szwajcarskiego.
"""

from django.shortcuts import render, redirect, get_object_or_404
from django.db.models import Sum, Max, Count
from django.contrib import messages

from .models import Turniej, Player, WystepGracza, Mecz, SzwajcarKolejka, SzwajcarPara
from .szwajcar_logika import generuj_pary, maks_kolejek


def _tabela_punktowa(turniej):
    """
    Zwraca listę [(gracz, punkty), ...] posortowaną malejąco po punktach.
    Gracze bez meczów mają 0 punktów.
    """
    # Pobierz punkty z WystepGracza
    punkty_map = {
        row['gracz']: row['suma']
        for row in WystepGracza.objects
        .filter(turniej=turniej)
        .values('gracz')
        .annotate(suma=Sum('punkty'))
    }

    # Wszyscy uczestnicy turnieju
    uczestnicy = list(
        turniej.uczestnicy.select_related('gracz').order_by('gracz__last_name')
    )

    tabela = [
        (u.gracz, punkty_map.get(u.gracz_id, 0))
        for u in uczestnicy
    ]

    # Sortuj malejąco po punktach, przy remisie alfabetycznie
    tabela.sort(key=lambda x: (-x[1], x[0].display_name().lower()))
    return tabela


def _rozegrane_pary(turniej):
    """
    Zwraca set frozenset({id_a, id_b}) — wszystkie pary które już grały w turnieju.
    Bierzemy ze wszystkich meczów w turnieju (niezależnie czy wpisane ręcznie czy przez szwajcara).
    Dzięki temu szwajcar nie powtórzy pary która już grała poza generatorem.
    """
    pary = set()
    for mecz in Mecz.objects.filter(turniej=turniej, gracz_b__isnull=False):
        pary.add(frozenset({mecz.gracz_a_id, mecz.gracz_b_id}))
    return pary


def _bye_historia(turniej):
    """Lista gracz_id którzy dostali BYE, chronologicznie (najstarszy pierwszy)."""
    return list(
        SzwajcarPara.objects
        .filter(kolejka__turniej=turniej, gracz_b__isnull=True)
        .order_by('kolejka__numer')
        .values_list('gracz_a_id', flat=True)
    )


@login_required
def szwajcar_formularz(request):
    """Wybór turnieju i podgląd aktualnej tabeli przed generowaniem."""
    turnieje = Turniej.objects.order_by('-data_start')

    turniej_pk = request.GET.get('turniej') or request.POST.get('turniej')
    turniej = None
    tabela = []
    kolejki = []
    maks = 0
    nastepna = 1
    blad = None

    if turniej_pk:
        turniej = get_object_or_404(Turniej, pk=turniej_pk)
        tabela  = _tabela_punktowa(turniej)
        kolejki = list(
            SzwajcarKolejka.objects
            .filter(turniej=turniej)
            .prefetch_related('pary__gracz_a', 'pary__gracz_b')
            .order_by('numer')
        )
        maks          = maks_kolejek(len(tabela))
        nastepna      = len(kolejki) + 1
        # Liczba rozegranych kolejek = max liczba meczów jednego gracza w turnieju
        kolejki_w_turnieju = (
            WystepGracza.objects
            .filter(turniej=turniej)
            .values('gracz')
            .annotate(ile=Count('id'))
            .aggregate(maks=Max('ile'))
        )['maks'] or 0

    if request.method == 'POST' and turniej:
        if nastepna > maks:
            blad = (
                f'Osiągnięto maksymalną liczbę kolejek ({maks}) '
                f'dla {len(tabela)} graczy. Wszyscy zagrali ze wszystkimi.'
            )
        else:
            gracze_z_punktami = [(g.pk, pkt) for g, pkt in tabela]
            rozegrane          = _rozegrane_pary(turniej)
            bye_hist           = _bye_historia(turniej)

            pary, bye_gracz, err = generuj_pary(gracze_z_punktami, rozegrane, bye_hist)

            if err:
                blad = err
            else:
                # Zapisz kolejkę
                kolejka = SzwajcarKolejka.objects.create(
                    turniej=turniej,
                    numer=nastepna,
                )
                for a, b in pary:
                    SzwajcarPara.objects.create(kolejka=kolejka, gracz_a_id=a, gracz_b_id=b)
                if bye_gracz:
                    SzwajcarPara.objects.create(kolejka=kolejka, gracz_a_id=bye_gracz, gracz_b=None)

                return redirect(
                    f"{request.path}?turniej={turniej.pk}"
                )

    return render(request, 'laczkerscup/szwajcar.html', {
        'turnieje':  turnieje,
        'turniej':   turniej,
        'tabela':    tabela,
        'kolejki':          kolejki,
        'maks':             maks,
        'nastepna':         nastepna,
        'kolejki_w_turnieju': kolejki_w_turnieju if turniej else 0,
        'blad':      blad,
    })


@login_required
def szwajcar_usun_kolejke(request, pk):
    """Usuwa ostatnią kolejkę (tylko jeśli jest ostatnią)."""
    kolejka = get_object_or_404(SzwajcarKolejka, pk=pk)
    turniej_pk = kolejka.turniej_id

    # Pozwól usunąć tylko ostatnią kolejkę danego turnieju
    ostatnia = SzwajcarKolejka.objects.filter(turniej=kolejka.turniej).order_by('-numer').first()
    if kolejka.pk == ostatnia.pk:
        kolejka.delete()
    else:
        messages.error(request, 'Można usunąć tylko ostatnią kolejkę.')

    return redirect(f"/szwajcar/?turniej={turniej_pk}")
