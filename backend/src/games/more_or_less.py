"""
Basado en el juego More Or Less.
Se entrega una persona y su cuenta de assets,
Se muestra una segunda persona, ¿esta nueva persona tiene más o menos assets?
El usuario debe ingresar una opción. Si es correcta, esta segunda queda como referencia,
y se busca otra persona al azar y se vuelve a hacer la pregunta.
"""


"""
MoreOrLessGame(BaseGame):
    Atributos: Tal cual ABC

    Metodos:
        hay_nuevo_round?:
            si le achuntó al resultado, hay nuevo round,
            Si no le achuntó, termina
"""

"""
MoreOrLessRound(BaseRound):
    Atributos: Tal cuál ABC

    Metodos:
        calcular_puntaje:
            si es correcto, puntaje es 1
            Si es incorrecto, puntaje 0
"""