from django.contrib.auth.decorators import login_required
"""
views_losowanie.py
------------------
Widoki Django dla modułu Losowanie ELO.
Logika losowania jest w losowanie_logika.py.
"""

from collections import defaultdict

from django.shortcuts import render, redirect, get_object_or_404

from .models import Player, LosowanieELO, UczestnikLosowania, MeczLosowania
from .losowanie_logika import losuj


@login_required
def losowanie_formularz(request):
    """
    GET  → formularz wyboru graczy i liczby kolejek
    POST → generuje losowanie, zapisuje do bazy, przekierowuje do wyników
    """
    if request.method == 'POST':
        nazwa          = request.POST.get('nazwa', '').strip()
        liczba_kolejek = int(request.POST.get('liczba_kolejek', 2))
        ids_R          = [int(x) for x in request.POST.getlist('gracze_R')]
        ids_N          = [int(x) for x in request.POST.getlist('gracze_N')]

        # Walidacja
        blad = None
        if not ids_R or not ids_N:
            blad = 'Musisz wybrać co najmniej jednego gracza do każdego koszyka.'
        elif set(ids_R) & set(ids_N):
            blad = 'Ten sam gracz nie może być jednocześnie w koszyku R i N.'

        if not blad:
            rundy, blad = losuj(ids_R, ids_N, liczba_kolejek)

        if not blad:
            # Zapisz do bazy
            los = LosowanieELO.objects.create(
                nazwa=nazwa or f'Losowanie {len(ids_R) + len(ids_N)} graczy',
                liczba_kolejek=liczba_kolejek,
            )
            for pid in ids_R:
                UczestnikLosowania.objects.create(losowanie=los, gracz_id=pid, koszyk='R')
            for pid in ids_N:
                UczestnikLosowania.objects.create(losowanie=los, gracz_id=pid, koszyk='N')
            for nr, pary, bye_gracze in rundy:
                for pid_bye in bye_gracze:
                    MeczLosowania.objects.create(
                        losowanie=los, kolejka=nr, gracz_a_id=pid_bye, czy_bye=True)
                for a, b in pary:
                    MeczLosowania.objects.create(
                        losowanie=los, kolejka=nr, gracz_a_id=a, gracz_b_id=b)

            return redirect('laczkerscup:losowanie_wyniki', pk=los.pk)

        # Błąd — wróć do formularza z komunikatem
        return render(request, 'laczkerscup/losowanie_formularz.html', {
            'gracze': Player.objects.filter(is_active=True),
            'blad':   blad,
        })

    return render(request, 'laczkerscup/losowanie_formularz.html', {
        'gracze': Player.objects.filter(is_active=True),
    })


@login_required
def losowanie_wyniki(request, pk):
    """Wyniki losowania — tabela zbiorcza + odsłanianie gracz po graczu."""
    los        = get_object_or_404(LosowanieELO, pk=pk)
    uczestnicy = list(los.uczestnicy.select_related('gracz'))
    mecze      = list(los.mecze.select_related('gracz_a', 'gracz_b'))

    # Słownik: id_gracza → koszyk ('R' lub 'N')
    koszyk_gracza = {u.gracz_id: u.koszyk for u in uczestnicy}

    # Dodaj koszyki i kolory bezpośrednio do obiektów meczu
    for m in mecze:
        m.koszyk_a = koszyk_gracza.get(m.gracz_a_id, 'N')
        m.kolor_a  = '#1565C0' if m.koszyk_a == 'R' else '#2E7D32'
        if m.gracz_b_id:
            m.koszyk_b = koszyk_gracza.get(m.gracz_b_id, 'N')
            m.kolor_b  = '#1565C0' if m.koszyk_b == 'R' else '#2E7D32'

    # Grupuj mecze per kolejka (do tabeli zbiorczej)
    kolejki = defaultdict(list)
    for m in mecze:
        kolejki[m.kolejka].append(m)

    # Grupuj mecze per gracz (do panelu odsłaniania)
    mecze_gracza = defaultdict(list)
    for m in mecze:
        mecze_gracza[m.gracz_a_id].append(m)
        if m.gracz_b_id:
            mecze_gracza[m.gracz_b_id].append(m)

    return render(request, 'laczkerscup/losowanie_wyniki.html', {
        'los':          los,
        'uczestnicy':   uczestnicy,
        'kolejki':      dict(sorted(kolejki.items())),
        'mecze_gracza': dict(mecze_gracza),
    })


@login_required
def losowanie_lista(request):
    """Lista wszystkich zapisanych losowań."""
    losowania = LosowanieELO.objects.prefetch_related('uczestnicy').all()
    return render(request, 'laczkerscup/losowanie_lista.html', {
        'losowania': losowania,
    })
