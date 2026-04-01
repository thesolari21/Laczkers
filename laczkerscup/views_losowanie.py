from django.contrib.auth.decorators import login_required
"""
views_losowanie.py
------------------
Widoki Django dla modułu Losowanie ELO.
Logika losowania jest w losowanie_logika.py.
"""

import json
from collections import defaultdict

from django.shortcuts import render, redirect, get_object_or_404

from .models import Player, LosowanieELO, UczestnikLosowania, MeczLosowania, Turniej, Etap, UczestnikTurnieju, Mecz
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
            turniej_pk_val = request.POST.get('turniej') or None
            los = LosowanieELO.objects.create(
                nazwa=nazwa or f'Losowanie {len(ids_R) + len(ids_N)} graczy',
                liczba_kolejek=liczba_kolejek,
            )
            # Zapisz turniej do losowania jeśli model go obsługuje
            if turniej_pk_val and hasattr(los, 'turniej'):
                try:
                    los.turniej = Turniej.objects.get(pk=turniej_pk_val)
                    los.save()
                except Turniej.DoesNotExist:
                    pass
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
        turnieje = Turniej.objects.prefetch_related('uczestnicy__gracz').order_by('-data_start')
        for t in turnieje:
            t.gracze_json = json.dumps([
                {'pk': u.gracz.pk, 'nazwa': u.gracz.display_name()}
                for u in t.uczestnicy.select_related('gracz').order_by('gracz__last_name')
            ], ensure_ascii=False)
        return render(request, 'laczkerscup/losowanie_formularz.html', {
            'turnieje':   turnieje,
            'turniej_pk': request.POST.get('turniej', ''),
            'blad':       blad,
        })

    turnieje = Turniej.objects.prefetch_related(
        'uczestnicy__gracz'
    ).order_by('-data_start')

    # Dla każdego turnieju przygotuj listę graczy jako JSON (do filtrowania w JS)
    for t in turnieje:
        t.gracze_json = json.dumps([
            {'pk': u.gracz.pk, 'nazwa': u.gracz.display_name()}
            for u in t.uczestnicy.select_related('gracz').order_by('gracz__last_name')
        ], ensure_ascii=False)

    return render(request, 'laczkerscup/losowanie_formularz.html', {
        'turnieje':  turnieje,
        'turniej_pk': request.GET.get('turniej', ''),
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

    # Etapy grupowe powiązanego turnieju — do importu
    turniej_los = getattr(los, 'turniej', None)
    etapy_import = []
    if turniej_los:
        etapy_import = list(Etap.objects.filter(
            turniej=turniej_los, typ='grupowy'
        ).order_by('poziom', 'data_utworzenia'))

    return render(request, 'laczkerscup/losowanie_wyniki.html', {
        'los':          los,
        'uczestnicy':   uczestnicy,
        'kolejki':      dict(sorted(kolejki.items())),
        'mecze_gracza': dict(mecze_gracza),
        'turniej':      turniej_los,
        'etapy_import': etapy_import,
    })


@login_required
def losowanie_lista(request):
    """Lista wszystkich zapisanych losowań."""
    losowania = LosowanieELO.objects.prefetch_related('uczestnicy').all()
    return render(request, 'laczkerscup/losowanie_lista.html', {
        'losowania': losowania,
    })


@login_required
def losowanie_importuj(request, pk):
    """
    Importuje wygenerowane pary jako mecze zaplanowane w wybranym etapie.
    Turniej pochodzi z losowania — nie trzeba go wybierać ponownie.
    Sprawdza czy etap nie ma już zaplanowanych meczów.
    """
    los     = get_object_or_404(LosowanieELO, pk=pk)
    turniej = los.turniej if hasattr(los, 'turniej') and los.turniej else get_object_or_404(Turniej, pk=request.POST.get('turniej'))
    etap    = get_object_or_404(Etap, pk=request.POST.get('etap'), turniej=turniej, typ='grupowy')

    # Sprawdź czy etap ma już zaplanowane mecze
    if Mecz.objects.filter(turniej=turniej, etap=etap, status='zaplanowany').exists():
        mecze     = list(los.mecze.select_related('gracz_a', 'gracz_b'))
        uczestnicy = list(los.uczestnicy.select_related('gracz'))
        koszyk_gracza = {u.gracz_id: u.koszyk for u in uczestnicy}
        for m in mecze:
            m.koszyk_a = koszyk_gracza.get(m.gracz_a_id, 'N')
            m.kolor_a  = '#1565C0' if m.koszyk_a == 'R' else '#2E7D32'
            if m.gracz_b_id:
                m.koszyk_b = koszyk_gracza.get(m.gracz_b_id, 'N')
                m.kolor_b  = '#1565C0' if m.koszyk_b == 'R' else '#2E7D32'
        from collections import defaultdict
        kolejki = defaultdict(list)
        for m in mecze:
            kolejki[m.kolejka].append(m)
        etapy_imp = list(Etap.objects.filter(turniej=turniej, typ='grupowy').order_by('poziom', 'data_utworzenia'))
        return render(request, 'laczkerscup/losowanie_wyniki.html', {
            'los':          los,
            'uczestnicy':   uczestnicy,
            'kolejki':      dict(sorted(kolejki.items())),
            'mecze_gracza': {},
            'blad_import':  f'Etap "{etap.nazwa}" ma już zaplanowane mecze. Usuń je ręcznie w adminie przed importem.',
            'turniej':      turniej,
            'etapy_import': etapy_imp,
        })

    # Importuj — utwórz mecze
    data = turniej.data_start  # może być None — Django przyjmie null
    for m in los.mecze.select_related('gracz_a', 'gracz_b').order_by('kolejka', 'id'):
        if m.czy_bye:
            Mecz.objects.create(
                turniej=turniej,
                etap=etap,
                gracz_a=m.gracz_a,
                gracz_b=None,
                status='wolny_los',
                data=data,
            )
        else:
            Mecz.objects.create(
                turniej=turniej,
                etap=etap,
                gracz_a=m.gracz_a,
                gracz_b=m.gracz_b,
                status='zaplanowany',
                data=data,
            )

    return redirect('laczkerscup:turniej_detail', pk=turniej.pk)



@login_required
def losowanie_etapy_json(request):
    """Zwraca etapy grupowe turnieju jako JSON — dla dynamicznego dropdownu."""
    from django.http import JsonResponse
    turniej_id = request.GET.get('turniej')
    if not turniej_id:
        return JsonResponse([], safe=False)
    etapy = Etap.objects.filter(
        turniej_id=turniej_id,
        typ='grupowy'
    ).order_by('poziom', 'data_utworzenia').values('id', 'nazwa')
    return JsonResponse(list(etapy), safe=False)
