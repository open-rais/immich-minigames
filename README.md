# Immich Minigames

Minijuegos de memoria hechos con la propia metadata de tu biblioteca de [Immich](https://immich.app).

Nada de bancos de preguntas genéricos: cada partida es sobre tu gente, tus viajes, tus fotos.
¿Cuántas fotos tiene esa persona? ¿Dónde se tomó esta? ¿De quién es esta cara tapada?

> Proyecto no oficial, sin afiliación con el equipo de Immich. Corre al lado de una instancia de
> Immich ya existente, reutilizando su misma base de datos y su servicio Immich-ML - no guarda una
> copia aparte de tus fotos.

## ¿Por qué?

Dos pájaros de un tiro: es entretenido, y de paso premia tener la metadata bien puesta. Entre mejor
etiquetada esté tu biblioteca (nombres, cumpleaños, ubicaciones), mejores y más variados salen los
juegos - un incentivo simpático para no dejar el catalogueo a medias.

## Los juegos

| Juego | Inspirado en | La idea |
|---|---|---|
| **MoreOrLess** | El clásico "más o menos" | ¿Esta persona tiene más o menos fotos que la anterior? |
| **Geoguessr** | [GeoGuessr](https://www.geoguessr.com/) | Adivina en un mapa dónde se tomó la foto |
| **Dateguessr** | Geoguessr, pero con fechas | Adivina en una línea de tiempo cuándo se tomó la foto |
| **Immichdle** | Los juegos *dle (Wordle) | Adivina a la persona incógnita con pistas comparativas |
| **Timeline** | El juego de mesa *Timeline* | Ordena las fotos cronológicamente entre ellas |
| **Who'sThatPerson** | "Who's That Pokémon?" | Adivina quién es la persona de la cara tapada |

Cómo se juega cada uno en detalle, con sus modos y reglas de puntaje, está en
[`docs/GAMES/`](./docs/GAMES/OVERVIEW.md).

## Más adelante

Login de usuario, un desafío diario compartido, reportar metadata incorrecta desde el propio juego
- ideas para después de tener los juegos base andando, no para la primera versión. El orden real de
todo esto está en [`docs/TODO/ROADMAP.md`](./docs/TODO/ROADMAP.md).

## Estado

Recién empezando - todavía no hay nada jugable. Este README se va a poner serio (instalación, stack,
capturas) cuando haya al menos 3 o 4 minijuegos funcionando.
