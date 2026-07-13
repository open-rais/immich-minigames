# MoreOrLess

## Inspiración

El clásico [More Or Less](https://moreorless.io/): comparar si un valor desconocido es mayor o menor
que uno ya conocido. Es el mismo mecanismo detrás de segmentos como "adivina el precio" en programas
de TV.

## Cómo se juega

Se muestra un candidato A junto con su número real (ej: "la persona A tiene 107 fotos"). Se muestra
un candidato B, sin su número. El jugador debe decir si B tiene **más** o **menos** que A.

- Si acierta: B pasa a ser la nueva referencia (con su número ahora visible), se elige un candidato
  C al azar y se repite la pregunta.
- Si falla: la partida termina.
- **Empate** (A y B tienen exactamente el mismo número): no cuenta como fallo sin importar qué haya
  respondido el jugador - siempre se trata como acierto. Se intenta evitar el empate al elegir
  candidato (ver `_pick_non_tied_candidate` en `more_or_less.py`), pero si igual ocurre (ej. muchas
  personas con el mismo conteo), no debe terminar la partida injustamente.
- La partida es **infinita**: los candidatos sí se pueden repetir (no hay una cantidad fija de
  personas en la biblioteca, así que el juego no puede depender de "no repetir nunca"). Lo que se
  evita es repetir a alguien mostrado muy recientemente - se recuerdan las últimas
  `_RECENT_EXCLUDE_WINDOW` personas (10 al momento de escribir esto) y esas no se vuelven a elegir
  hasta que "se les pierda el rastro" (salgan de esa ventana).

## Puntaje y fin de partida

- Cada ronda acertada (o empatada) vale 1 punto; el puntaje total de la partida es la cantidad de
  aciertos seguidos (la racha).
- `has_next_round()`: si acertó (o empató), hay ronda nueva; si falló, la partida termina. No
  termina por quedarse sin candidatos nuevos - ver la nota de "partida infinita" arriba.

## Modos

| Modo | Qué se compara | Prioridad |
|---|---|---|
| `personAssets` | Cantidad de fotos/videos de una persona | Inicial |
| `albumAssets` | Cantidad de fotos/videos de un álbum | Futuro |
| `assetDate` | Fecha en que se tomó una foto | Futuro |
| `personBirthDate` | Fecha de cumpleaños de una persona | Futuro |

Ver [docs/TODO/ROADMAP.md](../TODO/ROADMAP.md) para cuándo se implementa cada modo futuro.
