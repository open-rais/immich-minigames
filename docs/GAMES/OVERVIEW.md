# Minijuegos: visión general

Immich Minigames toma la metadata que ya vive en tu instancia de Immich (personas, álbumes, fechas,
ubicaciones, similitud de caras via Immich-ML) y la convierte en minijuegos de memoria/trivia sobre
tu propia biblioteca de fotos. La gracia es doble: entretiene, y de paso motiva a mantener la
metadata de Immich bien puesta (nombres, cumpleaños, ubicaciones) porque de eso salen los juegos.

Todos los juegos comparten la misma base técnica (ver más abajo) y solo difieren en dos cosas: qué
dato de Immich usan como pregunta, y cómo calculan el puntaje. Esto hace que agregar un juego nuevo
sea, en teoría, agregar solo esas dos reglas - el resto (persistencia, loop de rondas, API genérica)
ya está resuelto por la base compartida.

## Base compartida: `Game` y `Round`

Cada partida jugada es un **`Game`**: tiene un id, un owner (quién juega), un puntaje acumulado, la
lista de `Round`s jugados hasta ahora, y una bandera de si ya terminó (`finished`).

Cada pregunta individual dentro de una partida es un **`Round`**: tiene un id, referencia a su
`Game`, un índice (qué ronda es), la respuesta correcta contra la que se compara el guess del
jugador, el guess que efectivamente ingresó, y las entidades mostradas (assets y/o personas según
el juego) - estas últimas dos se guardan para poder reconstruir la ronda después (vista futura "Ver
rounds", y la futura feature de reportar metadata incorrecta).

El loop de juego es siempre el mismo, sin importar cuál minijuego sea:

1. Se le muestra al jugador la pregunta del round actual (definida por la respuesta correcta que
   guarda el `Round`).
2. El jugador envía su guess.
3. El `Round` calcula el *delta* de puntaje de esa jugada (`calculate_score()`) - puede ser positivo
   o negativo, y esta regla es específica de cada juego (ver el doc de cada uno).
4. El `Game` aplica ese delta sobre su puntaje acumulado.
5. El `Game` decide si corresponde crear un nuevo round (`has_next_round()`) - esta regla también es
   específica de cada juego (por ejemplo: "hasta la 5ta ronda", "hasta que se falle una vez", "hasta
   adivinar o quedarse sin puntaje"). Si se crea un nuevo round, este conoce las rondas anteriores
   para no repetir candidatos dentro de la misma partida.
6. Si no hay nuevo round, el `Game` queda `finished`.

Gracias a este diseño (patrón Template Method), cada juego nuevo solo necesita responder dos
preguntas - "¿cuándo termina esta partida?" y "¿cuántos puntos vale este guess?" - todo lo demás
(API, persistencia, orquestación) es compartido.

> Nota de idioma: los nombres de clases/métodos/atributos del código son en inglés (`finished`,
> `has_next_round()`, `calculate_score()`, etc., ver `games/base.py`) - las descripciones en
> español de este doc y de cada juego son a propósito (diseño/brainstorming en el idioma natal del
> dueño del proyecto), no una traducción pendiente.

## Catálogo de juegos

| Juego | Inspiración | Mecánica central | Doc |
|---|---|---|---|
| MoreOrLess | El clásico "más o menos" (comparar si algo es mayor o menor, al estilo de los segmentos de "adivina el precio") | Comparar un dato de un candidato B contra un candidato A ya revelado; fallar termina el juego | [MORE_OR_LESS.md](./MORE_OR_LESS.md) |
| Geoguessr | El juego online [GeoGuessr](https://www.geoguessr.com/) | Ubicar en un mapa dónde se tomó una foto; el puntaje decae con la distancia al lugar real | [GEOGUESSR.md](./GEOGUESSR.md) |
| Dateguessr | Geoguessr, pero adivinando fecha en vez de lugar | Ubicar en una línea de tiempo cuándo se tomó una foto; el puntaje decae con la distancia a la fecha real | [DATEGUESSR.md](./DATEGUESSR.md) |
| Immichdle | Los juegos estilo Wordle ("*dle"), en su variante "adivina a la persona/personaje" (persondle) | Adivinar una persona incógnita a partir de pistas comparativas con cada intento | [IMMICHDLE.md](./IMMICHDLE.md) |
| Timeline | El juego de mesa ["Timeline"](https://en.wikipedia.org/wiki/Timeline_(card_game)) | Insertar una foto en el orden cronológico correcto respecto a las fotos ya puestas | [TIMELINE.md](./TIMELINE.md) |
| Who'sThatPerson | El segmento "Who's That Pokémon?" del anime de Pokémon | Adivinar el nombre de una persona cuya cara aparece tapada en una foto | [WHOS_THAT_PERSON.md](./WHOS_THAT_PERSON.md) |

Cada juego tiene además "modos" adicionales (variantes de qué dato se usa como pregunta) que son de
menor prioridad y llegarán más adelante - ver [docs/TODO/ROADMAP.md](../TODO/ROADMAP.md) para el
orden real de implementación. El detalle de cada modo está en el doc de su propio juego.
