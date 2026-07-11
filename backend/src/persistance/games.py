"""
Estos son los modelos necesarios para los juegos que estarán en la BDD
"""


"""
GameModel
    - id
    - owner: id anónimo de sesión del cliente (no requiere login ni Redis, ver
      docs/ARCHITECTURE/BACKEND.md); si se pierde ese id, el juego queda huérfano.
    - tipo (slug del minijuego)
    - modo (slug del modo; se guarda desde el día 1 aunque cada juego tenga un solo modo válido)
    - puntaje
    - finalizado
    - createdAt
"""

"""
RoundModel
    - id
    - gameId
    - round_index
    - respuesta_correcta
    - guess_del_jugador
    - entidades_mostradas: ids de los assets y/o personas mostrados en la ronda (persona en
      MoreOrLess/Immichdle, assets en Geoguessr/Dateguessr/Timeline/Who'sThatPerson) - necesario
      para la futura vista "Ver rounds" y para la futura feature de reportar metadata incorrecta.
"""