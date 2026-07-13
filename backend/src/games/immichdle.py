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
        score: comienza en 100 (subirá a 200 cuando exista el sistema de pistas por intento, ver
            docs/GAMES/IMMICHDLE.md). Nunca baja de 0 (se floorea en 0 al aplicar un delta negativo).

    Metodos:
        has_next_round():
            si le achuntó al resultado, no hay nuevo round
            Si score (ya floreado en 0) == 0, no hay nuevo round
            En otro caso, se crea nuevo round
"""

"""
ImmichdleRound(BaseRound):
    Atributos: Tal cuál ABC

    Metodos:
        calculate_score():
            devuelve el delta: 0 si es correcto, negativo si es incorrecto (baja el score).
"""