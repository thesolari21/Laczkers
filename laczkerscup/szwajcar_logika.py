"""
szwajcar_logika.py
------------------
Algorytm parowania systemu szwajcarskiego.
Bez zależności od Django — tylko logika.

Zasady:
- Gracze sortowani malejąco po punktach
- Parujemy pierwszego z drugim, trzeciego z czwartym itd.
- Para nie może się powtórzyć (uwzględniamy wszystkie poprzednie mecze)
- Przy nieparzystej liczbie graczy jeden dostaje BYE (rotuje — nie może dostać drugi raz z rzędu jeśli da się uniknąć)
- Maksymalna liczba kolejek = liczba graczy - 1
"""


def maks_kolejek(liczba_graczy):
    """Maksymalna liczba kolejek jaką można rozegrać."""
    return max(0, liczba_graczy - 1)


def generuj_pary(gracze_z_punktami, rozegrane_pary, bye_historia):
    """
    Generuje pary na kolejną kolejkę.

    Parametry:
        gracze_z_punktami: lista [(gracz_id, punkty), ...] — posortowana malejąco po punktach
        rozegrane_pary:    set of frozenset({id_a, id_b}) — pary które już grały
        bye_historia:      list of gracz_id — kto już dostał BYE (ostatni na końcu = najnowszy)

    Zwraca:
        (pary, bye_gracz, blad)
        pary      = [(id_a, id_b), ...]
        bye_gracz = id gracza który dostaje BYE, lub None
        blad      = None jeśli OK, string z opisem problemu jeśli błąd
    """
    ids = [gid for gid, _ in gracze_z_punktami]
    n   = len(ids)

    if n < 2:
        return [], None, 'Za mało graczy (minimum 2).'

    bye_gracz = None

    # Przy nieparzystej liczbie — wybierz gracza na BYE
    if n % 2 == 1:
        bye_gracz = _wybierz_bye(ids, bye_historia)
        ids = [i for i in ids if i != bye_gracz]

    # Szukaj dopasowania backtrackingiem
    pary = _dopasuj(ids, rozegrane_pary)

    if pary is None:
        return [], bye_gracz, (
            'Nie można wygenerować par — wszyscy już grali ze wszystkimi. '
            'Osiągnięto maksymalną liczbę kolejek dla tej liczby graczy.'
        )

    return pary, bye_gracz, None


def _wybierz_bye(ids, bye_historia):
    """
    Wybierz gracza na BYE.
    Priorytet: kto najdawniej (lub nigdy) miał BYE,
    a jeśli remis — gracz z najniższego miejsca (ostatni na liście).
    """
    # Indeks ostatniego BYE dla każdego gracza (-1 = nigdy nie miał)
    def ostatni_bye(gid):
        for i in range(len(bye_historia) - 1, -1, -1):
            if bye_historia[i] == gid:
                return i
        return -1

    # Sortuj: najpierw ten kto najdawniej miał BYE, przy remisie — ostatni na liście (słabszy)
    kandydaci = sorted(ids, key=lambda gid: (ostatni_bye(gid), -ids.index(gid)))
    return kandydaci[0]


def _dopasuj(ids, rozegrane_pary):
    """
    Greedy + backtracking.
    Paruje pierwszego wolnego z najbliższym możliwym (po rankingu).
    """
    ids = list(ids)
    wynik = []

    def backtrack(pozostali):
        if not pozostali:
            return True
        a = pozostali[0]
        reszta = pozostali[1:]
        for i, b in enumerate(reszta):
            if frozenset({a, b}) not in rozegrane_pary:
                wynik.append((a, b))
                nowa_reszta = reszta[:i] + reszta[i+1:]
                if backtrack(nowa_reszta):
                    return True
                wynik.pop()
        return False

    return wynik if backtrack(ids) else None
