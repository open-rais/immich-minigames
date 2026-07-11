"""
Servicio de los juegos,
aca se implementan las funciones que se encargan de la logica de negocio de los juegos.
"""


"""
GamesService:
    Metodos:
        crear_juego:
            Crea un juego de un tipo determinado, con un owner determinado.
        ver_round_actual_de_un_juego:
            Devuelve el round actual de un juego determinado.
        jugar_round_de_un_juego:
            Recibe la respuesta del usuario, valida si es correcta o no, y devuelve el puntaje obtenido y si el juego continua o no.
        ver_puntaje_de_un_juego:
            Devuelve el puntaje actual de un juego determinado.
        ver_juego_por_id:
            Devuelve el juego completo, con todos sus rounds, de un juego determinado.
        ver_juegos_por_owner:
            Devuelve todos los juegos de un owner determinado.
        ver_juegos_por_tipo:
            Devuelve todos los juegos de un tipo determinado.
        listar_minijuegos_disponibles:
            Devuelve todos los tipos de minijuegos disponibles.
"""