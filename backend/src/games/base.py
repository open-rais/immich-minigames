"""
(ABC) Clase base para cada juego.
Define lo minimo que debe implementar un juego para ser compatible con el sistema.
"""

"""
BaseGame:
    Atributos:
        ID
        Owner
        *Seed* (Para un principio quizas sea mejor no tener seed)
        puntaje: int
        rounds: list[Round]
        finalizado: bool
    
    Metodos:
        Crear
        Jugar_round
            Da una respuesta
            cambia puntaje según corresponda
            Valida si con esto el juego termina o se crea un nuevo round
        Hay_nuevo_round?
        crear_nuevo_round (La idea es que esto conozca los rounds anteriores para no repetir)
"""

"""
BaseRound:
    Atributos:
        ID
        Game
        round_index
        respuesta_correcta
    
    Métodos:
        calcular_puntaje
"""