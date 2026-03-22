# FIFALeague — laczkerscup

Portal turniejowy do organizacji rozgrywek FIFA. System turniejowy z tabelami grupowymi, fazami pucharowymi, rankingiem ELO i generatorami par.

---

## Spis treści

1. [Struktura plików](#1-struktura-plików)
2. [Ranking ELO](#2-ranking-elo)
3. [Turnieje i etapy](#3-turnieje-i-etapy)
4. [Mecze](#4-mecze)
5. [Tabela grupowa](#5-tabela-grupowa)
6. [Harmonogram](#6-harmonogram)
7. [Generator — Losowanie ELO](#7-generator--losowanie-elo-faza-1)
8. [Generator — System Szwajcarski](#8-generator--system-szwajcarski)
9. [Klasyfikacje](#9-klasyfikacje)
10. [Dostęp i uprawnienia](#10-dostęp-i-uprawnienia)
11. [FAQ](#11-faq)

---

## 1. Struktura plików

```
laczkerscup/
├── models.py              # Definicje wszystkich tabel w bazie
├── views.py               # Logika widoków — helpery i widoki główne
├── urls.py                # Mapowanie URL na widoki
├── admin.py               # Konfiguracja panelu administracyjnego
├── elo.py                 # Cała logika obliczania rankingu ELO
├── signals.py             # Auto-przeliczanie ELO po zapisie meczu
├── losowanie_logika.py    # Algorytm losowania ELO (Faza 1), bez Django
├── views_losowanie.py     # Widoki generatora losowania ELO
├── szwajcar_logika.py     # Algorytm systemu szwajcarskiego, bez Django
├── views_szwajcar.py      # Widoki generatora szwajcarskiego
└── templates/laczkerscup/
    ├── base.html
    ├── index.html          # Strona główna turnieju
    ├── _tabela_grupowa.html
    ├── _mecz_card.html
    ├── gracz_turniej.html
    ├── turnieje.html
    ├── elo.html
    ├── elo_history.html
    ├── losowanie_formularz.html
    ├── losowanie_wyniki.html
    ├── losowanie_lista.html
    └── szwajcar.html
```

---

## 2. Ranking ELO

### Na czym polega

Każdy gracz startuje z ratingiem **1000**. Po każdym meczu ratingi obu graczy zmieniają się w zależności od wyniku i różnicy poziomów. Im silniejszy przeciwnik — tym więcej zyskujesz za wygraną i mniej tracisz za przegraną.

### Wzory

**Oczekiwany wynik:**
```
E = 1 / (1 + 10 ^ ((R_przeciwnik - R_gracz) / 400))
```

**Zmiana ratingu:**
```
Δ = K × (wynik - E)
```
gdzie `wynik`: 1.0 = wygrana, 0.5 = remis, 0.0 = przegrana

### Współczynnik K

Kontroluje jak mocno jeden mecz zmienia rating. Im wyższy K, tym większe wahania.

| Mecze rozegrane | K  | Interpretacja                          |
|-----------------|----|----------------------------------------|
| < 5             | 40 | Nowy gracz — szybkie ustalenie poziomu |
| 5–9             | 32 | Średniozaawansowany                    |
| 10+             | 24 | Doświadczony — stabilny rating         |

> **Zmiana K:** edytuj `get_k_factor()` w `elo.py`. Zmień progi (`5`, `10`) lub wartości (`40`, `32`, `24`).

> **Zmiana ratingu startowego:** edytuj `INITIAL_RATING = 1000` w `elo.py` (linia 14).

### Automatyczne przeliczanie

Ranking przelicza się **automatycznie** przy każdym dodaniu, edycji lub usunięciu meczu ELO. Działa przez `signals.py` — Django wysyła `post_save`/`post_delete` do modelu `EloMatch`, który wywołuje `recalculate_elo()`.

`recalculate_elo()` usuwa całą historię i przelicza **od zera** chronologicznie — dlatego zmiana daty meczu może wpłynąć na ratingi wszystkich graczy.

### Modele

| Model        | Co przechowuje                                         |
|--------------|--------------------------------------------------------|
| `Player`     | Gracz (first_name, last_name, nickname, is_active)     |
| `EloMatch`   | Mecz ELO: player_a, player_b, date, result (A/B/D)    |
| `EloHistory` | Historia zmian ratingu — jeden rekord na gracza/mecz  |

### Dodawanie meczów ELO

Admin → EloMatches → Dodaj. Pola: Player A, Player B, Date (ważna — decyduje o kolejności przeliczania), Result (A/B/D).

> ELO działa **niezależnie** od systemu turniejowego. To osobny moduł tylko do rankingu graczy.

---

## 3. Turnieje i etapy

### Tworzenie turnieju

Admin → Turnieje → Dodaj. W jednym formularzu tworzysz turniej razem z etapami i uczestnikami.

### Etapy (`Etap`)

Każdy turniej ma etapy. Etap = jedna faza rozgrywek.

| Pole                  | Opis                                                                                          |
|-----------------------|-----------------------------------------------------------------------------------------------|
| Nazwa                 | Np. "Faza grupowa", "Półfinały", "Finał"                                                      |
| Typ                   | `grupowy` — liczy tabelę punktową; `pucharowy` — pokazuje drabinkę/obrazek                   |
| Poziom                | Liczba całkowita. Wyższy = wyżej na stronie. Np: 1 = grupy, 2 = ćwierćfinały, 3 = finał     |
| Obrazek (opcjonalny)  | Tylko dla `pucharowy` — zdjęcie drabinki. Bez obrazka → czarny placeholder                  |

Kilka etapów na **tym samym poziomie** (np. Grupa A i Grupa B) wyświetla się jako zakładki przewijane w bok. Etap wyższy poziomem zawsze jest powyżej.

### Uczestnicy turnieju (`UczestnikTurnieju`)

W formularzu turnieju dodajesz uczestników inline:

| Pole            | Opis                                                                  |
|-----------------|-----------------------------------------------------------------------|
| Gracz           | Wybierz z listy                                                       |
| Zespół          | Jakim klubem FIFA gra w tym turnieju                                  |
| Ulubiony klub   | Któremu kibicuje w realu (opcjonalne — używane w rankingu Wierny Kibic) |

### Który turniej pokazuje się na stronie głównej?

Zawsze ten z najwyższą `data_start`. Dostęp do konkretnego turnieju przez `/turnieje/<pk>/`.

---

## 4. Mecze

### Statusy meczu

| Status        | Co się dzieje                                                    | Punkty              |
|---------------|------------------------------------------------------------------|---------------------|
| `zaplanowany` | Mecz w harmonogramie, brak `WystepGracza` w bazie               | Nie liczone         |
| `rozegrany`   | Wpisz wynik (gole, kartki, zwycięzca). Tworzone `WystepGracza`. | Liczone normalnie   |
| `wolny_los`   | Gracz A dostaje 3 pkt automatycznie. Gracz B = pusty.           | A: 3 pkt, B: 0 pkt  |

> Zmiana statusu z `zaplanowany` na `rozegrany` automatycznie tworzy `WystepGracza`. Zmiana wyniku istniejącego meczu też przelicza je od nowa — `Mecz.save()` wywołuje `przelicz_wystepy()` za każdym razem.

### Pole Zwycięzca

System **nie ustawia zwycięzcy automatycznie** na podstawie goli — wpisz ręcznie: `A`, `B` lub `remis`.

### BYE (Wolny los)

| Pole     | Wartość                        |
|----------|--------------------------------|
| Status   | `wolny_los`                    |
| Gracz A  | Gracz który ma wolny los       |
| Gracz B  | Zostaw puste                   |

Efekt: Gracz A dostaje 3 pkt. Gracz B nie jest tworzony w `WystepGracza`. BYE **nie liczy się** do klasyfikacji klubowej.

### WystepGracza

Tabela agregująca statystyki gracza per mecz. Tworzona/usuwana automatycznie przez `Mecz.save()`. **Nigdy nie edytuj ręcznie.** Na tej tabeli opierają się: tabela grupowa, nagrody indywidualne, klasyfikacja kibice.

---

## 5. Tabela grupowa

### Skąd bierze dane

Z `WystepGracza` dla danego etapu. Bierze pod uwagę tylko mecze o statusie `rozegrany` i `wolny_los` — zaplanowane są pomijane.

### Sortowanie

Gracze sortowani kolejno wg:

1. Punkty (malejąco)
2. Różnica bramek ogółem
3. Bramki zdobyte ogółem
4. Alfabetycznie (nick/nazwisko)

> Chcesz dodać mecze bezpośrednie jako kryterium? W `views.py`, funkcja `_tabela_grupowa()`, na końcu metody `sort()` są komentarze `# 4. Tu można dodać` — tam wstaw logikę.

### Forma

Ostatnie 5 meczów gracza w danym etapie: **W** = wygrana (3 pkt), **R** = remis (1 pkt), **P** = przegrana (0 pkt).

---

## 6. Harmonogram

Widoczny na stronie turnieju w 3 zakładkach:

| Zakładka      | Co pokazuje                                           |
|---------------|-------------------------------------------------------|
| Rozegrane     | Status: `rozegrany` lub `wolny_los`, od najnowszego  |
| Nadchodzące   | Status: `zaplanowany`                                 |
| Wszystkie     | Wszystkie mecze turnieju                              |

Domyślnie widać **5 meczów**, przycisk "Pokaż wszystkie" odkrywa resztę.

> Zmiana limitu: `templates/laczkerscup/index.html` → znajdź `|slice:":5"` i zmień liczbę.

---

## 7. Generator — Losowanie ELO (Faza 1)

### Na czym polega

Generator tworzy pary na kilka kolejek naraz. Gracze dzieleni są na dwie grupy: **R** (Rozstawieni) i **N** (Nierozstawieni).

| Runda           | Zasada                                |
|-----------------|---------------------------------------|
| Nieparzysta (1,3) | R vs N — każdy R gra z kimś z N     |
| Parzysta (2,4)  | R vs R i N vs N — grupy wewnętrznie  |

- Pary się nie powtarzają
- BYE rotuje — jeśli liczby są nieparzyste, ktoś pauzuje, ale nie dwa razy pod rząd

### Wymagania co do liczby graczy

- Parzysta łączna liczba graczy: R i N mogą być równe (np. 4R + 4N)
- Nieparzysta łączna liczba graczy: R musi być o 1 więcej niż N (np. 5R + 4N)

### Jak używać

1. Generatory → Losowanie ELO
2. Zaznacz graczy — checkbox R lub N
3. Wybierz liczbę kolejek (1–4)
4. Kliknij Generuj — pary zapisują się do bazy
5. Na podstawie losowania wpisz mecze ręcznie w adminie (Admin → Mecze)

### Pliki

- `losowanie_logika.py` — czysty algorytm bez Django
- `views_losowanie.py` — widoki (formularz, wyniki, historia)
- `templates/`: `losowanie_formularz.html`, `losowanie_wyniki.html`, `losowanie_lista.html`

---

## 8. Generator — System Szwajcarski

### Na czym polega

Generuje pary kolejka po kolejce na podstawie aktualnej tabeli punktowej turnieju. Gracze z podobną liczbą punktów grają ze sobą.

- Gracze sortowani malejąco po punktach → pierwszy z drugim, trzeci z czwartym itd.
- Para nie może się powtórzyć — system sprawdza **wszystkie** dotychczasowe mecze w turnieju (nie tylko wygenerowane przez szwajcara)
- Nieparzysta liczba graczy: jeden dostaje BYE (+3 pkt), BYE rotuje

### Maksymalna liczba kolejek

```
maks_kolejek = liczba_graczy - 1
```

### Jak używać

1. Generatory → System Szwajcarski
2. Wybierz turniej z dropdown
3. Kliknij "Generuj kolejkę N"
4. Wpisz wyniki meczów w adminie
5. Wróć i generuj kolejną kolejkę

Historia wygenerowanych kolejek widoczna po prawej. Można usunąć tylko **ostatnią** kolejkę.

### Kafelki informacyjne

| Kafelek            | Co oznacza                                                         |
|--------------------|--------------------------------------------------------------------|
| Graczy             | Liczba uczestników turnieju                                        |
| Kolejki w turnieju | Max liczba meczów jaką ma dowolny gracz — estymacja rozegranych kolejek |
| Kolejki szwajcara  | Ile razy kliknięto "Generuj" w tym generatorze                    |
| Maks. kolejek      | n−1 (teoretyczne maksimum)                                        |
| Następna kolejka   | Numer do wygenerowania                                             |

### Pliki

- `szwajcar_logika.py` — algorytm parowania
- `views_szwajcar.py` — widoki
- `templates/`: `szwajcar.html`

---

## 9. Klasyfikacje

### Król strzelców

Top 3 graczy z największą liczbą goli strzelonych. Liczy z `WystepGracza` (mecze `rozegrany` + `wolny_los`).

### Murarz

Top 3 z najmniejszą liczbą goli straconych. Liczy **tylko** z meczów `rozegrany` (BYE wykluczone).

### Kosiarz

Top 3 z największą liczbą punktów kartkowych. Punktacja: żółta = 1 pkt, czerwona = 2 pkt.

### Wierny kibic (ranking klubowy)

Ranking klubów których kibicami są gracze w turnieju.

- Liczone tylko mecze `rozegrany` między graczami kibicującymi **różnym i niepustym** klubom
- BYE się nie liczy
- Wygrana: 3 pkt, remis: 1 pkt, przegrana: 0 pkt
- Wynik = (punkty zdobyte / punkty możliwe) × 100%

> Przypisanie kibica: Admin → Turnieje → edytuj → tabela uczestników → pole "Ulubiony klub".

---

## 10. Dostęp i uprawnienia

Generatory (Losowanie ELO, System Szwajcarski) wymagają zalogowania — dekorator `@login_required` w `views_losowanie.py` i `views_szwajcar.py`.

Przekierowanie ustawione w `settings.py`:
```python
LOGIN_URL = '/admin/login/'
```

Strona główna, turnieje, ranking ELO — dostępne publicznie bez logowania.

---

## 11. FAQ

**Zmieniłem wynik meczu — czy statystyki się przeliczą?**  
Tak. `Mecz.save()` automatycznie usuwa i tworzy na nowo rekordy `WystepGracza`.

**Zmieniłem datę meczu ELO — czy ranking się przelicza?**  
Tak, w pełni od zera. Zmiana kolejności chronologicznej może zmienić ratingi wszystkich graczy.

**Gracz ma 0 punktów w tabeli mimo rozegranych meczów.**  
Sprawdź status meczu w adminie — musi być `rozegrany` lub `wolny_los`. Przy statusie `zaplanowany` `WystepGracza` nie jest tworzony.

**Klasyfikacja Wierny Kibic jest pusta.**  
Upewnij się że: (1) gracze mają wypełnione pole "Ulubiony klub" w uczestniku turnieju, (2) jest co najmniej jeden mecz `rozegrany` między graczami kibicującymi **różnym** klubom.

**System szwajcarski mówi że nie można wygenerować par.**  
Osiągnięto maksimum kolejek (n−1) albo wszystkie możliwe pary już grały. Sprawdź kafelek "Maks. kolejek".

**Chcę dodać nowe kryterium sortowania tabeli grupowej.**  
`views.py` → funkcja `_tabela_grupowa()` → metoda `sort()` na końcu — komentarze `# 4. Tu można dodać` wskazują miejsce.
