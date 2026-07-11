"""
Basado en el juego Geoguessr.
Se entregan 1-5 assets que estén en una misma ubicación (Puede haber una diferencia menor entre ellos).
El jugador deberá marcar en el mapa, dónde fueron tomados esos assets.
"""


"""
GeoguessrGame(BaseGame):
    Atributos: Tal cuál ABC

    Metodos:
        hay_nuevo_round?:
            si round actual == 5, no hay más rounds.
"""

"""
GeoguessrRound(BaseRound):
    Atributos: Tal cuál ABC

    Metodos:
        calcular_puntaje:
            Clavar la ubicación da 5000, mientras uno se aleja el puntaje va bajando.
"""