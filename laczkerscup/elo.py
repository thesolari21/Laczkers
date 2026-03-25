"""
Logika rankingu ELO.

Dwa miejsca gdzie możesz coś zmienić:
  - INITIAL_RATING  → punkty startowe każdego gracza
  - get_k_factor()  → jak szybko zmienia się rating
"""

import math
from .models import Player, EloMatch, EloHistory


INITIAL_RATING = 1000


def get_k_factor(matches_played):
    """
    Współczynnik K — im wyższy, tym większe zmiany ratingu po meczu.
    Nowi gracze mają wyższe K żeby szybciej trafić na właściwy poziom.

    Zmień progi i wartości według uznania.
    """
    if matches_played < 5:
        return 40   # nowy gracz
    elif matches_played < 10:
        return 32   # średniozaawansowany
    else:
        return 24   # doświadczony


def recalculate_elo():
    """
    Przelicza cały ranking ELO od zera.
    Wywoływana automatycznie przez signals.py po każdym zapisie/usunięciu meczu.

    Co robi krok po kroku:
    1. Usuwa całą tabelę EloHistory.
    2. Pobiera wszystkie mecze od najstarszego do najnowszego.
    3. Dla każdego meczu oblicza zmianę ratingu i zapisuje 2 rekordy EloHistory.
    """

    # Krok 1 — czyścimy historię
    EloHistory.objects.all().delete()

    # Krok 2 — zbieramy aktualne ratingi wszystkich graczy (start: 1000)
    # Słownik: { player_id: aktualny_rating }
    ratings = {}
    for player in Player.objects.all():
        ratings[player.id] = INITIAL_RATING

    # Słownik: { player_id: liczba_rozegranych_meczów }
    # (potrzebne do obliczenia K przed każdym meczem)
    played = {}
    for player in Player.objects.all():
        played[player.id] = 0

    # Krok 3 — przechodzimy przez mecze chronologicznie
    matches = EloMatch.objects.select_related('player_a', 'player_b').order_by('date', 'id')

    for match in matches:
        id_a = match.player_a_id
        id_b = match.player_b_id

        rating_a = ratings[id_a]
        rating_b = ratings[id_b]

        # Oczekiwany wynik wg formuły ELO
        # E_A = 1 / (1 + 10^((R_B - R_A) / 400))
        expected_a = 1 / (1 + math.pow(10, (rating_b - rating_a) / 400))
        expected_b = 1 - expected_a

        # Rzeczywisty wynik: wygrana = 1, remis = 0.5, przegrana = 0
        if match.result == 'A':
            score_a, score_b = 1.0, 0.0
        elif match.result == 'B':
            score_a, score_b = 0.0, 1.0
        else:  # remis
            score_a, score_b = 0.5, 0.5

        # Zmiana ratingu = K * (wynik_rzeczywisty - wynik_oczekiwany)
        k_a = get_k_factor(played[id_a])
        k_b = get_k_factor(played[id_b])

        delta_a = round(k_a * (score_a - expected_a))
        delta_b = round(k_b * (score_b - expected_b))

        new_rating_a = rating_a + delta_a
        new_rating_b = rating_b + delta_b

        # Zapisujemy 2 rekordy historii (jeden dla każdego gracza)
        EloHistory.objects.create(
            player        = match.player_a,
            match         = match,
            rating_before = rating_a,
            delta         = delta_a,
            rating_after  = new_rating_a,
        )
        EloHistory.objects.create(
            player        = match.player_b,
            match         = match,
            rating_before = rating_b,
            delta         = delta_b,
            rating_after  = new_rating_b,
        )

        # Aktualizujemy ratingi i liczniki na potrzeby kolejnych meczów
        ratings[id_a] = new_rating_a
        ratings[id_b] = new_rating_b
        played[id_a] += 1
        played[id_b] += 1


def get_elo_ranking():
    """
    Zwraca listę słowników do użycia w szablonie Django (widok elo.html).

    Sortowanie:
      - Najpierw gracze z meczami, malejąco po ratingu.
      - Na końcu debiutanci (0 meczów), alfabetycznie.

    Każdy słownik ma klucze:
      player    — obiekt Player
      rating    — aktualny rating
      matches   — liczba meczów
      change    — zmiana w ostatnim meczu (0 u debiutantów)
      win_pct   — % wygranych (0 u debiutantów)
      is_debut  — True jeśli brak meczów
      form      — lista ostatnich 5 wyników: 'W', 'D' lub 'L'
    """

    result_with    = []  # gracze z meczami
    result_without = []  # debiutanci

    for player in Player.objects.filter(is_active=True):

        # Historia tego gracza — od najstarszego do najnowszego
        history = list(
            EloHistory.objects
            .filter(player=player)
            .select_related('match')
            .order_by('match__date', 'match__id')
        )

        if not history:
            result_without.append({
                'player':   player,
                'rating':   INITIAL_RATING,
                'matches':  0,
                'change':   0,
                'win_pct':  0,
                'is_debut': True,
                'form':     [],
            })
            continue

        current_rating = history[-1].rating_after
        last_change    = history[-1].delta
        total_matches  = len(history)

        # Liczymy wygrane i punkty ligowe w jednej pętli
        wins   = 0
        points = 0
        for entry in history:
            m = entry.match
            is_winner = (m.result == 'A' and m.player_a_id == player.id) or \
                        (m.result == 'B' and m.player_b_id == player.id)
            if is_winner:
                wins   += 1
                points += 3
            elif m.result == 'D':
                points += 1
        win_pct = round(wins / total_matches * 100)

        # Forma — ostatnie 5 meczów
        form = []
        for entry in history[-5:]:
            m = entry.match
            if m.result == 'D':
                form.append('D')
            elif (m.result == 'A' and m.player_a_id == player.id) or \
                 (m.result == 'B' and m.player_b_id == player.id):
                form.append('W')
            else:
                form.append('L')

        result_with.append({
            'player':   player,
            'rating':   current_rating,
            'matches':  total_matches,
            'change':   last_change,
            'win_pct':  win_pct,
            'points':   points,
            'is_debut': False,
            'form':     form,
        })

    # Sortowanie
    result_with.sort(key=lambda x: x['rating'], reverse=True)
    result_without.sort(key=lambda x: str(x['player']))

    return result_with + result_without
