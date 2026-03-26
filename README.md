# FIFALeague — laczkerscup

Portal turniejowy do organizacji rozgrywek FIFA. System turniejowy z tabelami grupowymi, fazami pucharowymi, rankingiem ELO, generatorami par, typerem i klasyfikacją klubową.

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
10. [Typer](#10-typer)
11. [Notka o turnieju](#11-notka-o-turnieju)
12. [Dostęp i uprawnienia](#12-dostęp-i-uprawnienia)
13. [FAQ](#13-faq)

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
    ├── index.html              # Strona główna turnieju
    ├── _tabela_grupowa.html    # Partial: tabela grupowa
    ├── _mecz_card.html         # Partial: karta meczu w harmonogramie
    ├── gracz_turniej.html      # Mecze gracza w turnieju
    ├── turnieje.html           # Lista turniejów
    ├── turniej_notka.html      # Artykuł/notka o turnieju
    ├── elo.html                # Ranking ELO
    ├── elo_history.html        # Historia meczów ELO gracza
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

| Mecze rozegrane | K  | Interpretacja                          |
|-----------------|----|----------------------------------------|
| < 5             | 40 | Nowy gracz — szybkie ustalenie poziomu |
| 5–9             | 32 | Średniozaawansowany                    |
| 10+             | 24 | Doświadczony — stabilny rating         |

> **Zmiana K:** edytuj `get_k_factor()` w `elo.py`.

> **Zmiana ratingu startowego:** edytuj `INITIAL_RATING = 1000` w `elo.py` (linia 14).

### Automatyczne przeliczanie

Ranking przelicza się **automatycznie** przy każdym dodaniu, edycji lub usunięciu meczu ELO. Działa przez `signals.py` — `post_save`/`post_delete` → `recalculate_elo()` — przelicza od zera chronologicznie.

> Zmiana daty meczu może wpłynąć na ratingi wszystkich graczy (zmiana kolejności chronologicznej).

### Tabela rankingu ELO

Tabela na stronie `/elo/` pokazuje kolumny: `#`, Gracz, Rating ELO, Pkt, Mecze, % Wygranych.

- **Pkt** = punkty ligowe (wygrana = 3, remis = 1, przegrana = 0) — klikalna kolumna do sortowania
- **Rating ELO** — też klikalna do sortowania
- Kliknięcie na gracza → historia jego meczów ELO z filtrowaniem

### Historia meczów ELO (`/elo/history/<id>/`)

Tabela ze wszystkimi meczami gracza. Filtry JS (bez przeładowania strony):
- Data od / do
- Przeciwnik (wpisz fragment nazwiska)
- Wynik (Wygrana / Remis / Przegrana)
- Komentarz

### Modele

| Model        | Co przechowuje                                        |
|--------------|-------------------------------------------------------|
| `Player`     | Gracz (first_name, last_name, nickname, is_active)    |
| `EloMatch`   | Mecz ELO: player_a, player_b, date, result (A/B/D)   |
| `EloHistory` | Historia zmian ratingu — jeden rekord na gracza/mecz  |

### Dodawanie meczów ELO

Admin → EloMatches → Dodaj. Pola: Player A, Player B, Date, Result (A/B/D).

> ELO działa **niezależnie** od systemu turniejowego.

---

## 3. Turnieje i etapy

### Tworzenie turnieju

Admin → Turnieje → Dodaj. W jednym formularzu tworzysz turniej razem z etapami i uczestnikami.

### Etapy (`Etap`)

| Pole                                | Opis                                                                                          |
|-------------------------------------|-----------------------------------------------------------------------------------------------|
| Nazwa                               | Np. "Faza grupowa", "Półfinały", "Finał"                                                      |
| Typ                                 | `grupowy` — liczy tabelę; `pucharowy` — pokazuje drabinkę/obrazek                            |
| Poziom                              | Liczba całkowita. Wyższy = wyżej na stronie. 1 = grupy, 2 = ćwierćfinały, 3 = finał          |
| Obrazek (opcjonalny)                | Tylko dla `pucharowy` — zdjęcie drabinki. Bez obrazka → placeholder                          |
| Sumuj punkty z poprzednich poziomów | Jeśli zaznaczone, punkty gracza ze wszystkich etapów grupowych o niższym poziomie dodają się jako punkty startowe |

Kilka etapów na **tym samym poziomie** wyświetla się jako zakładki. Etap wyższy poziomem jest zawsze powyżej.

### Uczestnicy turnieju (`UczestnikTurnieju`)

| Pole          | Opis                                                                    |
|---------------|-------------------------------------------------------------------------|
| Gracz         | Wybierz z listy                                                         |
| Zespół        | Jakim klubem FIFA gra w tym turnieju                                    |
| Ulubiony klub | Któremu kibicuje w realu (opcjonalne — używane w rankingu Wierny Kibic) |

### Który turniej pokazuje się na stronie głównej?

Zawsze ten z najwyższą `data_start`. Dostęp do konkretnego turnieju przez `/turnieje/<pk>/`.

### Konwencja nazw graczy

`display_name` zwraca: nickname (jeśli ustawiony) lub `Nazwisko I.` Jeśli dwóch graczy ma to samo nazwisko i tę samą pierwszą literę imienia — automatycznie wyświetlane są dwie litery: `Nazwisko Im.`

---

## 4. Mecze

### Statusy meczu

| Status        | Co się dzieje                                                    | Punkty             |
|---------------|------------------------------------------------------------------|--------------------|
| `zaplanowany` | Mecz w harmonogramie, brak `WystepGracza` w bazie               | Nie liczone        |
| `rozegrany`   | Wpisz wynik (gole, kartki, zwycięzca). Tworzone `WystepGracza`. | Liczone normalnie  |
| `wolny_los`   | Gracz A dostaje 3 pkt automatycznie. Gracz B = pusty.           | A: 3 pkt, B: 0 pkt |

> `Mecz.save()` wywołuje `przelicz_wystepy()` przy każdym zapisie — statystyki zawsze aktualne.

### Pole Zwycięzca

System **nie ustawia zwycięzcy automatycznie** — wpisz ręcznie: `A`, `B` lub `remis`.

### BYE (Wolny los)

| Pole    | Wartość                  |
|---------|--------------------------|
| Status  | `wolny_los`              |
| Gracz A | Gracz który ma wolny los |
| Gracz B | Zostaw puste             |

BYE **nie liczy się** do klasyfikacji klubowej ani statystyk murarza/kosiarza.

### WystepGracza

Tabela agregująca statystyki gracza per mecz. Tworzona automatycznie przez `Mecz.save()`. **Nigdy nie edytuj ręcznie.**

---

## 5. Tabela grupowa

### Skąd bierze dane

Z `WystepGracza` dla danego etapu. Mecze `zaplanowany` są pomijane.

### Kolumny

`#` | Gracz | M | PKT | Bilans W-R-P | G+ | G- | Bil | Forma

- **Bil** = G+ minus G- (zielony jeśli dodatni, czerwony jeśli ujemny)
- **PKT** — jeśli etap ma zaznaczone `sumuj_punkty_z_poprzednich`, przy graczu widoczna adnotacja np. `9 (6↑)` informująca ile punktów przeniesionych

### Sortowanie

1. Punkty łącznie (malejąco)
2. Różnica bramek
3. Bramki zdobyte
4. Alfabetycznie

### Przenoszenie punktów między etapami

Jeśli turniej ma etap 1 (grupy A, B, C) i etap 2 (grupy E, F), zaznacz w każdej grupie etapu 2 opcję **"Sumuj punkty z poprzednich poziomów"**. System automatycznie znajdzie wszystkie mecze gracza ze wszystkich etapów grupowych o niższym poziomie i doda je jako punkty startowe — niezależnie w której grupie grał.

- Etap na poziomie 3 z zaznaczoną opcją → sumuje punkty z poziomów 1 i 2 łącznie
- Jeśli masz 3 grupy na poziomie 2 — zaznacz opcję przy każdej z nich osobno

### Forma

Ostatnie 5 meczów gracza w danym etapie: **W** = wygrana, **R** = remis, **P** = przegrana.

---

## 6. Harmonogram

Widoczny na stronie turnieju w 3 zakładkach:

| Zakładka    | Co pokazuje                                          |
|-------------|------------------------------------------------------|
| Rozegrane   | Status: `rozegrany` lub `wolny_los`, od najnowszego  |
| Nadchodzące | Status: `zaplanowany`                                |
| Wszystkie   | Wszystkie mecze turnieju                             |

Domyślnie widać **5 meczów**, przycisk "Pokaż wszystkie" odkrywa resztę. Kliknięcie na gracza w karcie meczu → jego mecze w turnieju.

> Zmiana limitu: `index.html` → `|slice:":5"`

---

## 7. Generator — Losowanie ELO (Faza 1)

### Na czym polega

Generator tworzy pary na kilka kolejek naraz. Gracze dzieleni są na dwie grupy: **R** (Rozstawieni) i **N** (Nierozstawieni).

| Runda             | Zasada                              |
|-------------------|-------------------------------------|
| Nieparzysta (1,3) | R vs N — każdy R gra z kimś z N     |
| Parzysta (2,4)    | R vs R i N vs N — grupy wewnętrznie |

- Pary się nie powtarzają
- BYE rotuje — nie dwa razy pod rząd
- Parzysta łączna liczba: R = N (np. 4+4); nieparzysta: R o 1 więcej niż N (np. 5+4)

### Jak używać

1. Generatory → Losowanie ELO
2. Zaznacz graczy — checkbox R lub N
3. Wybierz liczbę kolejek (1–4)
4. Kliknij Generuj
5. Wpisz mecze ręcznie w adminie

### Pliki

`losowanie_logika.py`, `views_losowanie.py`, `losowanie_formularz.html`, `losowanie_wyniki.html`, `losowanie_lista.html`

---

## 8. Generator — System Szwajcarski

### Na czym polega

Generuje pary kolejka po kolejce na podstawie aktualnej tabeli punktowej. Gracze z podobną liczbą punktów grają ze sobą.

- Para nie może się powtórzyć — system sprawdza **wszystkie** mecze w turnieju (nie tylko ze szwajcara)
- Nieparzysta liczba graczy: BYE rotuje (+3 pkt)
- Maks. kolejek = liczba graczy − 1

### Jak używać

1. Generatory → System Szwajcarski
2. Wybierz turniej
3. Kliknij "Generuj kolejkę N"
4. Wpisz wyniki w adminie, wróć i generuj kolejną

Można usunąć tylko **ostatnią** kolejkę.

### Kafelki

| Kafelek            | Co oznacza                                               |
|--------------------|----------------------------------------------------------|
| Graczy             | Liczba uczestników                                       |
| Kolejki w turnieju | Max mecze jednego gracza — estymacja rozegranych kolejek |
| Kolejki szwajcara  | Ile razy kliknięto "Generuj"                             |
| Maks. kolejek      | n−1                                                      |
| Następna kolejka   | Numer do wygenerowania                                   |

### Pliki

`szwajcar_logika.py`, `views_szwajcar.py`, `szwajcar.html`

---

## 9. Klasyfikacje

Na stronie turnieju sekcja "Klasyfikacje" zawiera 5 kafelków z top 3. Każdy ma przycisk "Wszyscy →" / "Szczegóły →" otwierający modal z pełną tabelą. Zamykanie: przycisk ×, klik w tło lub Escape.

### Król strzelców

Najwięcej goli strzelonych. Liczy z `WystepGracza` (`rozegrany` + `wolny_los`).

### Murarz

Najmniej goli straconych. Liczy **tylko** z meczów `rozegrany` (BYE wykluczone).

### Kosiarz

Punkty kartkowe: żółta = 1, czerwona = 2.

### Wierny kibic (ranking klubowy)

- Tylko mecze `rozegrany` między graczami kibicującymi **różnym i niepustym** klubom
- Wygrana: 3 pkt, remis: 1 pkt
- Wynik = (zdobyte / możliwe) × 100%

> Przypisanie kibica: Admin → Turnieje → edytuj → uczestnicy → "Ulubiony klub".

### Typer

Ranking graczy typujących — patrz sekcja 10.

---

## 10. Typer

System przewidywania wyników turnieju. Odpowiedzi wpisuje admin ręcznie na podstawie kartek od graczy.

### Pytania i punktacja

| Pytanie          | Trafienie dokładne | Trafienie częściowe              |
|------------------|--------------------|----------------------------------|
| 1. miejsce       | 2 pkt              | 1 pkt (gracz znalazł się w top 3)|
| 2. miejsce       | 2 pkt              | 1 pkt (gracz znalazł się w top 3)|
| 3. miejsce       | 2 pkt              | 1 pkt (gracz znalazł się w top 3)|
| Ostatnie miejsce | 1 pkt              | —                                |
| Król strzelców   | 1 pkt              | —                                |
| Murarz           | 1 pkt              | —                                |
| Kosiarz          | 1 pkt              | —                                |
| Zwycięski klub   | 1 pkt              | —                                |

**Maksimum: 11 pkt.** Punkty liczone w locie — każda zmiana natychmiast aktualizuje ranking.

### Jak używać

**Typy graczy:** Admin → Typy graczy → Dodaj → wybierz turniej, gracza i jego 8 odpowiedzi.

**Poprawne wyniki:** Admin → Turnieje → edytuj → inline "Wynik turnieju (typer)" na dole.

**Modal szczegółów:** "Szczegóły →" otwiera tabelę ze wszystkimi graczami, ich typami i punktami.

### Modele

| Model           | Co przechowuje                                         |
|-----------------|--------------------------------------------------------|
| `WynikTurnieju` | Poprawne odpowiedzi — jeden rekord na turniej          |
| `TypTurnieju`   | Odpowiedzi jednego gracza — unique(turniej, gracz)     |

---

## 11. Notka o turnieju

Każdy turniej może mieć artykuł z opisem i zdjęcie.

**Edycja:** Admin → Turnieje → edytuj → pola "Notka o turnieju" (edytor CKEditor) i "Zdjęcie".

**Wyświetlanie:** jeśli notka jest wypełniona, w hero pojawia się link "Więcej o turnieju →" → `/turnieje/<pk>/notka/`.

**Wymagana paczka:** `django-ckeditor`. W `settings.py`:
```python
INSTALLED_APPS += ['ckeditor', 'ckeditor_uploader']
CKEDITOR_UPLOAD_PATH = 'uploads/'
SILENCED_SYSTEM_CHECKS = ['ckeditor.W001']
```

W głównym `urls.py`:
```python
path('ckeditor/', include('ckeditor_uploader.urls')),
```

---

## 12. Dostęp i uprawnienia

Generatory wymagają zalogowania — `@login_required` w `views_losowanie.py` i `views_szwajcar.py`.

```python
LOGIN_URL = '/admin/login/'  # settings.py
```

Strona główna, turnieje, ranking ELO — dostępne publicznie.

---

## 13. FAQ

**Zmieniłem wynik meczu — czy statystyki się przeliczą?**
Tak. `Mecz.save()` zawsze przelicza `WystepGracza`.

**Zmieniłem datę meczu ELO — czy ranking się przelicza?**
Tak, od zera. Kolejność chronologiczna ma znaczenie.

**Gracz ma 0 punktów mimo rozegranych meczów.**
Sprawdź status meczu — musi być `rozegrany` lub `wolny_los`.

**Klasyfikacja Wierny Kibic jest pusta.**
Sprawdź: (1) gracze mają "Ulubiony klub", (2) jest mecz `rozegrany` między kibicami **różnych** klubów.

**Typer pokazuje 0 pkt mimo wpisanych typów.**
Sprawdź czy wypełniłeś "Wynik turnieju (typer)" w adminie turnieju.

**Punkty startowe nie działają w etapie 2.**
Zaznacz "Sumuj punkty z poprzednich poziomów" przy etapie 2. Opcja musi być zaznaczona przy każdej grupie osobno.

**System szwajcarski nie może wygenerować par.**
Osiągnięto maksimum kolejek (n−1) albo wszystkie pary już grały.

**Chcę dodać kryterium sortowania tabeli grupowej.**
`views.py` → `_tabela_grupowa()` → `sort()` → komentarz `# 4. Tu można dodać`.

**Dwóch graczy ma to samo nazwisko i inicjał.**
`display_name` automatycznie pokazuje dwie litery imienia — nie musisz nic robić.
