"""
(ABC) Clase base para cada juego.
Define lo minimo que debe implementar un juego para ser compatible con el sistema.
"""

"""
BaseGame:
    Atributos:
        ID
        Owner
        tipo (slug del minijuego)
        modo (slug del modo - se guarda desde el día 1 aunque cada juego tenga un solo modo válido)
        *Seed* (no en la versión inicial - se agrega al implementar el daily game, para que todos
            los jugadores de un mismo día vean el mismo desafío)
        puntaje: int
        rounds: list[Round]
        finalizado: bool
    
    Metodos:
        Crear
        Jugar_round
            Da una respuesta
            aplica sobre el puntaje el delta devuelto por calcular_puntaje del round
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
        guess_del_jugador
        entidades_mostradas (ids de assets y/o personas mostrados en la ronda - necesario para
            "Ver rounds" y para la futura feature de reportar metadata incorrecta)

    Métodos:
        calcular_puntaje:
            Devuelve el delta (puede ser negativo) a aplicar sobre el puntaje del Game,
            no el puntaje absoluto de la ronda. Es el Game quien lo suma/resta sobre su total.
"""