# MoreOrLess

## Inspiración

El clásico juego de "más o menos": comparar si un valor desconocido es mayor o menor que uno ya
conocido. Es el mismo mecanismo detrás de segmentos como "adivina el precio" en programas de TV.

## Cómo se juega

Se muestra un candidato A junto con su número real (ej: "la persona A tiene 107 fotos"). Se muestra
un candidato B, sin su número. El jugador debe decir si B tiene **más** o **menos** que A.

- Si acierta: B pasa a ser la nueva referencia (con su número ahora visible), se elige un candidato
  C al azar (sin repetir candidatos ya mostrados en esta partida) y se repite la pregunta.
- Si falla: la partida termina.

## Puntaje y fin de partida

- Cada ronda acertada vale 1 punto; el puntaje total de la partida es la cantidad de aciertos
  seguidos (la racha).
- `hay_nuevo_round?`: si acertó, hay ronda nueva; si falló, la partida termina.

## Modos

| Modo | Qué se compara | Prioridad |
|---|---|---|
| `personAssets` | Cantidad de fotos/videos de una persona | Inicial |
| `albumAssets` | Cantidad de fotos/videos de un álbum | Futuro |
| `assetDate` | Fecha en que se tomó una foto | Futuro |
| `personBirthDate` | Fecha de cumpleaños de una persona | Futuro |

Ver [docs/TODO/ROADMAP.md](../TODO/ROADMAP.md) para cuándo se implementa cada modo futuro.
