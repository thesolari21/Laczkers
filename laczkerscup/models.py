from django.db import models
from ckeditor.fields import RichTextField
from ckeditor.fields import RichTextField


# ─────────────────────────────────────────────────────────────────────
#  GRACZE (istniejący model — bez zmian)
# ─────────────────────────────────────────────────────────────────────

class Player(models.Model):
    first_name  = models.CharField('Imię',      max_length=50)
    last_name   = models.CharField('Nazwisko',  max_length=50)
    nickname    = models.CharField('Pseudonim', max_length=50, blank=True, null=True, unique=True)
    joined_date = models.DateField('Data dołączenia', auto_now_add=True)
    is_active   = models.BooleanField('Aktywny', default=True)

    class Meta:
        verbose_name        = 'Gracz'
        verbose_name_plural = 'Gracze'
        ordering            = ['last_name', 'first_name']

    def __str__(self):
        if self.nickname:
            return f'{self.nickname} ({self.first_name} {self.last_name})'
        return f'{self.first_name} {self.last_name}'

    def display_name(self):
        if self.nickname:
            return self.nickname
        # Sprawdź czy jest inny aktywny gracz z tym samym nazwiskiem i tą samą pierwszą literą imienia
        from django.db.models import Q
        duplikat = Player.objects.filter(
            last_name=self.last_name,
            is_active=True,
        ).exclude(pk=self.pk).filter(first_name__startswith=self.first_name[0]).exists()
        if duplikat:
            return f'{self.last_name} {self.first_name[:2]}.'
        return f'{self.last_name} {self.first_name[0]}.' 


# ─────────────────────────────────────────────────────────────────────
#  ELO (istniejące modele — bez zmian)
# ─────────────────────────────────────────────────────────────────────

class EloMatch(models.Model):
    RESULT_CHOICES = [
        ('A', 'Wygrywa Gracz A'),
        ('B', 'Wygrywa Gracz B'),
        ('D', 'Remis'),
    ]
    player_a = models.ForeignKey(Player, on_delete=models.PROTECT,
                                 related_name='matches_as_a', verbose_name='Gracz A')
    player_b = models.ForeignKey(Player, on_delete=models.PROTECT,
                                 related_name='matches_as_b', verbose_name='Gracz B')
    result   = models.CharField('Wynik', max_length=1, choices=RESULT_CHOICES)
    date     = models.DateField('Data meczu')
    notes    = models.TextField('Uwagi', blank=True)

    class Meta:
        verbose_name        = 'Mecz ELO'
        verbose_name_plural = 'Mecze ELO'
        ordering            = ['-date', '-id']

    def __str__(self):
        return f'{self.player_a} vs {self.player_b} ({self.date})'


class EloHistory(models.Model):
    player        = models.ForeignKey(Player,   on_delete=models.CASCADE, verbose_name='Gracz')
    match         = models.ForeignKey(EloMatch, on_delete=models.CASCADE, verbose_name='Mecz')
    rating_before = models.IntegerField('Rating przed')
    delta         = models.IntegerField('Zmiana')
    rating_after  = models.IntegerField('Rating po')

    class Meta:
        verbose_name        = 'Historia ELO'
        verbose_name_plural = 'Historia ELO'
        ordering            = ['match__date', 'match__id']

    def __str__(self):
        sign = '+' if self.delta >= 0 else ''
        return f'{self.player} | {self.match.date} | {self.rating_before} {sign}{self.delta} → {self.rating_after}'


# ─────────────────────────────────────────────────────────────────────
#  LOSOWANIE ELO (istniejące modele — bez zmian)
# ─────────────────────────────────────────────────────────────────────

class LosowanieELO(models.Model):
    nazwa          = models.CharField('Nazwa', max_length=100, blank=True)
    data           = models.DateTimeField('Data utworzenia', auto_now_add=True)
    liczba_kolejek = models.PositiveSmallIntegerField('Liczba kolejek')

    class Meta:
        verbose_name        = 'Losowanie ELO'
        verbose_name_plural = 'Losowania ELO'
        ordering            = ['-data']

    def __str__(self):
        return self.nazwa or f'Losowanie #{self.pk} ({self.data.strftime("%d.%m.%Y")})'


class UczestnikLosowania(models.Model):
    KOSZYK = [('R', 'Rozstawiony'), ('N', 'Nierozstawiony')]
    losowanie = models.ForeignKey(LosowanieELO, on_delete=models.CASCADE,
                                  related_name='uczestnicy')
    gracz     = models.ForeignKey(Player, on_delete=models.PROTECT)
    koszyk    = models.CharField(max_length=1, choices=KOSZYK)

    class Meta:
        unique_together = [('losowanie', 'gracz')]
        ordering        = ['koszyk', 'gracz__last_name']

    def __str__(self):
        return f'{self.gracz.display_name()} [{self.koszyk}]'


class MeczLosowania(models.Model):
    losowanie = models.ForeignKey(LosowanieELO, on_delete=models.CASCADE,
                                  related_name='mecze')
    kolejka   = models.PositiveSmallIntegerField('Kolejka')
    gracz_a   = models.ForeignKey(Player, on_delete=models.PROTECT,
                                  related_name='losowania_jako_a')
    gracz_b   = models.ForeignKey(Player, on_delete=models.PROTECT,
                                  related_name='losowania_jako_b',
                                  null=True, blank=True)
    czy_bye   = models.BooleanField('BYE', default=False)

    class Meta:
        ordering = ['kolejka', 'id']

    def __str__(self):
        if self.czy_bye:
            return f'K{self.kolejka}: {self.gracz_a.display_name()} — BYE'
        return f'K{self.kolejka}: {self.gracz_a.display_name()} vs {self.gracz_b.display_name()}'


# ─────────────────────────────────────────────────────────────────────
#  TURNIEJE
# ─────────────────────────────────────────────────────────────────────

class Turniej(models.Model):
    nazwa      = models.CharField('Nazwa', max_length=100)
    data_start = models.DateField('Data rozpoczęcia', blank=True, null=True)
    data_koniec = models.DateField('Data zakończenia', blank=True, null=True)
    opis       = models.TextField('Opis', blank=True)
    notka      = RichTextField(
        'Notka o turnieju',
        blank=True, default='',
        help_text='Artykuł opisujący turniej — wyświetlany na osobnej podstronie.'
    )
    zdjecie    = models.ImageField(
        'Zdjęcie',
        upload_to='turnieje/',
        blank=True, null=True,
        help_text='Opcjonalne zdjęcie wyświetlane w notce turnieju.'
    )

    class Meta:
        verbose_name        = 'Turniej'
        verbose_name_plural = 'Turnieje'
        ordering            = ['-data_start']

    def __str__(self):
        return self.nazwa


class Etap(models.Model):
    TYP_CHOICES = [
        ('grupowy',   'Grupowy'),
        ('pucharowy', 'Pucharowy'),
    ]

    turniej    = models.ForeignKey(Turniej, on_delete=models.CASCADE,
                                   related_name='etapy', verbose_name='Turniej')
    nazwa      = models.CharField('Nazwa', max_length=100)
    typ        = models.CharField('Typ', max_length=20, choices=TYP_CHOICES)
    poziom     = models.PositiveSmallIntegerField(
        'Poziom',
        help_text='Określa kolejność etapów: 1 = faza grupowa, 2 = ćwierćfinały, 3 = finał itp.'
    )
    obrazek    = models.ImageField(
        'Drabinka (obrazek)',
        upload_to='drabinki/',
        blank=True, null=True,
        help_text='Wyświetlany przy etapach pucharowych. Zostaw puste = placeholder.'
    )
    sumuj_punkty_z_poprzednich = models.BooleanField(
        'Sumuj punkty z poprzednich poziomów',
        default=False,
        help_text='Jeśli zaznaczone, punkty gracza ze wszystkich etapów grupowych '
                  'o niższym poziomie w tym turnieju zostaną dodane jako punkty startowe.'
    )

    class Meta:
        verbose_name        = 'Etap'
        verbose_name_plural = 'Etapy'
        ordering            = ['turniej', 'poziom', 'nazwa']

    def __str__(self):
        return f'{self.turniej.nazwa} › {self.nazwa}'


class UczestnikTurnieju(models.Model):
    """Gracz przypisany do turnieju wraz z zespołem którym gra."""
    turniej = models.ForeignKey(Turniej, on_delete=models.CASCADE,
                                related_name='uczestnicy', verbose_name='Turniej')
    gracz   = models.ForeignKey(Player, on_delete=models.PROTECT, verbose_name='Gracz')
    zespol          = models.CharField('Zespół', max_length=100)
    ulubiony_klub   = models.CharField('Ulubiony klub', max_length=100,
                                       blank=True, default='',
                                       help_text='Zostaw puste jeśli gracz nie kibicuje żadnemu klubowi.')

    class Meta:
        verbose_name        = 'Uczestnik turnieju'
        verbose_name_plural = 'Uczestnicy turnieju'
        unique_together     = [('turniej', 'gracz')]
        ordering            = ['gracz__last_name']

    def __str__(self):
        return f'{self.gracz.display_name()} — {self.zespol} ({self.turniej.nazwa})'


# ─────────────────────────────────────────────────────────────────────
#  MECZE TURNIEJOWE
# ─────────────────────────────────────────────────────────────────────

class Mecz(models.Model):
    STATUS_CHOICES = [
        ('zaplanowany', 'Zaplanowany'),
        ('rozegrany',   'Rozegrany'),
        ('wolny_los',   'Wolny los'),
    ]
    ZWYCIEZCA_CHOICES = [
        ('A',    'Gracz A'),
        ('B',    'Gracz B'),
        ('remis', 'Remis'),
    ]

    turniej = models.ForeignKey(Turniej, on_delete=models.PROTECT,
                                related_name='mecze', verbose_name='Turniej')
    etap    = models.ForeignKey(Etap, on_delete=models.PROTECT,
                                related_name='mecze', verbose_name='Etap')

    gracz_a = models.ForeignKey(Player, on_delete=models.PROTECT,
                                related_name='mecze_jako_a', verbose_name='Gracz A')
    gracz_b = models.ForeignKey(Player, on_delete=models.PROTECT,
                                related_name='mecze_jako_b', verbose_name='Gracz B',
                                null=True, blank=True,
                                help_text='Zostaw puste dla wolnego losu')

    gole_a     = models.PositiveSmallIntegerField('Gole A', null=True, blank=True)
    gole_b     = models.PositiveSmallIntegerField('Gole B', null=True, blank=True)
    zolte_a    = models.PositiveSmallIntegerField('Żółte kartki A', default=0)
    zolte_b    = models.PositiveSmallIntegerField('Żółte kartki B', default=0)
    czerwone_a = models.PositiveSmallIntegerField('Czerwone kartki A', default=0)
    czerwone_b = models.PositiveSmallIntegerField('Czerwone kartki B', default=0)

    zwyciezca = models.CharField('Zwycięzca', max_length=10,
                                 choices=ZWYCIEZCA_CHOICES,
                                 null=True, blank=True)
    status    = models.CharField('Status', max_length=20,
                                 choices=STATUS_CHOICES,
                                 default='zaplanowany')

    data = models.DateField('Data meczu', null=True, blank=True)
    opis = models.TextField('Opis / notatki', blank=True)

    class Meta:
        verbose_name        = 'Mecz'
        verbose_name_plural = 'Mecze'
        ordering            = ['turniej', 'etap__poziom', 'data']

    def __str__(self):
        b = self.gracz_b.display_name() if self.gracz_b else 'BYE'
        return f'{self.gracz_a.display_name()} vs {b} ({self.etap})'

    def punkty_a(self):
        """Zwraca punkty zdobyte przez gracza A."""
        if self.status == 'wolny_los':
            return 3
        if self.zwyciezca == 'A':
            return 3
        if self.zwyciezca == 'remis':
            return 1
        return 0

    def punkty_b(self):
        """Zwraca punkty zdobyte przez gracza B (0 przy wolnym losie)."""
        if self.status == 'wolny_los' or self.gracz_b is None:
            return 0
        if self.zwyciezca == 'B':
            return 3
        if self.zwyciezca == 'remis':
            return 1
        return 0

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        self.przelicz_wystepy()

    def przelicz_wystepy(self):
        """
        Usuwa i tworzy na nowo rekordy WystepGracza dla tego meczu.
        Wywołuj ręcznie po zapisaniu/edycji meczu.
        """
        # Usuń stare rekordy
        WystepGracza.objects.filter(mecz=self).delete()

        # Nie twórz wystąpień dla zaplanowanych meczów
        if self.status == 'zaplanowany':
            return

        # Gracz A
        WystepGracza.objects.create(
            mecz             = self,
            turniej          = self.turniej,
            etap             = self.etap,
            gracz            = self.gracz_a,
            przeciwnik       = self.gracz_b,
            gole_strzelone   = self.gole_a or 0,
            gole_stracone    = self.gole_b or 0,
            zolte_kartki     = self.zolte_a,
            czerwone_kartki  = self.czerwone_a,
            punkty           = self.punkty_a(),
        )

        # Gracz B (tylko jeśli nie wolny los)
        if self.gracz_b and self.status != 'wolny_los':
            WystepGracza.objects.create(
                mecz             = self,
                turniej          = self.turniej,
                etap             = self.etap,
                gracz            = self.gracz_b,
                przeciwnik       = self.gracz_a,
                gole_strzelone   = self.gole_b or 0,
                gole_stracone    = self.gole_a or 0,
                zolte_kartki     = self.zolte_b,
                czerwone_kartki  = self.czerwone_b,
                punkty           = self.punkty_b(),
            )


# ─────────────────────────────────────────────────────────────────────
#  STATYSTYKI
# ─────────────────────────────────────────────────────────────────────

class WystepGracza(models.Model):
    """
    Jeden rekord = jeden gracz w jednym meczu.
    Generowany i przeliczany przez Mecz.przelicz_wystepy().
    Nie edytuj ręcznie — zawsze przeliczaj przez mecz.
    """
    mecz            = models.ForeignKey(Mecz, on_delete=models.CASCADE,
                                        related_name='wystepy')
    turniej         = models.ForeignKey(Turniej, on_delete=models.PROTECT,
                                        related_name='wystepy')
    etap            = models.ForeignKey(Etap, on_delete=models.PROTECT,
                                        related_name='wystepy')
    gracz           = models.ForeignKey(Player, on_delete=models.PROTECT,
                                        related_name='wystepy')
    przeciwnik      = models.ForeignKey(Player, on_delete=models.PROTECT,
                                        related_name='wystepy_jako_przeciwnik',
                                        null=True, blank=True)

    gole_strzelone  = models.PositiveSmallIntegerField(default=0)
    gole_stracone   = models.PositiveSmallIntegerField(default=0)
    zolte_kartki    = models.PositiveSmallIntegerField(default=0)
    czerwone_kartki = models.PositiveSmallIntegerField(default=0)
    punkty          = models.PositiveSmallIntegerField(default=0)

    class Meta:
        verbose_name        = 'Występ gracza'
        verbose_name_plural = 'Występy graczy'
        ordering            = ['turniej', 'etap__poziom', 'mecz']

    def __str__(self):
        return f'{self.gracz.display_name()} | {self.mecz} | {self.punkty} pkt'


# ─────────────────────────────────────────────────────────────────────
#  SYSTEM SZWAJCARSKI
# ─────────────────────────────────────────────────────────────────────

class SzwajcarKolejka(models.Model):
    """Jedna wygenerowana kolejka systemu szwajcarskiego."""
    turniej         = models.ForeignKey(Turniej, on_delete=models.CASCADE,
                                        related_name='szwajcar_kolejki')
    numer           = models.PositiveSmallIntegerField('Numer kolejki')
    data_utworzenia = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name        = 'Kolejka szwajcarska'
        verbose_name_plural = 'Kolejki szwajcarskie'
        unique_together     = [('turniej', 'numer')]
        ordering            = ['turniej', 'numer']

    def __str__(self):
        return f'{self.turniej.nazwa} — kolejka {self.numer}'


class SzwajcarPara(models.Model):
    """Para graczy w jednej kolejce szwajcarskiej."""
    kolejka = models.ForeignKey(SzwajcarKolejka, on_delete=models.CASCADE,
                                related_name='pary')
    gracz_a = models.ForeignKey(Player, on_delete=models.PROTECT,
                                related_name='szwajcar_jako_a')
    gracz_b = models.ForeignKey(Player, on_delete=models.PROTECT,
                                related_name='szwajcar_jako_b',
                                null=True, blank=True,
                                help_text='Null = wolny los dla gracza A')

    class Meta:
        ordering = ['kolejka', 'id']

    def __str__(self):
        b = self.gracz_b.display_name() if self.gracz_b else 'BYE'
        return f'{self.kolejka} | {self.gracz_a.display_name()} vs {b}'


# ─────────────────────────────────────────────────────────────────────
#  TYPER TURNIEJOWY
# ─────────────────────────────────────────────────────────────────────

class WynikTurnieju(models.Model):
    """
    Poprawne odpowiedzi dla typera — wpisywane ręcznie po zakończeniu turnieju.
    Jeden rekord na turniej.
    """
    turniej         = models.OneToOneField(Turniej, on_delete=models.CASCADE,
                                           related_name='wynik', verbose_name='Turniej')
    miejsce_1       = models.ForeignKey(Player, on_delete=models.PROTECT,
                                        related_name='+', verbose_name='1. miejsce',
                                        null=True, blank=True)
    miejsce_2       = models.ForeignKey(Player, on_delete=models.PROTECT,
                                        related_name='+', verbose_name='2. miejsce',
                                        null=True, blank=True)
    miejsce_3       = models.ForeignKey(Player, on_delete=models.PROTECT,
                                        related_name='+', verbose_name='3. miejsce',
                                        null=True, blank=True)
    miejsce_ostatnie = models.ForeignKey(Player, on_delete=models.PROTECT,
                                         related_name='+', verbose_name='Ostatnie miejsce',
                                         null=True, blank=True)
    krol_strzelcow  = models.ForeignKey(Player, on_delete=models.PROTECT,
                                        related_name='+', verbose_name='Król strzelców',
                                        null=True, blank=True)
    murarz          = models.ForeignKey(Player, on_delete=models.PROTECT,
                                        related_name='+', verbose_name='Murarz',
                                        null=True, blank=True)
    kosiarz         = models.ForeignKey(Player, on_delete=models.PROTECT,
                                        related_name='+', verbose_name='Kosiarz',
                                        null=True, blank=True)
    zwycięski_klub  = models.CharField('Zwycięski klub', max_length=100,
                                       blank=True, default='')

    class Meta:
        verbose_name        = 'Wynik turnieju (typer)'
        verbose_name_plural = 'Wyniki turniejów (typer)'

    def __str__(self):
        return f'Wyniki — {self.turniej.nazwa}'


class TypTurnieju(models.Model):
    """
    Odpowiedzi jednego gracza w typerze — wpisywane ręcznie przez admina.
    """
    turniej         = models.ForeignKey(Turniej, on_delete=models.CASCADE,
                                        related_name='typy', verbose_name='Turniej')
    gracz           = models.ForeignKey(Player, on_delete=models.PROTECT,
                                        related_name='typy', verbose_name='Gracz typujący')
    miejsce_1       = models.ForeignKey(Player, on_delete=models.PROTECT,
                                        related_name='+', verbose_name='Typ: 1. miejsce',
                                        null=True, blank=True)
    miejsce_2       = models.ForeignKey(Player, on_delete=models.PROTECT,
                                        related_name='+', verbose_name='Typ: 2. miejsce',
                                        null=True, blank=True)
    miejsce_3       = models.ForeignKey(Player, on_delete=models.PROTECT,
                                        related_name='+', verbose_name='Typ: 3. miejsce',
                                        null=True, blank=True)
    miejsce_ostatnie = models.ForeignKey(Player, on_delete=models.PROTECT,
                                         related_name='+', verbose_name='Typ: Ostatnie miejsce',
                                         null=True, blank=True)
    krol_strzelcow  = models.ForeignKey(Player, on_delete=models.PROTECT,
                                        related_name='+', verbose_name='Typ: Król strzelców',
                                        null=True, blank=True)
    murarz          = models.ForeignKey(Player, on_delete=models.PROTECT,
                                        related_name='+', verbose_name='Typ: Murarz',
                                        null=True, blank=True)
    kosiarz         = models.ForeignKey(Player, on_delete=models.PROTECT,
                                        related_name='+', verbose_name='Typ: Kosiarz',
                                        null=True, blank=True)
    zwycięski_klub  = models.CharField('Typ: Zwycięski klub', max_length=100,
                                       blank=True, default='')

    class Meta:
        verbose_name        = 'Typ gracza'
        verbose_name_plural = 'Typy graczy'
        unique_together     = [('turniej', 'gracz')]
        ordering            = ['turniej', 'gracz__last_name']

    def __str__(self):
        return f'{self.gracz.display_name()} — {self.turniej.nazwa}'

    def oblicz_punkty(self, wynik):
        """
        Oblicza punkty dla tego typa na podstawie obiektu WynikTurnieju.
        Zwraca liczbę punktów (int).
        """
        if not wynik:
            return 0

        pkt = 0
        podium_wynik  = [wynik.miejsce_1_id, wynik.miejsce_2_id, wynik.miejsce_3_id]
        podium_wynik_bez_none = [p for p in podium_wynik if p]

        # Miejsca 1-3: 2 pkt za dokładne trafienie, 1 pkt jeśli trafiony gracz jest gdzieś w podium
        for typ_id, wynik_id, pozycja in [
            (self.miejsce_1_id,  wynik.miejsce_1_id,  1),
            (self.miejsce_2_id,  wynik.miejsce_2_id,  2),
            (self.miejsce_3_id,  wynik.miejsce_3_id,  3),
        ]:
            if not typ_id:
                continue
            if typ_id == wynik_id:
                pkt += 2
            elif typ_id in podium_wynik_bez_none:
                pkt += 1

        # Ostatnie miejsce: 1 pkt
        if self.miejsce_ostatnie_id and self.miejsce_ostatnie_id == wynik.miejsce_ostatnie_id:
            pkt += 1

        # Król strzelców: 1 pkt
        if self.krol_strzelcow_id and self.krol_strzelcow_id == wynik.krol_strzelcow_id:
            pkt += 1

        # Murarz: 1 pkt
        if self.murarz_id and self.murarz_id == wynik.murarz_id:
            pkt += 1

        # Kosiarz: 1 pkt
        if self.kosiarz_id and self.kosiarz_id == wynik.kosiarz_id:
            pkt += 1

        # Zwycięski klub: 1 pkt
        if self.zwycięski_klub and self.zwycięski_klub == wynik.zwycięski_klub:
            pkt += 1

        return pkt
