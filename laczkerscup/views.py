from django.shortcuts import render, get_object_or_404
from django.db.models import Sum, Count, Q, Avg, F
from django.utils import timezone

from .models import Player, EloHistory, Turniej, Etap, WystepGracza, Mecz, SzwajcarKolejka, SzwajcarPara, WynikTurnieju, TypTurnieju
from .elo import get_elo_ranking
from .views_losowanie import losowanie_formularz, losowanie_wyniki, losowanie_lista
from .views_szwajcar import szwajcar_formularz, szwajcar_usun_kolejke


# ─────────────────────────────────────────────────────────────────────
#  HELPERS
# ─────────────────────────────────────────────────────────────────────

def _mecze_rozegrane(turniej):
    """Mecze rozegrane lub wolny los w danym turnieju."""
    return Mecz.objects.filter(
        turniej=turniej,
        status__in=['rozegrany', 'wolny_los']
    ).select_related('gracz_a', 'gracz_b', 'etap')


def _statystyki_turnieju(turniej):
    """Szybkie statystyki do hero i kafelków."""
    mecze = _mecze_rozegrane(turniej)
    mecze_count = mecze.count()

    wystepy = WystepGracza.objects.filter(turniej=turniej)

    gole_lacznie = wystepy.aggregate(s=Sum('gole_strzelone'))['s'] or 0

    avg_goli = round(gole_lacznie / mecze_count, 2) if mecze_count else 0

    # Czyste konto = gracz stracił 0 goli w meczu rozgranym (nie wolny los)
    czyste_konta = wystepy.filter(
        gole_stracone=0,
        mecz__status='rozegrany'
    ).count()

    zolte  = wystepy.aggregate(s=Sum('zolte_kartki'))['s'] or 0
    czerwone = wystepy.aggregate(s=Sum('czerwone_kartki'))['s'] or 0

    gracze_count = turniej.uczestnicy.count()

    return {
        'gracze':        gracze_count,
        'mecze':         mecze_count,
        'gole':          gole_lacznie,
        'avg_goli':      avg_goli,
        'czyste_konta':  czyste_konta,
        'zolte':         zolte,
        'czerwone':      czerwone,
    }


def _tabela_grupowa(etap):
    """
    Buduje tabelę wyników dla jednego etapu grupowego.
    Sortowanie:
      1. Punkty
      2. Różnica bramek ogółem
      3. Bramki zdobyte ogółem
      4. Kolejność alfabetyczna (nick/nazwisko)
    Komentarze opisują kolejne poziomy kryterium — łatwo rozbudować.
    """
    wystepy = (
        WystepGracza.objects
        .filter(etap=etap)
        .values('gracz')
        .annotate(
            mecze       = Count('id'),
            punkty      = Sum('punkty'),
            gole_za     = Sum('gole_strzelone'),
            gole_str    = Sum('gole_stracone'),
            zolte       = Sum('zolte_kartki'),
            czerwone    = Sum('czerwone_kartki'),
        )
    )

    # Zlicz W/R/P osobno
    wygrane    = {
        w['gracz']: w['cnt']
        for w in WystepGracza.objects.filter(etap=etap, punkty=3)
        .values('gracz').annotate(cnt=Count('id'))
    }
    remisy = {
        w['gracz']: w['cnt']
        for w in WystepGracza.objects.filter(etap=etap, punkty=1)
        .values('gracz').annotate(cnt=Count('id'))
    }
    przegrane = {
        w['gracz']: w['cnt']
        for w in WystepGracza.objects.filter(etap=etap, punkty=0)
        .values('gracz').annotate(cnt=Count('id'))
    }

    # Forma — ostatnie 5 wyników (najnowsze mecze wg id)
    forma_raw = {}
    for w in WystepGracza.objects.filter(etap=etap).select_related('gracz').order_by('-mecz__id'):
        pid = w.gracz_id
        if pid not in forma_raw:
            forma_raw[pid] = []
        if len(forma_raw[pid]) < 5:
            if w.punkty == 3:
                forma_raw[pid].append('W')
            elif w.punkty == 1:
                forma_raw[pid].append('R')
            else:
                forma_raw[pid].append('P')

    # Pobierz imiona graczy
    gracze = {p.pk: p for p in Player.objects.all()}

    wiersze = []
    for row in wystepy:
        pid  = row['gracz']
        gracz = gracze.get(pid)
        if not gracz:
            continue
        roznica = (row['gole_za'] or 0) - (row['gole_str'] or 0)
        wiersze.append({
            'gracz':    gracz,
            'mecze':    row['mecze'],
            'wygrane':  wygrane.get(pid, 0),
            'remisy':   remisy.get(pid, 0),
            'przegrane': przegrane.get(pid, 0),
            'gole_za':  row['gole_za'] or 0,
            'gole_str': row['gole_str'] or 0,
            'roznica':  roznica,
            'forma':    forma_raw.get(pid, []),
            'punkty':   row['punkty'] or 0,
        })

    # Sortowanie — kolejne kryteria opisane w komentarzach
    wiersze.sort(key=lambda r: (
        -r['punkty'],          # 1. Punkty (malejąco)
        -r['roznica'],         # 2. Różnica bramek ogółem
        -r['gole_za'],         # 3. Bramki zdobyte ogółem
        # 4. Tu można dodać: punkty w meczach bezpośrednich
        # 5. Tu można dodać: różnica bramek w meczach bezpośrednich
        r['gracz'].display_name().lower(),  # Ostateczny: alfabetycznie
    ))

    return wiersze


def _wszystkie_etapy(turniej):
    """
    Zwraca etapy pogrupowane po poziomie, posortowane od najwyższego poziomu w dół.
    Każdy wpis: {'poziom': int, 'etapy': [{'etap': Etap, 'wiersze': [...] lub None}]}
    Dla grupowych — liczymy tabelę. Dla pucharowych — tylko etap (obrazek).
    """
    etapy = Etap.objects.filter(turniej=turniej).order_by('-poziom', 'nazwa')

    # Grupuj po poziomie (zachowaj kolejność od najwyższego)
    from collections import OrderedDict
    poziomy = OrderedDict()
    for etap in etapy:
        if etap.poziom not in poziomy:
            poziomy[etap.poziom] = []
        entry = {'etap': etap}
        if etap.typ == 'grupowy':
            entry['wiersze'] = _tabela_grupowa(etap)
        else:
            entry['wiersze'] = None
        poziomy[etap.poziom].append(entry)

    return [{'poziom': poziom, 'etapy': lista} for poziom, lista in poziomy.items()]


def _harmonogram(turniej):
    """Zwraca słownik z trzema listami meczów: rozegrane, nadchodzące, wszystkie."""
    base = (
        Mecz.objects
        .filter(turniej=turniej)
        .select_related('gracz_a', 'gracz_b', 'etap')
        .order_by('-id')
    )
    return {
        'rozegrane':    list(base.filter(status__in=['rozegrany', 'wolny_los'])),
        'nadchodzace':  list(base.filter(status='zaplanowany')),
        'wszystkie':    list(base),
    }


def _nagrody(turniej):
    """
    Zwraca top-3 dla każdej nagrody indywidualnej.
    Liczymy tylko mecze rozegrane i wolny los.
    """
    wystepy = WystepGracza.objects.filter(turniej=turniej)

    # Król strzelców — najwięcej goli zdobytych
    krol = list(
        wystepy.values('gracz')
        .annotate(gole=Sum('gole_strzelone'), mecze=Count('id'))
        .filter(gole__gt=0)
        .order_by('-gole', 'gracz__last_name')[:3]
    )

    # Murarz — najmniej goli straconych (min. 1 mecz rozegrany, nie wolny los)
    murarz = list(
        wystepy.filter(mecz__status='rozegrany')
        .values('gracz')
        .annotate(stracone=Sum('gole_stracone'), mecze=Count('id'))
        .order_by('stracone', 'gracz__last_name')[:3]
    )

    # Kosiarz — suma kartek (żółta=1, czerwona=2)
    kosiarz = list(
        wystepy.values('gracz')
        .annotate(
            punkty_kartek=Sum(
                F('zolte_kartki') + F('czerwone_kartki') * 2
            ),
            zolte=Sum('zolte_kartki'),
            czerwone=Sum('czerwone_kartki'),
        )
        .filter(punkty_kartek__gt=0)
        .order_by('-punkty_kartek', 'gracz__last_name')[:3]
    )

    # Uzupełnij imiona graczy
    gracze = {p.pk: p for p in Player.objects.all()}

    def wzbogac(lista, pola):
        wynik = []
        for row in lista:
            gracz = gracze.get(row['gracz'])
            if gracz:
                entry = {'gracz': gracz}
                entry.update({k: row[k] for k in pola})
                wynik.append(entry)
        return wynik

    return {
        'krol':    wzbogac(krol,    ['gole', 'mecze']),
        'murarz':  wzbogac(murarz,  ['stracone', 'mecze']),
        'kosiarz': wzbogac(kosiarz, ['punkty_kartek', 'zolte', 'czerwone']),
    }


def _kibice(turniej):
    """Zwraca listę uczestników z polem zespol i ulubiony_klub."""
    return list(
        turniej.uczestnicy
        .select_related('gracz')
        .order_by('gracz__last_name')
    )


def _klasyfikacja_klubowa(turniej):
    """
    Ranking klubów kibiców.
    Liczymy tylko mecze rozegrane (nie BYE) między graczami kibicującymi różnym klubom.
    Za wygraną 3 pkt, za remis 1 pkt.
    Wynik końcowy: zdobyte / możliwe (jako procent).
    """
    # Słownik gracz_id → ulubiony_klub (tylko niepuste)
    klub_gracza = {
        u.gracz_id: u.ulubiony_klub
        for u in turniej.uczestnicy.all()
        if u.ulubiony_klub
    }

    if not klub_gracza:
        return []

    # Rozegrane mecze (nie BYE) w turnieju
    mecze = Mecz.objects.filter(
        turniej=turniej,
        status='rozegrany',
        gracz_b__isnull=False,
    )

    # Zlicz punkty per klub
    kluby = {}  # nazwa_klubu → {'zdobyte': int, 'mozliwe': int}

    for mecz in mecze:
        klub_a = klub_gracza.get(mecz.gracz_a_id)
        klub_b = klub_gracza.get(mecz.gracz_b_id)

        # Oba muszą kibicować i różnym klubom
        if not klub_a or not klub_b or klub_a == klub_b:
            continue

        for klub in [klub_a, klub_b]:
            if klub not in kluby:
                kluby[klub] = {'zdobyte': 0, 'mozliwe': 0}
            kluby[klub]['mozliwe'] += 3

        if mecz.zwyciezca == 'A':
            kluby[klub_a]['zdobyte'] += 3
        elif mecz.zwyciezca == 'B':
            kluby[klub_b]['zdobyte'] += 3
        elif mecz.zwyciezca == 'remis':
            kluby[klub_a]['zdobyte'] += 1
            kluby[klub_b]['zdobyte'] += 1

    # Zbuduj ranking
    ranking = []
    for klub, dane in kluby.items():
        wspolczynnik = dane['zdobyte'] / dane['mozliwe'] if dane['mozliwe'] else 0
        ranking.append({
            'klub':         klub,
            'zdobyte':      dane['zdobyte'],
            'mozliwe':      dane['mozliwe'],
            'wspolczynnik': round(wspolczynnik * 100, 1),
        })

    ranking.sort(key=lambda x: (-x['wspolczynnik'], x['klub']))
    return ranking


def _typer(turniej):
    """
    Zwraca ranking typerów dla danego turnieju.
    Każdy wpis: {'gracz': Player, 'punkty': int, 'typ': TypTurnieju}
    Posortowany malejąco po punktach.
    """
    try:
        wynik = turniej.wynik
    except WynikTurnieju.DoesNotExist:
        wynik = None

    typy = TypTurnieju.objects.filter(turniej=turniej).select_related(
        'gracz', 'miejsce_1', 'miejsce_2', 'miejsce_3',
        'miejsce_ostatnie', 'krol_strzelcow', 'murarz', 'kosiarz'
    )

    ranking = []
    for typ in typy:
        ranking.append({
            'gracz':  typ.gracz,
            'punkty': typ.oblicz_punkty(wynik),
            'typ':    typ,
        })

    ranking.sort(key=lambda x: (-x['punkty'], x['gracz'].display_name().lower()))
    return ranking, wynik


# ─────────────────────────────────────────────────────────────────────
#  WIDOKI
# ─────────────────────────────────────────────────────────────────────

def index(request):
    """Strona główna — wyświetla turniej z najwyższą datą rozpoczęcia."""
    turniej = Turniej.objects.order_by('-data_start').first()

    if not turniej:
        return render(request, 'laczkerscup/index.html', {'brak_turnieju': True})

    stats = _statystyki_turnieju(turniej)

    poziomy_etapow = _wszystkie_etapy(turniej)

    harmonogram          = _harmonogram(turniej)
    nagrody              = _nagrody(turniej)
    kibice               = _kibice(turniej)
    klasyfikacja_klubowa = _klasyfikacja_klubowa(turniej)
    typer_ranking, typer_wynik = _typer(turniej)

    return render(request, 'laczkerscup/index.html', {
        'turniej':              turniej,
        'stats':                stats,
        'poziomy_etapow':       poziomy_etapow,
        'harmonogram':          harmonogram,
        'nagrody':              nagrody,
        'kibice':               kibice,
        'klasyfikacja_klubowa': klasyfikacja_klubowa,
        'typer':                typer_ranking,
        'typer_wynik':          typer_wynik,
    })


def turnieje(request):
    """Lista wszystkich turniejów — aktywne i archiwalne."""
    dzisiaj = timezone.now().date()

    aktywne   = Turniej.objects.filter(
        Q(data_koniec__gte=dzisiaj) | Q(data_koniec__isnull=True)
    ).order_by('-data_start')

    archiwalne = Turniej.objects.filter(
        data_koniec__lt=dzisiaj
    ).order_by('-data_start')

    return render(request, 'laczkerscup/turnieje.html', {
        'aktywne':   aktywne,
        'archiwalne': archiwalne,
    })


def turniej_detail(request, pk):
    """Szczegóły jednego turnieju — ta sama logika co index ale dla wybranego."""
    turniej = get_object_or_404(Turniej, pk=pk)

    stats = _statystyki_turnieju(turniej)
    poziomy_etapow = _wszystkie_etapy(turniej)
    harmonogram          = _harmonogram(turniej)
    nagrody              = _nagrody(turniej)
    kibice               = _kibice(turniej)
    klasyfikacja_klubowa = _klasyfikacja_klubowa(turniej)
    typer_ranking, typer_wynik = _typer(turniej)

    return render(request, 'laczkerscup/index.html', {
        'turniej':              turniej,
        'stats':                stats,
        'poziomy_etapow':       poziomy_etapow,
        'harmonogram':          harmonogram,
        'nagrody':              nagrody,
        'kibice':               kibice,
        'klasyfikacja_klubowa': klasyfikacja_klubowa,
        'typer':                typer_ranking,
        'typer_wynik':          typer_wynik,
    })


def gracz_w_turnieju(request, turniej_pk, gracz_pk):
    """Mecze i statystyki gracza w konkretnym turnieju."""
    turniej = get_object_or_404(Turniej, pk=turniej_pk)
    gracz   = get_object_or_404(Player, pk=gracz_pk)

    mecze = (
        Mecz.objects
        .filter(turniej=turniej)
        .filter(Q(gracz_a=gracz) | Q(gracz_b=gracz))
        .select_related('gracz_a', 'gracz_b', 'etap')
        .order_by('etap__poziom', 'id')
    )

    # Statystyki tylko z rozegranych (WystepGracza nie ma zaplanowanych)
    wystepy = WystepGracza.objects.filter(turniej=turniej, gracz=gracz)
    sumy = wystepy.aggregate(
        mecze    = Count('id'),
        pkt      = Sum('punkty'),
        gole_za  = Sum('gole_strzelone'),
        gole_str = Sum('gole_stracone'),
        zolte    = Sum('zolte_kartki'),
        czerwone = Sum('czerwone_kartki'),
    )

    return render(request, 'laczkerscup/gracz_turniej.html', {
        'turniej': turniej,
        'gracz':   gracz,
        'mecze':   mecze,
        'sumy':    sumy,
    })



def turniej_notka(request, pk):
    """Notka / artykuł o turnieju ze zdjęciem."""
    turniej = get_object_or_404(Turniej, pk=pk)
    return render(request, 'laczkerscup/turniej_notka.html', {
        'turniej': turniej,
    })

def elo(request):
    ranking = get_elo_ranking()
    return render(request, 'laczkerscup/elo.html', {'ranking': ranking})


def elo_history(request, player_id):
    player = get_object_or_404(Player, id=player_id)
    history = (
        EloHistory.objects
        .filter(player=player)
        .select_related('match', 'match__player_a', 'match__player_b')
        .order_by('-match__date', '-match__id')
    )
    return render(request, 'laczkerscup/elo_history.html', {
        'player':  player,
        'history': history,
    })
