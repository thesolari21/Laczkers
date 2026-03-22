"""
losowanie_logika.py
-------------------
Algorytm losowania par do fazy 1 turnieju.
Bez zależności od Django — tylko logika.

Zasady:
- Rundy nieparzyste (1,3): każdy z R gra z kimś z N
- Rundy parzyste   (2,4): R gra z R, N gra z N
- Przy |R| > |N|: jeden gracz z R ma BYE (rotuje)
- Przy |N| nieparzystym: jeden gracz z N ma BYE w rundach parzystych (rotuje)
- Pary się nie powtarzają
"""

import random


def _dopasuj_cross(lista_A, lista_B, uzyte_pary):
    """Losuje perfect matching między A i B, pomijając już użyte pary."""
    A = lista_A[:]
    B = lista_B[:]
    random.shuffle(A)
    random.shuffle(B)
    wynik = []
    zajete_B = set()

    def backtrack(i):
        if i == len(A):
            return True
        a = A[i]
        kandydaci = [
            b for b in B
            if b not in zajete_B
            and (min(a, b), max(a, b)) not in uzyte_pary
        ]
        random.shuffle(kandydaci)
        for b in kandydaci:
            wynik.append((a, b))
            zajete_B.add(b)
            if backtrack(i + 1):
                return True
            wynik.pop()
            zajete_B.remove(b)
        return False

    return wynik if backtrack(0) else None


def _dopasuj_wewnetrzny(lista_K, uzyte_pary):
    """Losuje perfect matching wewnątrz koszyka (musi być parzysta liczba graczy)."""
    if len(lista_K) % 2 != 0:
        return None
    K = lista_K[:]
    random.shuffle(K)
    wynik = []

    def backtrack(pozostali):
        if not pozostali:
            return True
        a = pozostali[0]
        reszta = pozostali[1:]
        kandydaci = [
            b for b in reszta
            if (min(a, b), max(a, b)) not in uzyte_pary
        ]
        random.shuffle(kandydaci)
        for b in kandydaci:
            wynik.append((a, b))
            if backtrack([x for x in reszta if x != b]):
                return True
            wynik.pop()
        return False

    return wynik if backtrack(K) else None


def losuj(gracze_R, gracze_N, liczba_kolejek, seed=None):
    """
    Główna funkcja. Zwraca (rundy, blad).

    rundy = lista krotek:
        (numer_kolejki, pary, gracze_z_bye)
        pary          = [(id_a, id_b), ...]
        gracze_z_bye  = [id, ...]  — gracze bez meczu w tej kolejce

    blad = None jeśli OK, string z opisem problemu jeśli błąd.
    """
    if seed is not None:
        random.seed(seed)

    R = list(gracze_R)
    N = list(gracze_N)
    uzyte_pary = set()
    rundy = []
    bye_R_idx = 0
    bye_N_idx = 0

    for nr in range(1, liczba_kolejek + 1):
        cross = (nr % 2 == 1)  # True = runda nieparzysta = R vs N
        bye_gracze = []

        if cross:
            aktywni_R = R[:]
            if len(R) > len(N):
                bye = R[bye_R_idx % len(R)]
                bye_R_idx += 1
                bye_gracze.append(bye)
                aktywni_R = [p for p in R if p != bye]
            pary = _dopasuj_cross(aktywni_R, N, uzyte_pary)

        else:
            aktywni_R = R[:]
            aktywni_N = N[:]
            if len(R) % 2 != 0:
                bye = R[bye_R_idx % len(R)]
                bye_R_idx += 1
                bye_gracze.append(bye)
                aktywni_R = [p for p in R if p != bye]
            if len(N) % 2 != 0:
                bye = N[bye_N_idx % len(N)]
                bye_N_idx += 1
                bye_gracze.append(bye)
                aktywni_N = [p for p in N if p != bye]
            pary_R = _dopasuj_wewnetrzny(aktywni_R, uzyte_pary)
            pary_N = _dopasuj_wewnetrzny(aktywni_N, uzyte_pary)
            pary = (pary_R + pary_N) if (pary_R is not None and pary_N is not None) else None

        if pary is None:
            return None, f'Nie można wygenerować par w kolejce {nr}. Spróbuj ponownie.'

        for a, b in pary:
            uzyte_pary.add((min(a, b), max(a, b)))

        rundy.append((nr, pary, bye_gracze))

    return rundy, None
