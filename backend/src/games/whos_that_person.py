"""
Basado en Who's That Pokémon.
Se entrega un asset imágen con personas en la foto,
donde hay QRects de caras, se pondrá cuadros negros,
se debe tocar un cuadro y escribir la persona que esté ahí.
Máximo 5 caras tapadas por foto. Se juega hasta preguntar por 15 personas en total (15 rounds),
sin importar si se acierta o no.
"""

"""
WhosThatPersonGame(BaseGame):
    Atributos: Tal cuál ABC

    Metodos:
        has_next_round():
            hay nuevo round mientras round_index < 15; en el 15avo, termina.
"""

"""
WhosThatPersonRound(BaseRound):
    Atributos: Tal cuál ABC

    Metodos:
        calculate_score():
            devuelve el delta tipo combo: si acierta, el valor de la racha actual (que sube en 1
            respecto al acierto anterior consecutivo, partiendo en 1); si falla, 0 y resetea la
            racha a 0 (no resta score ya ganado).
"""