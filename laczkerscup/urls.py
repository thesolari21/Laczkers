from django.urls import path
from . import views

app_name = 'laczkerscup'

urlpatterns = [
    # Istniejące
    path('',                                views.index,       name='index'),
    path('elo/',                            views.elo,         name='elo'),
    path('elo/history/<int:player_id>/',    views.elo_history, name='elo_history'),

    # Turnieje
    path('turnieje/',                       views.turnieje,        name='turnieje'),
    path('turnieje/<int:pk>/',              views.turniej_detail,  name='turniej_detail'),
    path('turnieje/<int:turniej_pk>/gracz/<int:gracz_pk>/', views.gracz_w_turnieju, name='gracz_turniej'),

    # System szwajcarski
    path('szwajcar/',                       views.szwajcar_formularz, name='szwajcar'),
    path('szwajcar/usun/<int:pk>/',         views.szwajcar_usun_kolejke, name='szwajcar_usun'),

    # Losowanie ELO
    path('losowanie_elo/',                  views.losowanie_formularz, name='losowanie_formularz'),
    path('losowanie_elo/wyniki/<int:pk>/',  views.losowanie_wyniki,    name='losowanie_wyniki'),
    path('losowanie_elo/historia/',         views.losowanie_lista,     name='losowanie_lista'),
]
