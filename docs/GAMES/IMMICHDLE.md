# Immichdle

## Inspiración

Los juegos estilo Wordle ("*dle"), en particular su variante "adivina al personaje/persona"
(persondle): hay un objetivo oculto y cada intento revela pistas comparativas que van acotando la
respuesta.

## Cómo se juega

Se elige al azar una persona incógnita. El jugador va probando nombres de otras personas como
intento. Cada intento entrega pistas comparativas contra el incógnito:

- **Age**: mayor, menor, igual o desconocido.
- **AssetCount**: mayor, menor o igual cantidad de fotos.
- **FirstApparicion**: si el primer asset de la persona es antes, después o el mismo que el del
  incógnito.
- **CommonNames**: separando el nombre por espacios (`split(" ")`), cuántos nombres/apellidos tiene
  en común con el incógnito.
- **MLSimilarity**: similitud de caras según Immich-ML.
- **AssetTogether**: cantidad de fotos donde salen juntos el incógnito y el candidato probado.

Cada 5 intentos se revela además una pista extra (en este orden): cantidad de nombres del
incógnito, cantidad de letras de cada nombre, iniciales de cada nombre, y finalmente su thumbnail.
**La versión inicial sale sin este sistema de pistas reveladas por intentos** - todas las pistas
comparativas de arriba están desde el principio, y las reveladas por intentos quedan para después.

## Puntaje y fin de partida

- El puntaje inicial es 100. Este valor es el correcto **mientras no exista el sistema de pistas
  reveladas por intentos** (ver sección Modos - ese sistema es futuro, roadmap ítem 11). Cuando se
  implemente ese sistema de pistas, el puntaje inicial debe subir a ~200, para que el costo por
  intento fallido/pista revelada se mantenga proporcional sin cambiar el resto de las reglas. Hasta
  entonces, 100 es la fuente de verdad.
- Cada intento fallido resta 5 puntos; cada pista extra revelada (de las que se agregan después)
  resta 10 puntos.
- El puntaje nunca baja de 0: si un descuento lo dejaría negativo, se floorea en 0.
- `hay_nuevo_round?`: si el intento fue correcto, la partida termina (ganada); si el puntaje
  (ya floreado en 0) llega a 0, la partida termina (perdida); en cualquier otro caso, hay una ronda
  nueva.

## Modos

| Modo | Sobre qué se juega | Prioridad |
|---|---|---|
| `person` | Personas (pistas de arriba) | Inicial |
| `album` (albumdle) | Álbumes - pistas: FirstAssetDate, AssetCount, ThumbMLSimilarity, CommonAssets, CommonNames, Duration (diferencia entre primera y última fecha) | Futuro |

Ver [docs/TODO/ROADMAP.md](../TODO/ROADMAP.md) para cuándo se implementa el modo `album`.
