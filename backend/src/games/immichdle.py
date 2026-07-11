"""
Basado en los juegos *dle (Wordle).
Se tiene una persona incognita, hay que adivinar escribiendo otras personas y habrá pistas como:
- Age (Mayor, Menor, Igual?, Desconocido)
- AssetCount (Mayor, Menor, Igual)
- FirstApparison (Fecha del primer asset de la persona (Antes, después, Igual))
- CommonNames (Haciendo split(" "), cantidad de nombres (o apellidos) en común)
- MLSimilarity (Similitud de sus caras según ImmichML)
- AssetTogether (Cantidad de assets en los que el incognito y el guess tienen en común)
"""


"""
ImmichdleGame(BaseGame):
    Atributos:
        puntaje: comienza en 100

    Metodos:
        hay_nuevo_round?:
            si le achuntó al resultado, no hay nuevo round
            Si puntaje == 0, no hay nuevo round
            En otro caso, se crea nuevo round
"""

"""
ImmichdleRound(BaseRound):
    Atributos: Tal cuál ABC

    Metodos:
        calcular_puntaje:
            si es correcto, puntaje es 0, si es incorrecto baja puntaje.
"""